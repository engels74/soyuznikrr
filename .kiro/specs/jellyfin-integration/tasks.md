# Implementation Plan: Phase 2 - Jellyfin Integration

## Overview

This implementation plan breaks down the Jellyfin Integration feature into discrete coding tasks. Each task builds on previous work and includes property-based tests where applicable. The implementation follows the established patterns from Phase 1 and adheres to the backend development guidelines.

## Tasks

- [x] 1. Implement JellyfinClient core functionality
  - [x] 1.1 Implement connection management and test_connection
    - Initialize jellyfin.api in __aenter__, cleanup in __aexit__
    - Implement test_connection using jellyfin-sdk system.info
    - Handle connection errors gracefully (return False, don't raise)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
    - [x] 1.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 1.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 1.2 Implement get_libraries method
    - Retrieve virtual folders via jellyfin-sdk
    - Map Jellyfin response to LibraryInfo structs
    - Handle CollectionType mapping (movies, tvshows, music, etc.)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
    - [x] 1.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 1.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 1.3 Write property test for library mapping
    - **Property 2: Library Mapping Preserves Fields**
    - **Validates: Requirements 2.2, 2.4**
    - [x] 1.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 1.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [x] 2. Implement JellyfinClient user management
  - [x] 2.1 Implement create_user method
    - Create user via jellyfin-sdk users.create
    - Set password via users.update_password
    - Return ExternalUser with id, username, email
    - Handle USERNAME_TAKEN error case
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
    - [x] 2.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 2.2 Implement delete_user method
    - Delete user via jellyfin-sdk users.delete
    - Return True on success, False if not found
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
    - [x] 2.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 2.3 Implement set_user_enabled method
    - Get current user and policy
    - Update IsDisabled flag based on enabled parameter
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
    - [x] 2.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 2.4 Write property test for enable/disable mapping
    - **Property 4: Enable/Disable Maps to IsDisabled Correctly**
    - **Validates: Requirements 5.2, 5.3**
    - [x] 2.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [x] 3. Implement JellyfinClient library access and permissions
  - [x] 3.1 Implement set_library_access method
    - Get current user and policy
    - Set EnableAllFolders=False and EnabledFolders to library IDs
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
    - [x] 3.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 3.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 3.2 Write property test for library access configuration
    - **Property 5: Library Access Configuration**
    - **Validates: Requirements 6.2, 6.3**
    - [x] 3.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 3.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 3.3 Implement update_permissions method
    - Map universal permissions to Jellyfin policy fields
    - can_download → EnableContentDownloading
    - can_stream → EnableMediaPlayback
    - can_sync → EnableSyncTranscoding
    - can_transcode → EnableAudioPlaybackTranscoding, EnableVideoPlaybackTranscoding
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_
    - [x] 3.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 3.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 3.4 Write property test for permission mapping
    - **Property 6: Permission Mapping Correctness**
    - **Validates: Requirements 7.3, 7.4, 7.5, 7.6**
    - [x] 3.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 3.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 3.5 Implement list_users method
    - Retrieve all users via jellyfin-sdk users.all
    - Map to ExternalUser structs
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
    - [x] 3.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 3.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 3.6 Write property test for user listing
    - **Property 7: User Listing Returns Complete Objects**
    - **Validates: Requirements 8.3**
    - [x] 3.6.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 3.6.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [x] 4. Checkpoint - JellyfinClient complete
  - Ensure all JellyfinClient tests pass, ask the user if questions arise.

- [x] 5. Add API schemas for invitations
  - [x] 5.1 Add invitation request/response schemas to api/schemas.py
    - CreateInvitationRequest with server_ids, code, expires_at, max_uses, duration_days, library_ids, permissions
    - UpdateInvitationRequest with mutable fields only
    - InvitationResponse and InvitationDetailResponse with computed fields
    - InvitationListResponse with pagination
    - _Requirements: 9.1, 9.7, 10.1, 10.5, 11.1, 11.2_
    - [x] 5.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 5.2 Add validation/redemption schemas
    - InvitationValidationResponse with valid, failure_reason, servers, libraries
    - RedeemInvitationRequest with username, password, email
    - RedemptionResponse and RedemptionErrorResponse
    - _Requirements: 13.1, 13.3, 14.1, 14.2_
    - [x] 5.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [x] 6. Extend InvitationService with CRUD operations
  - [x] 6.1 Add code generation with collision handling
    - Generate 12-char codes using valid alphabet (no 0, O, I, L)
    - Retry up to 3 times on collision
    - _Requirements: 9.2, 9.3, 9.4_
    - [x] 6.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 6.2 Write property test for code generation
    - **Property 8: Generated Codes Are Valid**
    - **Validates: Requirements 9.2, 9.3**
    - [x] 6.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 6.3 Add server and library validation on create
    - Validate all server_ids reference existing enabled MediaServer records
    - Validate all library_ids belong to specified servers
    - _Requirements: 9.5, 9.6_
    - [x] 6.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 6.4 Write property test for server/library validation
    - **Property 9: Server and Library Validation on Create**
    - **Validates: Requirements 9.5, 9.6**
    - [x] 6.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 6.5 Add computed fields calculation
    - is_active: enabled AND not expired AND use_count < max_uses
    - remaining_uses: max_uses - use_count if max_uses set
    - _Requirements: 10.5_
    - [x] 6.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 6.6 Write property test for computed fields
    - **Property 10: Invitation Computed Fields**
    - **Validates: Requirements 10.5**
    - [x] 6.6.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.6.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 6.7 Add update method with immutable field protection
    - Allow updating: expires_at, max_uses, duration_days, enabled, server_ids, library_ids
    - Ignore/reject: code, use_count, created_at, created_by
    - _Requirements: 11.2, 11.3, 11.4_
    - [x] 6.7.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.7.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 6.8 Write property test for immutable fields
    - **Property 11: Immutable Fields Cannot Be Updated**
    - **Validates: Requirements 11.3**
    - [x] 6.8.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.8.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 6.9 Add delete method preserving users
    - Delete invitation without cascading to User records
    - _Requirements: 12.1, 12.2, 12.3, 12.4_
    - [x] 6.9.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.9.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 6.10 Write property test for user preservation on delete
    - **Property 12: Invitation Deletion Preserves Users**
    - **Validates: Requirements 12.4**
    - [x] 6.10.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.10.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [x] 7. Extend InvitationRepository with pagination and filtering
  - [x] 7.1 Add list_paginated method
    - Support filtering by enabled, expired status
    - Support sorting by created_at, expires_at, use_count
    - Return (items, total) tuple for pagination
    - _Requirements: 10.1, 10.2, 10.3_
    - [x] 7.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 7.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [x] 8. Checkpoint - Invitation CRUD complete
  - Ensure all invitation service tests pass, ask the user if questions arise.

- [ ] 9. Implement InvitationController
  - [ ] 9.1 Create InvitationController with CRUD endpoints
    - POST /api/v1/invitations - create invitation
    - GET /api/v1/invitations - list with pagination
    - GET /api/v1/invitations/{id} - get details
    - PATCH /api/v1/invitations/{id} - update
    - DELETE /api/v1/invitations/{id} - delete
    - _Requirements: 9.1, 10.1, 10.4, 11.1, 12.1_
    - [ ] 9.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 9.2 Add validation endpoint (public)
    - GET /api/v1/invitations/validate/{code}
    - Check all validation conditions
    - Return specific failure reason
    - Do not increment use_count
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_
    - [ ] 9.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 9.3 Write property test for validation
    - **Property 13: Validation Checks All Conditions**
    - **Property 14: Validation Does Not Increment Use Count**
    - **Validates: Requirements 13.2, 13.4, 13.6**
    - [ ] 9.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 10. Implement RedemptionService
  - [ ] 10.1 Create RedemptionService with redeem method
    - Validate invitation
    - Create users on each target server via JellyfinClient
    - Apply library restrictions and permissions
    - Create local Identity and User records
    - Increment use_count on success
    - _Requirements: 14.3, 14.4, 14.5, 14.6, 14.7, 14.8_
    - [ ] 10.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 10.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 10.2 Write property test for user creation on all servers
    - **Property 15: Redemption Creates Users on All Target Servers**
    - **Validates: Requirements 14.4, 14.7**
    - [ ] 10.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 10.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 10.3 Write property test for use_count increment
    - **Property 16: Redemption Increments Use Count**
    - **Validates: Requirements 14.8**
    - [ ] 10.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 10.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 10.4 Add expiration calculation from duration_days
    - Set expires_at on Identity and Users if duration_days set
    - _Requirements: 14.9_
    - [ ] 10.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 10.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 10.5 Write property test for duration_days expiration
    - **Property 17: Duration Days Sets Expiration**
    - **Validates: Requirements 14.9**
    - [ ] 10.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 10.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 10.6 Implement rollback on failure
    - Track created users during redemption
    - Delete created users if any server fails
    - Do not increment use_count on failure
    - Do not create local records on failure
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
    - [ ] 10.6.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 10.6.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 10.7 Write property test for rollback behavior
    - **Property 18: Rollback on Failure**
    - **Validates: Requirements 15.1, 15.2, 15.3, 15.4**
    - [ ] 10.7.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 10.7.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 11. Implement JoinController
  - [ ] 11.1 Create JoinController with redemption endpoint
    - POST /api/v1/join/{code} - redeem invitation
    - Public endpoint (no auth required)
    - Return RedemptionResponse on success
    - Return RedemptionErrorResponse on failure
    - _Requirements: 14.1, 14.2, 14.10, 15.5_
    - [ ] 11.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 11.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 12. Checkpoint - Redemption flow complete
  - Ensure all redemption tests pass, ask the user if questions arise.

- [ ] 13. Add User management schemas and repository
  - [ ] 13.1 Add user schemas to api/schemas.py
    - UserDetailResponse with relationships
    - UserListResponse with pagination
    - UserListFilters for query parameters
    - _Requirements: 16.1, 16.4, 17.1_
    - [ ] 13.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 13.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 13.2 Create UserRepository
    - get_by_server method for filtering by media_server_id
    - list_paginated with filtering and sorting
    - Add invitation_id foreign key to User model
    - _Requirements: 16.2, 16.3_
    - [ ] 13.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 13.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 13.3 Create IdentityRepository
    - get_with_users method for eager loading
    - delete_if_no_users method for cascade logic
    - _Requirements: 17.2, 19.5_
    - [ ] 13.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 13.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 14. Implement UserService
  - [ ] 14.1 Create UserService with CRUD operations
    - create_identity_with_users for redemption
    - get_user_detail with relationships
    - _Requirements: 14.7, 17.1, 17.2, 17.3, 17.4_
    - [ ] 14.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 14.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 14.2 Add enable/disable with atomicity
    - Update Jellyfin first via JellyfinClient
    - Only update local record if Jellyfin succeeds
    - _Requirements: 18.1, 18.2, 18.3, 18.4_
    - [ ] 14.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 14.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 14.3 Write property test for enable/disable atomicity
    - **Property 19: Enable/Disable Atomicity**
    - **Validates: Requirements 18.3, 18.4**
    - [ ] 14.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 14.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 14.4 Add delete with atomicity and cascade
    - Delete from Jellyfin first
    - Only delete local record if Jellyfin succeeds
    - Delete Identity if last User deleted
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6_
    - [ ] 14.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 14.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 14.5 Write property test for deletion atomicity
    - **Property 20: User Deletion Atomicity**
    - **Validates: Requirements 19.3, 19.4**
    - [ ] 14.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 14.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 14.6 Write property test for Identity cascade
    - **Property 21: Last User Deletion Cascades to Identity**
    - **Validates: Requirements 19.5**
    - [ ] 14.6.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 14.6.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 15. Implement UserController
  - [ ] 15.1 Create UserController with list and detail endpoints
    - GET /api/v1/users - list with pagination, filtering, sorting
    - GET /api/v1/users/{id} - get details with relationships
    - Enforce page_size max of 100
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 17.1, 17.2, 17.3, 17.4, 17.5_
    - [ ] 15.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 15.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 15.2 Write property test for page size cap
    - **Property 25: Page Size Is Capped**
    - **Validates: Requirements 16.6**
    - [ ] 15.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 15.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 15.3 Add enable/disable endpoints
    - POST /api/v1/users/{id}/enable
    - POST /api/v1/users/{id}/disable
    - _Requirements: 18.1, 18.2, 18.5, 18.6_
    - [ ] 15.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 15.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 15.4 Add delete endpoint
    - DELETE /api/v1/users/{id}
    - Return 204 on success, 404 if not found
    - _Requirements: 19.1, 19.6, 19.7_
    - [ ] 15.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 15.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 16. Checkpoint - User management complete
  - Ensure all user management tests pass, ask the user if questions arise.

- [ ] 17. Implement SyncService
  - [ ] 17.1 Create SyncService with sync_server method
    - Fetch users from Jellyfin via list_users
    - Compare with local User records
    - Identify orphaned (on server, not local) and stale (local, not on server)
    - Return SyncResult with counts
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_
    - [ ] 17.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 17.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 17.2 Write property test for discrepancy identification
    - **Property 22: Sync Identifies Discrepancies Correctly**
    - **Validates: Requirements 20.3, 20.4**
    - [ ] 17.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 17.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 17.3 Write property test for idempotency
    - **Property 23: Sync Is Idempotent**
    - **Validates: Requirements 20.6**
    - [ ] 17.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 17.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 17.4 Write property test for no modification
    - **Property 24: Sync Does Not Modify Users**
    - **Validates: Requirements 20.7**
    - [ ] 17.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 17.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 18. Implement ServerController sync endpoint
  - [ ] 18.1 Add sync endpoint to ServerController
    - POST /api/v1/servers/{id}/sync
    - Accept SyncRequest with dry_run flag
    - Return SyncResult
    - Return 503 if server unreachable
    - _Requirements: 20.1, 20.5, 20.8_
    - [ ] 18.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 18.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 19. Register controllers in app.py
  - [ ] 19.1 Update app.py to register new controllers
    - Add InvitationController
    - Add JoinController
    - Add UserController
    - Update ServerController with sync endpoint
    - _Requirements: All API requirements_
    - [ ] 19.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 19.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 20. Final checkpoint - Backend complete
  - Ensure all backend tests pass, ask the user if questions arise.

- [ ] 21. Implement frontend join page
  - [ ] 21.1 Create /join/[code] route structure
    - Create routes/(public)/join/[code]/+page.svelte
    - Create routes/(public)/join/[code]/+page.server.ts
    - _Requirements: 21.1_
    - [ ] 21.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 21.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 21.2 Implement server-side validation on load
    - Call validation endpoint in +page.server.ts load function
    - Pass validation result to page
    - _Requirements: 21.2, 21.3, 21.4_
    - [ ] 21.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 21.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 21.3 Implement join form with Superforms
    - Create form with username, password, email fields
    - Add Zod validation schema matching API constraints
    - Use Formsnap for accessible form controls
    - _Requirements: 21.5, 21.8_
    - [ ] 21.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 21.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 21.4 Implement form submission and feedback
    - Call redemption endpoint on submit
    - Display success page on success
    - Display error toast on failure
    - _Requirements: 21.6, 21.7_
    - [ ] 21.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 21.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 22. Implement frontend user management
  - [ ] 22.1 Create /admin/users route structure
    - Create routes/(admin)/users/+page.svelte
    - Create routes/(admin)/users/+page.server.ts
    - _Requirements: 22.1_
    - [ ] 22.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 22.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 22.2 Implement user list table
    - Use shadcn-svelte Table component
    - Display username, server, status, created, expires columns
    - _Requirements: 22.2_
    - [ ] 22.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 22.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 22.3 Add filtering and sorting controls
    - Add filter dropdowns for server, status, expiration
    - Add sortable column headers
    - _Requirements: 22.3, 22.4_
    - [ ] 22.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 22.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 22.4 Add pagination controls
    - Implement page navigation
    - Display total count and current page
    - _Requirements: 22.4_
    - [ ] 22.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 22.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 22.5 Implement user detail modal
    - Show full user information on row click
    - Include enable/disable/delete actions
    - Display toast notifications for action results
    - _Requirements: 22.5, 22.6, 22.7_
    - [ ] 22.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 22.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 23. Final checkpoint - All tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks including property-based tests are required for comprehensive coverage
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation follows the repository → service → controller layering pattern
- All async database operations use SQLAlchemy 2.0 patterns with selectinload for collections

## Verification Guidelines

### General Code Quality Verification (*.1 subtasks)

Verify the task implementation adheres to all coding guidelines specified in `.augment/rules/backend-dev-pro.md`.

### Type Safety Verification (*.2 subtasks)

Run `uvx basedpyright@latest` in the project directory to perform static type checking on the Python codebase. After the command completes, analyze all reported errors and warnings, then systematically fix each issue by:

1. Running the type checker and capturing the full output
2. Categorizing the errors and warnings by type and severity
3. Creating a task list to track progress on fixing each category of issues
4. For each error/warning:
   - Always rely on the "Type Safety Guidelines" described below
   - Locate the relevant code using the file path and line number from the error message
   - Understand the root cause by examining the code context
   - Implement the appropriate fix (type annotations, imports, logic corrections, etc.)
   - Verify the fix resolves the specific error
5. Re-run `uvx basedpyright@latest` after fixes to confirm all issues are resolved
6. Ensure all fixes maintain code functionality and follow existing code patterns in the repository

Focus on fixing actual errors first, then warnings. Check for any downstream changes needed when fixing type-related issues (such as updating function signatures, return types, or parameter types that may affect callers).

#### Type Safety Guidelines

##### Core rules
- Use uvx basedpyright everywhere:
  - Local checks: `uvx basedpyright@latest`
  - CI: `uvx basedpyright@latest` (must pass with 0 errors, 0 warnings)
- Absolutely 0 errors and 0 warnings across all code, including tests. No exceptions.
- Fix issues rather than ignoring them. Ignores are only for unavoidable third‑party gaps.
- Never use global ignores or looser project-level rules to hide issues.
- Only install type stubs when basedpyright reports missing stubs (e.g., `uv add -D types-requests`).

##### Ignore policy (strict)
- Per-line, rule-scoped ignores only: `# pyright: ignore[rule-code]`
- Forbid bare `# type: ignore` (enforced via config).
- Add a brief reason only when not obvious (e.g., "third‑party lib has no stubs").
- Remove ignores as soon as the underlying issue is resolved.

Examples:
```python
# Good (explicit + scoped)
data = third_party_func()  # pyright: ignore[reportUnknownVariableType]  # lib lacks stubs

# Bad (blanket suppression)
data = third_party_func()  # type: ignore
```

##### Modern typing conventions (3.14+)

###### PEP 695 generics and type aliases
- Use inline `class Foo[T]:` and `def foo[T]:` syntax for all generic types instead of explicit `TypeVar` declarations.
- Use the `type` statement for type aliases: `type ListOrSet[T] = list[T] | set[T]`
- No need to import `TypeVar` or `Generic` for simple cases—variance is auto-inferred.

```python
# ❌ Legacy (pre-3.12)
from typing import TypeVar, Generic
_T_co = TypeVar("_T_co", covariant=True, bound=str)
class ClassA(Generic[_T_co]):
    def method1(self) -> _T_co: ...

# ✅ Modern (3.12+)
class ClassA[T: str]:  # Variance auto-inferred, bound inline
    def method1(self) -> T: ...

# Type aliases
type ListOrSet[T] = list[T] | set[T]
```

###### Deferred annotation evaluation (3.14)
- Remove string quotes from forward references—Python 3.14's deferred evaluation handles them automatically.
- Remove `from __future__ import annotations` imports (now deprecated, emits warning).
- Use `annotationlib.get_annotations()` for runtime inspection when needed.

```python
# Python 3.14: No quotes needed for forward references
class Node:
    def __init__(self, value: int, next: Node | None = None):  # Works!
        self.value = value
        self.next = next
```

###### TypeIs for intuitive type narrowing
- Prefer `TypeIs` over `TypeGuard` for type narrowing functions—it narrows both `if` and `else` branches.
- Reserve `TypeGuard` only when narrowing to a non-subtype (e.g., invariant containers).

```python
from typing import TypeIs, TypeGuard

# ✅ Preferred: TypeIs narrows both branches
def is_str(val: object) -> TypeIs[str]:
    return isinstance(val, str)

def process(val: int | str) -> None:
    if is_str(val):
        print(val.upper())  # val is str
    else:
        print(val + 1)      # val is int ← TypeIs enables this!

# Use TypeGuard only for non-subtype narrowing
def is_str_list(val: list[object]) -> TypeGuard[list[str]]:
    return all(isinstance(x, str) for x in val)
```

###### Self type for method chaining
- Use `Self` for methods returning the instance's type, especially in method chaining and classmethods.

```python
from typing import Self

class Shape:
    def set_scale(self, scale: float) -> Self:
        self.scale = scale
        return self

    @classmethod
    def create(cls) -> Self:
        return cls()
```

###### @override decorator
- Decorate all intentional method overrides with `@override` to catch inheritance bugs.

```python
from typing import override

class Child(Parent):
    @override
    def foo(self, x: int) -> int:  # ✅ Verified override
        return x + 1
```

###### Built-in generics and union syntax
- Use built-in generics: `list[str]`, `dict[str, int]`, `set[T]`
- Use `|` union syntax: `str | None`, `int | str`
- Use abstract types from `collections.abc` for APIs: `Iterable[str]`, `Mapping[str, int]`

###### TypedDict with modern features
- Use `Required`/`NotRequired` for mixed totality.
- Use `ReadOnly` for immutable keys (3.13+).
- Use `closed=True` for strict TypedDicts that reject extra keys (3.14+).

```python
from typing import TypedDict, Required, NotRequired, ReadOnly

class Movie(TypedDict):
    title: Required[str]
    year: NotRequired[int]
    rating: ReadOnly[float]

# Closed TypedDict (3.14+) - no extra keys allowed
class StrictConfig(TypedDict, closed=True):
    host: str
    port: int
```

###### Protocol for structural subtyping
- Use `Protocol` for interfaces; prefer structural subtyping over ABCs for flexibility.

```python
from typing import Protocol

class SupportsClose(Protocol):
    def close(self) -> None: ...

def close_all(items: Iterable[SupportsClose]) -> None:
    for item in items:
        item.close()
```

###### Additional conventions
- Prefer `Final`, `Literal`, `Annotated` where they add clarity or constraints.
- Use `typing.assert_never` for exhaustiveness in match/if-else fallthroughs.
- Avoid walrus operator (`:=`), `yield`, and `await` in annotations (disallowed in 3.14).

##### Public API quality bar
- Public functions, methods, and module-level constants must be fully typed (params and return).
- Avoid `Any` at API boundaries. If unavoidable at the edge, isolate with a small, well-documented adapter and keep `Any` from leaking inward.
- Don't use `cast(...)` to silence type errors except in tiny, audited boundary helpers.
- Prefer small, composable `Protocol`s over deep inheritance to express behavior.

##### Tests are first-class
- Tests must meet the same 0-warnings standard.
- Avoid untyped fixtures; annotate fixture return types and parametrized values.
- For factories/builders, provide precise types—don't default to `dict[str, Any]` unless the data truly is open-ended.

##### basedpyright configuration
Use `typeCheckingMode = "recommended"` for strictest checking:

```toml
[tool.basedpyright]
typeCheckingMode = "recommended"
pythonVersion = "3.14"
```

| Mode | Missing returns | Missing params | Unknown types |
|------|-----------------|----------------|---------------|
| basic | none | none | none |
| standard | none | none | warning |
| strict | error | error | error |
| recommended | error | error | error + extras |
| all | error (every rule) | error | error |

##### Migration from older patterns
When fixing issues, prefer modern replacements:

| Legacy Pattern | Modern Replacement |
|---------------|-------------------|
| `"ClassName"` forward refs | Direct references (deferred evaluation) |
| `from __future__ import annotations` | Remove (default behavior in 3.14) |
| `TypeVar("T")` boilerplate | `class Foo[T]:` syntax |
| `TypeGuard` for narrowing | `TypeIs` for intuitive narrowing |
| `typing.List`, `typing.Dict` | `list`, `dict` builtins |
| `Optional[X]` | `X \| None` |
| `Union[A, B]` | `A \| B` |
| `TypeAlias` annotation | `type` statement |

##### Workflow
- Local: `uvx basedpyright@latest` (run before commits)
- Add stubs only on demand (when missing-stub diagnostics appear)
- Use `autopep695` to auto-convert old TypeVar syntax to PEP 695
- Use `ruff --select=UP` to upgrade deprecated patterns
