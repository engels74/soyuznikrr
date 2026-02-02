# Requirements Document

## Introduction

This document defines the requirements for Phase 4: Frontend Foundation & Core UI of the Zondarr project. Zondarr is a unified invitation and user management system for media servers (Plex, Jellyfin). The backend is complete with Litestar + msgspec APIs. This phase builds the complete SvelteKit frontend with admin dashboard, invitation management, user management, server management, and public join flow.

## Glossary

- **Frontend**: The SvelteKit web application running on Bun runtime
- **Admin_Dashboard**: The authenticated area for server administrators to manage invitations, users, and servers
- **Join_Flow**: The public-facing pages where users redeem invitation codes
- **API_Client**: The type-safe HTTP client generated from OpenAPI spec using openapi-fetch
- **Invitation**: A code-based access grant with configurable permissions, expiration, and target servers
- **User**: A media server account created via invitation redemption
- **Identity**: A unified record grouping users across multiple media servers
- **Media_Server**: A configured Plex or Jellyfin server connection
- **Library**: A media collection (movies, TV shows, music) on a media server
- **Mode_Watcher**: The dark mode management component from mode-watcher package
- **Superforms**: The form validation and handling library for SvelteKit
- **Formsnap**: The shadcn-svelte integration layer for Superforms

## Requirements

### Requirement 1: Project Setup and Configuration

**User Story:** As a developer, I want a properly configured SvelteKit project with all required dependencies, so that I can build the frontend with consistent tooling and patterns.

#### Acceptance Criteria

1. THE Frontend SHALL be initialized as a SvelteKit project with Bun runtime and svelte-adapter-bun
2. THE Frontend SHALL use TypeScript in strict mode throughout all source files
3. THE Frontend SHALL configure UnoCSS with presetWind4, presetShadcn (neutral color, .dark selector), presetIcons, and presetAnimations
4. THE Frontend SHALL include shadcn-svelte components in $lib/components/ui/ directory
5. THE Frontend SHALL configure Superforms with Zod validation adapter
6. THE Frontend SHALL generate API types from the backend OpenAPI spec using openapi-typescript
7. THE Frontend SHALL configure openapi-fetch as the API client with proper base URL handling
8. THE Frontend SHALL include mode-watcher for dark mode support
9. THE Frontend SHALL include svelte-sonner for toast notifications
10. THE Frontend SHALL include @lucide/svelte for icons

### Requirement 2: API Client Integration

**User Story:** As a developer, I want a type-safe API client that matches the backend schemas, so that I can make API calls with full TypeScript support and catch errors at compile time.

#### Acceptance Criteria

1. THE API_Client SHALL be generated from the backend OpenAPI specification at /docs/openapi.json
2. THE API_Client SHALL provide typed request and response objects for all endpoints
3. THE API_Client SHALL handle authentication headers automatically for protected endpoints
4. THE API_Client SHALL handle API errors and transform them into user-friendly messages
5. WHEN an API request fails, THE API_Client SHALL return structured error information including error_code and detail
6. THE API_Client SHALL support pagination parameters (page, page_size) for list endpoints
7. THE API_Client SHALL support filter parameters for user and invitation list endpoints

### Requirement 3: Admin Layout and Navigation

**User Story:** As an administrator, I want a consistent dashboard layout with navigation, so that I can easily access all management features.

#### Acceptance Criteria

1. THE Admin_Dashboard SHALL display a sidebar navigation with links to Dashboard, Invitations, Users, and Servers sections
2. THE Admin_Dashboard SHALL display the current section title in a header area
3. THE Admin_Dashboard SHALL include a dark mode toggle in the header using Mode_Watcher
4. THE Admin_Dashboard SHALL persist the user's dark mode preference across sessions
5. WHEN the viewport is narrow, THE Admin_Dashboard SHALL collapse the sidebar into a mobile-friendly menu
6. THE Admin_Dashboard SHALL display toast notifications using svelte-sonner for success and error feedback
7. THE Admin_Dashboard SHALL use a "Control Room" aesthetic with dark-first design, high contrast accents, and status indicators

### Requirement 4: Invitation List View

**User Story:** As an administrator, I want to view all invitations in a paginated list, so that I can monitor invitation usage and status.

#### Acceptance Criteria

