# Requirements Document

## Introduction

Phase 2: Jellyfin Integration extends the Zondarr media server user management system with complete Jellyfin server support. This phase implements the JellyfinClient to communicate with Jellyfin servers, provides CRUD API endpoints for invitation management, enables invitation redemption with automatic user provisioning, and adds user listing with synchronization capabilities.

The implementation builds upon the Phase 1 foundation including the MediaClient protocol, ClientRegistry pattern, InvitationService, and existing SQLAlchemy models.

## Glossary

- **JellyfinClient**: The concrete implementation of the MediaClient protocol for communicating with Jellyfin media servers via the jellyfin-sdk library (webysther/jellyfin-sdk-python)
- **Invitation**: A time-limited, usage-limited code that grants access to one or more media servers and optionally specific libraries
- **Identity**: A user's account within Zondarr that links to multiple User accounts across different media servers
- **User**: A media server account on a specific server (Jellyfin or Plex) linked to an Identity
- **MediaServer**: A configured media server instance (Jellyfin or Plex) that Zondarr manages user access for
- **Library**: A content collection (movies, TV shows, music) within a media server that can be granted access to
- **Redemption**: The process of using an invitation code to create a new user account on target media servers
- **Sync**: The process of reconciling local User records with actual users on a media server
- **Permission_Mapping**: The translation layer between universal Zondarr permissions and Jellyfin-specific policy settings
- **External_User_ID**: The unique identifier for a user on the external media server (Jellyfin's GUID)

## Requirements

### Requirement 1: Jellyfin Client Connection Management

**User Story:** As a system administrator, I want the JellyfinClient to establish and manage connections to Jellyfin servers, so that I can verify server connectivity and authenticate API requests.

#### Acceptance Criteria

1. WHEN the JellyfinClient enters an async context THEN the System SHALL initialize a jellyfin.api instance with the configured URL and API key
2. WHEN the JellyfinClient exits an async context THEN the System SHALL release any resources held by the jellyfin.api instance
3. WHEN test_connection is called THEN the JellyfinClient SHALL use the jellyfin-sdk to query server info and return True if successful
4. IF the Jellyfin server is unreachable THEN the JellyfinClient SHALL return False from test_connection without raising an exception
5. IF the API key is invalid THEN the JellyfinClient SHALL return False from test_connection without raising an exception
6. THE JellyfinClient SHALL configure the jellyfin-sdk with the API key for authentication

### Requirement 2: Jellyfin Library Retrieval

**User Story:** As a system administrator, I want to retrieve the list of libraries from a Jellyfin server, so that I can configure which libraries users can access.

#### Acceptance Criteria

1. WHEN get_libraries is called THEN the JellyfinClient SHALL use the jellyfin-sdk to retrieve virtual folders from the server
2. WHEN libraries are retrieved THEN the JellyfinClient SHALL return a sequence of LibraryInfo objects containing external_id (ItemId), name (Name), and library_type (CollectionType)
3. IF the library retrieval fails THEN the JellyfinClient SHALL raise a MediaClientError with the failure details
4. THE JellyfinClient SHALL map Jellyfin CollectionType values (movies, tvshows, music, books, photos, homevideos, musicvideos, boxsets) to the library_type field

### Requirement 3: Jellyfin User Creation

**User Story:** As a system administrator, I want to create new users on Jellyfin servers, so that invited users can access media content.

#### Acceptance Criteria

1. WHEN create_user is called with username and password THEN the JellyfinClient SHALL use the jellyfin-sdk to create a new user
2. WHEN a user is successfully created THEN the JellyfinClient SHALL use the jellyfin-sdk to set the initial password
3. WHEN a user is successfully created THEN the JellyfinClient SHALL return an ExternalUser with the Jellyfin user Id, Name, and optional email
4. IF the username already exists on Jellyfin THEN the JellyfinClient SHALL raise a MediaClientError with error code USERNAME_TAKEN
5. IF user creation fails THEN the JellyfinClient SHALL raise a MediaClientError with the failure details

### Requirement 4: Jellyfin User Deletion

**User Story:** As a system administrator, I want to delete users from Jellyfin servers, so that I can revoke access when needed.

#### Acceptance Criteria

1. WHEN delete_user is called with an external_user_id THEN the JellyfinClient SHALL use the jellyfin-sdk to delete the user
2. WHEN a user is successfully deleted THEN the JellyfinClient SHALL return True
3. IF the user does not exist on Jellyfin THEN the JellyfinClient SHALL return False
4. IF user deletion fails for other reasons THEN the JellyfinClient SHALL raise a MediaClientError

### Requirement 5: Jellyfin User Enable/Disable

**User Story:** As a system administrator, I want to enable or disable users on Jellyfin servers, so that I can temporarily suspend access without deleting accounts.

#### Acceptance Criteria

1. WHEN set_user_enabled is called THEN the JellyfinClient SHALL use the jellyfin-sdk to retrieve the current user and their policy
2. WHEN set_user_enabled is called with enabled=True THEN the JellyfinClient SHALL update the user policy with IsDisabled=False
3. WHEN set_user_enabled is called with enabled=False THEN the JellyfinClient SHALL update the user policy with IsDisabled=True
4. WHEN the user status is successfully changed THEN the JellyfinClient SHALL return True
5. IF the user does not exist on Jellyfin THEN the JellyfinClient SHALL return False
6. IF the status change fails THEN the JellyfinClient SHALL raise a MediaClientError

### Requirement 6: Jellyfin Library Access Control

**User Story:** As a system administrator, I want to configure which libraries a user can access on Jellyfin, so that I can restrict content based on invitation settings.

#### Acceptance Criteria

1. WHEN set_library_access is called THEN the JellyfinClient SHALL use the jellyfin-sdk to retrieve the current user and their policy
2. WHEN set_library_access is called with a non-empty list of library_ids THEN the JellyfinClient SHALL update the user policy with EnableAllFolders=False and EnabledFolders set to the library IDs
3. WHEN set_library_access is called with an empty library_ids list THEN the JellyfinClient SHALL update the user policy with EnableAllFolders=False and EnabledFolders as an empty list
4. WHEN library access is successfully updated THEN the JellyfinClient SHALL return True
5. IF the user does not exist THEN the JellyfinClient SHALL return False
6. IF the library access update fails THEN the JellyfinClient SHALL raise a MediaClientError

### Requirement 7: Jellyfin Permission Mapping

**User Story:** As a system administrator, I want universal permissions to be translated to Jellyfin-specific settings, so that permission management is consistent across media servers.

#### Acceptance Criteria

1. THE JellyfinClient SHALL implement an update_permissions method that accepts a dictionary of universal permission settings
2. WHEN update_permissions is called THEN the JellyfinClient SHALL use the jellyfin-sdk to retrieve the current user and their policy
3. THE Permission_Mapping SHALL translate can_download to EnableContentDownloading in the Jellyfin UserPolicy
4. THE Permission_Mapping SHALL translate can_stream to EnableMediaPlayback in the Jellyfin UserPolicy
5. THE Permission_Mapping SHALL translate can_sync to EnableSyncTranscoding in the Jellyfin UserPolicy
6. THE Permission_Mapping SHALL translate can_transcode to EnableAudioPlaybackTranscoding and EnableVideoPlaybackTranscoding in the Jellyfin UserPolicy
7. WHEN update_permissions is called THEN the JellyfinClient SHALL use the jellyfin-sdk to update the user policy with the mapped fields
8. IF permission update fails THEN the JellyfinClient SHALL raise a MediaClientError

### Requirement 8: Jellyfin User Listing

**User Story:** As a system administrator, I want to list all users from a Jellyfin server, so that I can synchronize local records with the server state.

#### Acceptance Criteria

1. THE JellyfinClient SHALL implement a list_users method that retrieves all users from Jellyfin
2. WHEN list_users is called THEN the JellyfinClient SHALL use the jellyfin-sdk to retrieve all users from the server
3. WHEN users are retrieved THEN the JellyfinClient SHALL return a sequence of ExternalUser objects with external_user_id (Id), username (Name), and email (if available)
4. IF user listing fails THEN the JellyfinClient SHALL raise a MediaClientError

### Requirement 9: Invitation CRUD - Create

**User Story:** As a system administrator, I want to create invitations with configurable settings, so that I can control how users gain access to media servers.

#### Acceptance Criteria

1. WHEN a POST request is made to /api/v1/invitations THEN the System SHALL create a new invitation
2. WHEN an invitation is created without a code THEN the System SHALL generate a cryptographically secure 12-character code
3. THE generated code SHALL use uppercase letters and digits excluding ambiguous characters (0, O, I, L)
4. IF a code collision occurs THEN the System SHALL regenerate the code up to 3 times before failing
5. WHEN an invitation is created THEN the System SHALL validate that all server_ids reference existing enabled MediaServer records
6. WHEN an invitation is created with library_ids THEN the System SHALL validate that all libraries belong to the specified servers
7. WHEN an invitation is created THEN the System SHALL return the complete invitation details including the generated code
8. IF validation fails THEN the System SHALL return HTTP 400 with field-level error details

### Requirement 10: Invitation CRUD - Read

**User Story:** As a system administrator, I want to view invitation details and list all invitations, so that I can manage access to my media servers.

#### Acceptance Criteria

1. WHEN a GET request is made to /api/v1/invitations THEN the System SHALL return a paginated list of invitations
2. WHEN listing invitations THEN the System SHALL support filtering by enabled status, expiration status, and target server
3. WHEN listing invitations THEN the System SHALL support sorting by created_at, expires_at, and use_count
4. WHEN a GET request is made to /api/v1/invitations/{id} THEN the System SHALL return the complete invitation details
5. WHEN returning invitation details THEN the System SHALL include computed fields: is_active, remaining_uses, target_servers, and allowed_libraries
6. IF the invitation does not exist THEN the System SHALL return HTTP 404

### Requirement 11: Invitation CRUD - Update

**User Story:** As a system administrator, I want to modify existing invitations, so that I can adjust settings without creating new codes.

#### Acceptance Criteria

1. WHEN a PATCH request is made to /api/v1/invitations/{id} THEN the System SHALL update the specified fields
2. THE System SHALL allow updating: expires_at, max_uses, duration_days, enabled, server_ids, and library_ids
3. THE System SHALL NOT allow updating: code, use_count, created_at, or created_by
4. WHEN updating server_ids or library_ids THEN the System SHALL validate the references exist
5. IF the invitation does not exist THEN the System SHALL return HTTP 404
6. IF validation fails THEN the System SHALL return HTTP 400 with field-level error details

### Requirement 12: Invitation CRUD - Delete

**User Story:** As a system administrator, I want to delete invitations, so that I can remove codes that should no longer be used.

#### Acceptance Criteria

1. WHEN a DELETE request is made to /api/v1/invitations/{id} THEN the System SHALL delete the invitation
2. WHEN an invitation is deleted THEN the System SHALL return HTTP 204 No Content
3. IF the invitation does not exist THEN the System SHALL return HTTP 404
4. WHEN an invitation is deleted THEN the System SHALL NOT delete any users created from that invitation

### Requirement 13: Invitation Validation Endpoint

**User Story:** As a user, I want to validate an invitation code before attempting to redeem it, so that I know if the code is valid and what access it grants.

#### Acceptance Criteria

1. WHEN a GET request is made to /api/v1/invitations/validate/{code} THEN the System SHALL validate the invitation without redeeming it
2. WHEN validating THEN the System SHALL check: code exists, invitation is enabled, not expired, and use count below max_uses
3. WHEN the invitation is valid THEN the System SHALL return the target servers and allowed libraries
4. WHEN the invitation is invalid THEN the System SHALL return the specific failure reason (not_found, disabled, expired, max_uses_reached)
5. THE validation endpoint SHALL be publicly accessible without authentication
6. THE validation endpoint SHALL NOT increment the use count

### Requirement 14: Invitation Redemption Endpoint

**User Story:** As a user, I want to redeem an invitation code to create my media server account, so that I can access the media content.

#### Acceptance Criteria

1. WHEN a POST request is made to /api/v1/join/{code} THEN the System SHALL attempt to redeem the invitation
2. THE redemption request SHALL require username, password, and optionally email
3. WHEN redeeming THEN the System SHALL validate the invitation using the same rules as the validation endpoint
4. WHEN the invitation is valid THEN the System SHALL create a user on each target Jellyfin server via JellyfinClient.create_user
5. WHEN a user is created THEN the System SHALL apply library restrictions via JellyfinClient.set_library_access
6. WHEN a user is created THEN the System SHALL apply permissions via JellyfinClient.update_permissions
7. WHEN users are created THEN the System SHALL create a local Identity record linking all User records
8. WHEN redemption succeeds THEN the System SHALL increment the invitation use_count
9. IF the invitation has duration_days THEN the System SHALL set expires_at on the Identity and User records
10. THE redemption endpoint SHALL be publicly accessible without authentication

### Requirement 15: Redemption Transaction Handling

**User Story:** As a system administrator, I want redemption to be atomic, so that partial failures don't leave the system in an inconsistent state.

#### Acceptance Criteria

1. WHEN redemption fails on any target server THEN the System SHALL rollback all changes
2. IF a user is created on server A but fails on server B THEN the System SHALL delete the user from server A
3. WHEN rollback occurs THEN the System SHALL NOT increment the invitation use_count
4. WHEN rollback occurs THEN the System SHALL NOT create local Identity or User records
5. WHEN redemption fails THEN the System SHALL return HTTP 400 with details about which server failed
6. THE System SHALL log all rollback operations for debugging

### Requirement 16: User Listing API

**User Story:** As a system administrator, I want to list all users managed by Zondarr, so that I can view and manage access across all media servers.

#### Acceptance Criteria

1. WHEN a GET request is made to /api/v1/users THEN the System SHALL return a paginated list of users
2. WHEN listing users THEN the System SHALL support filtering by: media_server_id, invitation_id, enabled status, and expiration status
3. WHEN listing users THEN the System SHALL support sorting by: created_at, username, and expires_at
4. WHEN returning user details THEN the System SHALL include: identity info, media server info, invitation source, and current permissions
5. THE user listing endpoint SHALL require authentication
6. THE System SHALL use pagination with configurable page size (default 50, max 100)

### Requirement 17: User Detail API

**User Story:** As a system administrator, I want to view detailed information about a specific user, so that I can understand their access and permissions.

#### Acceptance Criteria

1. WHEN a GET request is made to /api/v1/users/{id} THEN the System SHALL return complete user details
2. WHEN returning user details THEN the System SHALL include the parent Identity with all linked Users
3. WHEN returning user details THEN the System SHALL include the source invitation if available
4. WHEN returning user details THEN the System SHALL include the media server details
5. IF the user does not exist THEN the System SHALL return HTTP 404

### Requirement 18: User Enable/Disable API

**User Story:** As a system administrator, I want to enable or disable users, so that I can control access without deleting accounts.

#### Acceptance Criteria

1. WHEN a POST request is made to /api/v1/users/{id}/enable THEN the System SHALL enable the user
2. WHEN a POST request is made to /api/v1/users/{id}/disable THEN the System SHALL disable the user
3. WHEN enabling or disabling THEN the System SHALL update both the local User record and the Jellyfin server via JellyfinClient.set_user_enabled
4. IF the Jellyfin update fails THEN the System SHALL NOT update the local record
5. WHEN the operation succeeds THEN the System SHALL return the updated user details
6. IF the user does not exist THEN the System SHALL return HTTP 404

### Requirement 19: User Deletion API

**User Story:** As a system administrator, I want to delete users, so that I can revoke access and clean up accounts.

#### Acceptance Criteria

1. WHEN a DELETE request is made to /api/v1/users/{id} THEN the System SHALL delete the user
2. WHEN deleting THEN the System SHALL delete the user from Jellyfin via JellyfinClient.delete_user
3. WHEN deleting THEN the System SHALL delete the local User record
4. IF the Jellyfin deletion fails THEN the System SHALL NOT delete the local record
5. WHEN the last User for an Identity is deleted THEN the System SHALL also delete the Identity
6. WHEN deletion succeeds THEN the System SHALL return HTTP 204 No Content
7. IF the user does not exist THEN the System SHALL return HTTP 404

### Requirement 20: Media Server Sync Endpoint

**User Story:** As a system administrator, I want to synchronize local user records with the actual state of a media server, so that I can detect and handle out-of-band changes.

#### Acceptance Criteria

1. WHEN a POST request is made to /api/v1/servers/{id}/sync THEN the System SHALL synchronize users with the media server
2. WHEN syncing THEN the System SHALL fetch all users from Jellyfin via JellyfinClient.list_users
3. WHEN syncing THEN the System SHALL identify users that exist on Jellyfin but not locally (orphaned)
4. WHEN syncing THEN the System SHALL identify users that exist locally but not on Jellyfin (stale)
5. WHEN syncing THEN the System SHALL return a report of orphaned and stale users
6. THE sync operation SHALL be idempotent - running it multiple times produces the same result
7. THE sync operation SHALL NOT automatically delete or create users - it only reports discrepancies
8. IF the media server is unreachable THEN the System SHALL return HTTP 503 with error details

### Requirement 21: Frontend Join Page

**User Story:** As a user, I want a friendly web page to redeem my invitation code, so that I can easily create my media server account.

#### Acceptance Criteria

1. WHEN a user visits /join/{code} THEN the Frontend SHALL display a form to create an account
2. WHEN the page loads THEN the Frontend SHALL validate the invitation code via the validation endpoint
3. IF the invitation is invalid THEN the Frontend SHALL display the specific error reason
4. IF the invitation is valid THEN the Frontend SHALL display the target servers and available libraries
5. WHEN the user submits the form THEN the Frontend SHALL call the redemption endpoint
6. WHEN redemption succeeds THEN the Frontend SHALL display a success message with next steps
7. WHEN redemption fails THEN the Frontend SHALL display the error message with guidance
8. THE form SHALL validate username (3-32 chars, lowercase, starts with letter) and password (min 8 chars) client-side

### Requirement 22: Frontend User Management

**User Story:** As a system administrator, I want a web interface to manage users, so that I can view and control access without using the API directly.

#### Acceptance Criteria

1. WHEN an admin visits /admin/users THEN the Frontend SHALL display a paginated table of users
2. THE user table SHALL display: username, media server, status, created date, and expiration date
3. THE user table SHALL support filtering by server, status, and expiration
4. THE user table SHALL support sorting by clicking column headers
5. WHEN an admin clicks a user row THEN the Frontend SHALL display a detail modal with full user information
6. THE detail modal SHALL provide actions: enable, disable, and delete
7. WHEN an action is performed THEN the Frontend SHALL display a toast notification with the result

### Requirement 23: API Authentication

**User Story:** As a system administrator, I want API endpoints to be protected, so that only authorized users can manage the system.

#### Acceptance Criteria

1. THE System SHALL require authentication for all /api/v1/* endpoints except /invitations/validate/{code} and /join/{code}
2. THE System SHALL support session-based authentication for the web frontend
3. THE System SHALL support API key authentication for programmatic access
4. WHEN authentication fails THEN the System SHALL return HTTP 401 Unauthorized
5. WHEN authorization fails THEN the System SHALL return HTTP 403 Forbidden
6. THE System SHALL log all authentication failures with client IP and attempted resource

### Requirement 24: Performance Requirements

**User Story:** As a system administrator, I want the system to perform well under load, so that it remains responsive with many users.

#### Acceptance Criteria

1. THE user listing endpoint SHALL return results within 500ms for up to 1000 users
2. THE System SHALL use database indexes on: users.media_server_id, users.identity_id, invitations.code, and invitations.enabled
3. THE System SHALL use pagination with a maximum page size of 100 to limit response sizes
4. THE JellyfinClient SHALL use connection pooling to reuse HTTP connections
5. THE System SHALL implement request timeouts of 30 seconds for Jellyfin API calls

### Requirement 25: Error Handling and Logging

**User Story:** As a system administrator, I want comprehensive error handling and logging, so that I can diagnose and resolve issues.

#### Acceptance Criteria

1. WHEN a Jellyfin API call fails THEN the System SHALL raise MediaClientError with the HTTP status and response body
2. WHEN an error occurs THEN the System SHALL log the error with correlation ID, operation, and context
3. THE System SHALL NOT expose internal error details (stack traces, file paths) in API responses
4. WHEN a validation error occurs THEN the System SHALL return field-level error details
5. THE System SHALL use structured logging with JSON format for production environments
