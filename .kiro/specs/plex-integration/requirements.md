# Requirements Document

## Introduction

This document specifies the requirements for Phase 3 of the Zondarr project: Plex media server integration. The Plex integration enables Zondarr to manage user access to Plex media servers through the existing invitation system. Unlike Jellyfin (which uses local user accounts), Plex operates through Plex.tv accounts and has two distinct user types: Friends (external Plex accounts) and Home Users (managed accounts within a Plex Home). The integration must handle Plex OAuth authentication, the Friend/Home user distinction, and Plex-specific library access management.

## Glossary

- **PlexClient**: The implementation of the MediaClient protocol for Plex servers
- **MediaClient_Protocol**: The abstract interface defining operations for media server clients
- **Plex_Friend**: An external Plex.tv account invited to share a server via inviteFriend()
- **Plex_Home_User**: A managed user account within the Plex Home created via createHomeUser()
- **PlexServer**: The python-plexapi class representing a connection to a Plex Media Server
- **MyPlexAccount**: The python-plexapi class for Plex.tv account operations (user management)
- **Plex_OAuth**: The OAuth 2.0 authentication flow used by Plex.tv for user authentication
- **Library_Section**: A Plex content library (movies, TV shows, music) identified by section ID
- **X_Plex_Token**: The authentication token used for Plex API requests
- **Capability**: An enum value indicating a supported operation (CREATE_USER, DELETE_USER, LIBRARY_ACCESS)
- **ExternalUser**: A msgspec Struct containing user information from the media server
- **LibraryInfo**: A msgspec Struct containing library information from the media server
- **MediaClientError**: The exception raised when media client operations fail
- **Redemption_Service**: The service orchestrating invitation redemption across media servers

## Requirements

### Requirement 1: PlexClient Connection Management

**User Story:** As a system administrator, I want the PlexClient to establish and manage connections to Plex servers, so that I can perform user management operations.

#### Acceptance Criteria

1. WHEN the PlexClient enters an async context, THE PlexClient SHALL initialize a PlexServer connection using asyncio.to_thread() to avoid blocking the event loop
2. WHEN the PlexClient exits an async context, THE PlexClient SHALL release the PlexServer connection and clean up resources
3. WHEN test_connection is called, THE PlexClient SHALL verify server connectivity and token validity by querying server information
4. IF the server is unreachable or the token is invalid, THEN THE PlexClient SHALL return False without raising an exception
5. WHEN test_connection succeeds, THE PlexClient SHALL return True

### Requirement 2: PlexClient Capability Declaration

**User Story:** As a developer, I want the PlexClient to declare its supported capabilities, so that the system can query available operations before attempting them.

#### Acceptance Criteria

1. THE PlexClient SHALL declare CREATE_USER capability
2. THE PlexClient SHALL declare DELETE_USER capability
3. THE PlexClient SHALL declare LIBRARY_ACCESS capability
4. THE PlexClient SHALL NOT declare ENABLE_DISABLE_USER capability since Plex does not support enabling/disabling users
5. THE PlexClient SHALL NOT declare DOWNLOAD_PERMISSION capability since Plex manages downloads differently

### Requirement 3: Library Retrieval

**User Story:** As a system administrator, I want to retrieve all library sections from a Plex server, so that I can configure library access for invitations.

#### Acceptance Criteria

1. WHEN get_libraries is called, THE PlexClient SHALL retrieve all library sections from the Plex server using asyncio.to_thread()
2. WHEN libraries are retrieved, THE PlexClient SHALL map each section to a LibraryInfo struct with external_id (section key), name, and library_type
3. IF the client is not initialized, THEN THE PlexClient SHALL raise MediaClientError with operation "get_libraries"
4. IF library retrieval fails, THEN THE PlexClient SHALL raise MediaClientError with the cause

### Requirement 4: Plex Friend User Creation

**User Story:** As a system administrator, I want to invite external Plex.tv accounts as Friends, so that existing Plex users can access my server.

#### Acceptance Criteria

1. WHEN create_user is called with an email address for a Friend invitation, THE PlexClient SHALL call MyPlexAccount.inviteFriend() with the user's email and server
2. WHEN a Friend invitation is sent, THE PlexClient SHALL return an ExternalUser with the email as external_user_id and username
3. IF the email is already a Friend, THEN THE PlexClient SHALL raise MediaClientError with error_code "USER_ALREADY_EXISTS"
4. IF the invitation fails, THEN THE PlexClient SHALL raise MediaClientError with the cause
5. WHEN creating a Friend, THE PlexClient SHALL use asyncio.to_thread() for all python-plexapi calls