1. WHEN the administrator navigates to the Invitations section, THE Frontend SHALL display a paginated list of invitations
2. THE Invitation list SHALL display code, use_count, max_uses, expires_at, enabled status, and is_active computed status for each invitation
3. THE Invitation list SHALL support filtering by enabled status and expired status
4. THE Invitation list SHALL support sorting by created_at, expires_at, and use_count
5. THE Invitation list SHALL display visual status badges: green for active, amber for pending/limited, red for disabled/expired
6. WHEN an invitation has remaining_uses, THE Frontend SHALL display the remaining count
7. THE Invitation list SHALL support pagination with configurable page size (default 50, max 100)

### Requirement 5: Invitation Creation

**User Story:** As an administrator, I want to create new invitations with configurable settings, so that I can grant access to users with appropriate restrictions.

#### Acceptance Criteria

1. WHEN the administrator clicks "Create Invitation", THE Frontend SHALL display a creation form
2. THE creation form SHALL allow selecting one or more target media servers
3. THE creation form SHALL allow setting an optional custom code (auto-generated if not provided)
4. THE creation form SHALL allow setting an optional expiration date/time
5. THE creation form SHALL allow setting an optional maximum number of uses
6. THE creation form SHALL allow setting an optional duration in days for user access
7. THE creation form SHALL allow selecting specific libraries to grant access to (optional)
8. WHEN the form is submitted with valid data, THE Frontend SHALL create the invitation and display a success toast
9. IF the form submission fails, THEN THE Frontend SHALL display validation errors inline and show an error toast
10. THE creation form SHALL use Superforms with Zod validation for client-side validation

### Requirement 6: Invitation Detail and Edit

**User Story:** As an administrator, I want to view and edit invitation details, so that I can modify settings or review usage.

#### Acceptance Criteria

1. WHEN the administrator clicks on an invitation, THE Frontend SHALL display the invitation detail view
2. THE detail view SHALL display all invitation fields including target_servers and allowed_libraries
3. THE detail view SHALL allow editing mutable fields: expires_at, max_uses, duration_days, enabled, server_ids, library_ids
4. THE detail view SHALL NOT allow editing immutable fields: code, use_count, created_at, created_by
5. WHEN the administrator saves changes, THE Frontend SHALL update the invitation and display a success toast
6. THE detail view SHALL include a delete button with confirmation dialog
7. WHEN the administrator confirms deletion, THE Frontend SHALL delete the invitation and navigate back to the list

### Requirement 7: User List View

**User Story:** As an administrator, I want to view all users across all servers, so that I can monitor user accounts and their status.

#### Acceptance Criteria

1. WHEN the administrator navigates to the Users section, THE Frontend SHALL display a paginated list of users
2. THE User list SHALL display username, media_server name, enabled status, expires_at, and created_at for each user
3. THE User list SHALL support filtering by media_server_id, invitation_id, enabled status, and expired status
4. THE User list SHALL support sorting by created_at, username, and expires_at
5. THE User list SHALL display visual status badges: green for enabled, red for disabled, amber for expiring soon
6. THE User list SHALL support pagination with configurable page size (default 50, max 100)
7. THE User list SHALL display the source invitation code if available

### Requirement 8: User Detail and Management

**User Story:** As an administrator, I want to view user details and manage their account status, so that I can enable, disable, or remove users as needed.

#### Acceptance Criteria

1. WHEN the administrator clicks on a user, THE Frontend SHALL display the user detail view
2. THE detail view SHALL display user information including identity, media_server, and source invitation
3. THE detail view SHALL display the parent identity with all linked users across servers
4. THE detail view SHALL include an Enable button for disabled users
5. THE detail view SHALL include a Disable button for enabled users
6. WHEN the administrator clicks Enable, THE Frontend SHALL call the enable endpoint and update the UI
7. WHEN the administrator clicks Disable, THE Frontend SHALL call the disable endpoint and update the UI
8. THE detail view SHALL include a Delete button with confirmation dialog
9. WHEN the administrator confirms deletion, THE Frontend SHALL delete the user from both local database and media server

### Requirement 9: Server Management

**User Story:** As an administrator, I want to view and sync media servers, so that I can ensure user records are consistent with the actual server state.

#### Acceptance Criteria

1. WHEN the administrator navigates to the Servers section, THE Frontend SHALL display a list of configured media servers
2. THE Server list SHALL display name, server_type (Plex/Jellyfin), url, enabled status, and library count for each server
3. WHEN the administrator clicks on a server, THE Frontend SHALL display server details including libraries
4. THE detail view SHALL include a Sync button to synchronize users with the media server
5. WHEN the administrator clicks Sync, THE Frontend SHALL call the sync endpoint and display the results
6. THE sync results SHALL display orphaned_users (on server but not local), stale_users (local but not on server), and matched_users count
7. IF the sync fails due to server unreachability, THEN THE Frontend SHALL display an error message with the failure reason

### Requirement 10: Public Join Flow - Code Validation

**User Story:** As a user with an invitation code, I want to validate my code and see what access I'll receive, so that I can proceed with account creation.

#### Acceptance Criteria

1. WHEN a user navigates to /join/{code}, THE Join_Flow SHALL validate the invitation code via the API
2. IF the code is valid, THEN THE Join_Flow SHALL display the target servers and allowed libraries
3. IF the code is invalid, THEN THE Join_Flow SHALL display the failure reason (not_found, disabled, expired, max_uses_reached)
4. THE validation page SHALL display the duration_days if set, indicating how long access will last
5. THE validation page SHALL provide a "Continue" button to proceed to registration

### Requirement 11: Public Join Flow - Jellyfin Registration

**User Story:** As a user joining a Jellyfin server, I want to create my account with a username and password, so that I can access the media server.

#### Acceptance Criteria

1. WHEN the invitation targets a Jellyfin server, THE Join_Flow SHALL display a registration form
2. THE registration form SHALL require username (3-32 chars, lowercase, starts with letter)
3. THE registration form SHALL require password (minimum 8 characters)
4. THE registration form SHALL allow optional email address
5. THE registration form SHALL use Superforms with Zod validation matching backend constraints
6. WHEN the form is submitted, THE Join_Flow SHALL call the redeem endpoint
7. IF redemption succeeds, THEN THE Join_Flow SHALL display a success page with server access instructions
8. IF redemption fails with USERNAME_TAKEN, THEN THE Join_Flow SHALL display an error asking for a different username
9. IF redemption fails with SERVER_ERROR, THEN THE Join_Flow SHALL display the failed_server name and error message

### Requirement 12: Public Join Flow - Plex OAuth

**User Story:** As a user joining a Plex server, I want to authenticate with my Plex account, so that I can be added to the server.

#### Acceptance Criteria

1. WHEN the invitation targets a Plex server, THE Join_Flow SHALL display a "Sign in with Plex" button
2. WHEN the user clicks the button, THE Join_Flow SHALL create an OAuth PIN via the API
3. THE Join_Flow SHALL display the PIN code and open the Plex auth URL in a new window/tab
4. THE Join_Flow SHALL poll the PIN status endpoint until authenticated or expired
5. WHEN the PIN is authenticated, THE Join_Flow SHALL display the user's Plex email and proceed to redemption
6. IF the PIN expires, THEN THE Join_Flow SHALL display an error and allow retry
7. WHEN redemption completes, THE Join_Flow SHALL display a success page with server access instructions

### Requirement 13: Design System and Aesthetics

**User Story:** As a user, I want a visually distinctive and professional interface, so that the application feels polished and trustworthy.

#### Acceptance Criteria

1. THE Frontend SHALL use a "Control Room" aesthetic with dark-first design
2. THE Frontend SHALL use high contrast accent colors for interactive elements
3. THE Frontend SHALL use monospace or technical display fonts for data presentation (codes, IDs, timestamps)
4. THE Frontend SHALL use status color coding: green (active/enabled), amber (pending/limited), red (disabled/expired)
5. THE Frontend SHALL use card-based layouts for invitations, users, and servers
6. THE Frontend SHALL include subtle animations for state changes and loading states
7. THE Frontend SHALL NOT use generic AI aesthetics (Inter font, purple gradients, cookie-cutter layouts)
8. THE Frontend SHALL maintain WCAG 2.1 AA accessibility compliance

### Requirement 14: Error Handling and Loading States

**User Story:** As a user, I want clear feedback during operations and when errors occur, so that I understand what's happening and can take appropriate action.

#### Acceptance Criteria

1. WHEN data is loading, THE Frontend SHALL display skeleton loaders or loading spinners
2. WHEN an API request fails, THE Frontend SHALL display a toast notification with the error message
3. WHEN a form submission fails, THE Frontend SHALL display inline validation errors
4. WHEN a destructive action is requested, THE Frontend SHALL display a confirmation dialog
5. THE Frontend SHALL handle network errors gracefully with retry options where appropriate
6. THE Frontend SHALL display empty states with helpful messages when lists have no items