### Requirement 5: Plex Home User Creation

**User Story:** As a system administrator, I want to create managed Home Users within my Plex Home, so that I can provide access without requiring external Plex accounts.

#### Acceptance Criteria

1. WHEN create_user is called for a Home User, THE PlexClient SHALL call MyPlexAccount.createHomeUser() with the username
2. WHEN a Home User is created, THE PlexClient SHALL return an ExternalUser with the Plex user ID as external_user_id
3. IF the username already exists in the Plex Home, THEN THE PlexClient SHALL raise MediaClientError with error_code "USERNAME_TAKEN"
4. IF Home User creation fails, THEN THE PlexClient SHALL raise MediaClientError with the cause
5. WHEN creating a Home User, THE PlexClient SHALL use asyncio.to_thread() for all python-plexapi calls

### Requirement 6: User Type Selection

**User Story:** As a system administrator, I want to specify whether to create a Friend or Home User, so that I can choose the appropriate user type for each invitation.

#### Acceptance Criteria

1. WHEN create_user is called, THE PlexClient SHALL accept a user_type parameter indicating "friend" or "home"
2. IF user_type is "friend" and email is provided, THEN THE PlexClient SHALL create a Friend via inviteFriend()
3. IF user_type is "home", THEN THE PlexClient SHALL create a Home User via createHomeUser()
4. IF user_type is "friend" but no email is provided, THEN THE PlexClient SHALL raise MediaClientError with error_code "EMAIL_REQUIRED"
5. THE PlexClient SHALL default to "friend" user_type when not specified

### Requirement 7: User Deletion

**User Story:** As a system administrator, I want to remove users from my Plex server, so that I can revoke access when needed.

#### Acceptance Criteria

1. WHEN delete_user is called for a Friend, THE PlexClient SHALL call MyPlexAccount.removeFriend() with the user identifier
2. WHEN delete_user is called for a Home User, THE PlexClient SHALL call the appropriate removal method for Home Users
3. IF the user is successfully deleted, THEN THE PlexClient SHALL return True
4. IF the user is not found, THEN THE PlexClient SHALL return False
5. IF deletion fails for other reasons, THEN THE PlexClient SHALL raise MediaClientError with the cause
6. WHEN deleting a user, THE PlexClient SHALL use asyncio.to_thread() for all python-plexapi calls

### Requirement 8: Library Access Management for Friends

**User Story:** As a system administrator, I want to configure which libraries a Friend can access, so that I can restrict content visibility.

#### Acceptance Criteria

1. WHEN set_library_access is called for a Friend, THE PlexClient SHALL call MyPlexAccount.updateFriend() with the specified library sections
2. WHEN library access is updated, THE PlexClient SHALL return True
3. IF the Friend is not found, THEN THE PlexClient SHALL return False
4. IF the library update fails, THEN THE PlexClient SHALL raise MediaClientError with the cause
5. WHEN an empty library list is provided, THE PlexClient SHALL revoke access to all libraries

### Requirement 9: Library Access Management for Home Users

**User Story:** As a system administrator, I want to configure which libraries a Home User can access, so that I can restrict content visibility for managed users.

#### Acceptance Criteria

1. WHEN set_library_access is called for a Home User, THE PlexClient SHALL configure section access for the Home User
2. WHEN library access is updated, THE PlexClient SHALL return True
3. IF the Home User is not found, THEN THE PlexClient SHALL return False
4. IF the library update fails, THEN THE PlexClient SHALL raise MediaClientError with the cause

### Requirement 10: User Enable/Disable Handling

**User Story:** As a developer, I want the PlexClient to handle enable/disable requests gracefully, so that the system behaves predictably even when the operation is unsupported.

#### Acceptance Criteria

1. WHEN set_user_enabled is called, THE PlexClient SHALL return False since Plex does not support enable/disable
2. THE PlexClient SHALL NOT raise an exception for set_user_enabled calls
3. THE PlexClient SHALL log a warning when set_user_enabled is called indicating the operation is unsupported

### Requirement 11: Permission Updates

**User Story:** As a system administrator, I want to update user permissions on Plex, so that I can control what actions users can perform.

#### Acceptance Criteria

1. WHEN update_permissions is called, THE PlexClient SHALL map universal permissions to Plex-specific settings where applicable
2. WHEN can_download is set, THE PlexClient SHALL configure the allowSync setting for the user
3. IF the user is not found, THEN THE PlexClient SHALL return False
4. IF permission update fails, THEN THE PlexClient SHALL raise MediaClientError with the cause
5. WHEN permissions are successfully updated, THE PlexClient SHALL return True

### Requirement 12: User Listing

**User Story:** As a system administrator, I want to list all users with access to my Plex server, so that I can synchronize local records with the server state.

#### Acceptance Criteria

1. WHEN list_users is called, THE PlexClient SHALL retrieve all Friends via MyPlexAccount.users()
2. WHEN list_users is called, THE PlexClient SHALL retrieve all Home Users via MyPlexAccount.users() with home filter
3. WHEN users are retrieved, THE PlexClient SHALL map each user to an ExternalUser struct
4. IF user listing fails, THEN THE PlexClient SHALL raise MediaClientError with the cause
5. WHEN listing users, THE PlexClient SHALL use asyncio.to_thread() for all python-plexapi calls

### Requirement 13: Plex OAuth Flow Initiation

**User Story:** As a user redeeming an invitation, I want to authenticate via Plex OAuth, so that I can link my existing Plex account to the server.

#### Acceptance Criteria

1. WHEN a Plex OAuth flow is initiated, THE System SHALL generate a Plex OAuth PIN via the Plex API
2. WHEN a PIN is generated, THE System SHALL return the PIN ID and authentication URL to the client
3. THE System SHALL store the PIN ID temporarily for callback verification
4. IF PIN generation fails, THEN THE System SHALL return an error response with details

### Requirement 14: Plex OAuth Callback Handling

**User Story:** As a user completing Plex OAuth, I want the system to retrieve my Plex account information, so that I can be invited to the server.

#### Acceptance Criteria

1. WHEN the OAuth callback is received, THE System SHALL verify the PIN ID matches a pending authentication
2. WHEN the PIN is verified, THE System SHALL retrieve the user's Plex auth token from the PIN
3. WHEN the auth token is retrieved, THE System SHALL fetch the user's Plex account email
4. IF the PIN is not found or expired, THEN THE System SHALL return an error response
5. IF the user's email cannot be retrieved, THEN THE System SHALL return an error response

### Requirement 15: Plex-Specific Redemption Flow

**User Story:** As a user redeeming a Plex invitation, I want the system to handle Plex-specific requirements, so that my account is properly configured.

#### Acceptance Criteria

1. WHEN redeeming an invitation for a Plex server with OAuth, THE Redemption_Service SHALL use the OAuth-retrieved email for Friend invitations
2. WHEN redeeming an invitation for a Plex Home User, THE Redemption_Service SHALL use the provided username
3. WHEN a Plex user is created, THE Redemption_Service SHALL apply library restrictions via set_library_access
4. WHEN a Plex user is created, THE Redemption_Service SHALL apply permissions via update_permissions
5. IF user creation fails on Plex, THEN THE Redemption_Service SHALL rollback any created users on other servers

### Requirement 16: Client Registration

**User Story:** As a developer, I want the PlexClient to be registered in the client registry, so that it can be instantiated for Plex server operations.

#### Acceptance Criteria

1. THE PlexClient SHALL be registered in the ClientRegistry for ServerType.PLEX
2. WHEN registry.create_client is called with ServerType.PLEX, THE Registry SHALL return a PlexClient instance
3. WHEN registry.get_capabilities is called with ServerType.PLEX, THE Registry SHALL return the PlexClient capabilities

### Requirement 17: Error Handling and Logging

**User Story:** As a system administrator, I want comprehensive error handling and logging, so that I can diagnose issues with Plex operations.

#### Acceptance Criteria

1. WHEN any PlexClient operation fails, THE PlexClient SHALL raise MediaClientError with operation name, server URL, and cause
2. WHEN any PlexClient operation is performed, THE PlexClient SHALL log the operation using structlog
3. WHEN an operation succeeds, THE PlexClient SHALL log at info level with relevant context
4. WHEN an operation fails, THE PlexClient SHALL log at warning or error level with the exception details
5. THE PlexClient SHALL NOT log sensitive information such as API tokens or passwords

### Requirement 18: Async Thread Safety

**User Story:** As a developer, I want all Plex operations to be non-blocking, so that the async event loop is not blocked by synchronous python-plexapi calls.

#### Acceptance Criteria

1. WHEN any python-plexapi method is called, THE PlexClient SHALL wrap it in asyncio.to_thread()
2. THE PlexClient SHALL NOT call any blocking python-plexapi methods directly in async methods
3. THE PlexClient SHALL maintain thread safety when accessing shared state
