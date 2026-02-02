# Implementation Plan: Plex Integration

## Overview

This implementation plan covers Phase 3 of the Zondarr project: Plex media server integration. The tasks are organized to build incrementally, starting with core types and the PlexClient implementation, then adding OAuth support, and finally integrating with the existing redemption flow.

## Tasks

- [x] 1. Add plexapi dependency and extend media types
  - [x] 1.1 Add plexapi package to project dependencies
    - Run `uv add plexapi` in the backend directory
    - Verify plexapi version >= 4.18.0
    - _Requirements: 18.1_
    - [x] 1.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 1.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 1.2 Add PlexUserType enum to media/types.py
    - Add `PlexUserType` StrEnum with FRIEND and HOME values
    - Follow existing Capability enum pattern
    - _Requirements: 6.1_
    - [x] 1.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 1.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 1.3 Commit and push changes and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

- [x] 2. Implement PlexClient core functionality
  - [x] 2.1 Implement PlexClient connection management
    - Implement `__init__` with url and api_key parameters
    - Implement `__aenter__` using asyncio.to_thread() to create PlexServer and MyPlexAccount
    - Implement `__aexit__` to clean up resources
    - Implement `capabilities()` returning CREATE_USER, DELETE_USER, LIBRARY_ACCESS
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 2.5_
    - [x] 2.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 2.2 Write property test for context manager round-trip
    - **Property 1: Context Manager Round-Trip**
    - **Validates: Requirements 1.1, 1.2**
    - [x] 2.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 2.3 Implement test_connection method
    - Use asyncio.to_thread() to query server info
    - Return True on success, False on any exception
    - Do not raise exceptions for connection failures
    - _Requirements: 1.3, 1.4, 1.5_
    - [x] 2.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 2.4 Write property test for test_connection return values
    - **Property 2: Connection Test Return Value Correctness**
    - **Validates: Requirements 1.3, 1.4, 1.5**
    - [x] 2.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 2.5 Implement get_libraries method
    - Use asyncio.to_thread() to call server.library.sections()
    - Map each section to LibraryInfo with key as external_id, title as name, type as library_type
    - Raise MediaClientError if client not initialized or on API failure
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
    - [x] 2.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 2.6 Write property test for get_libraries
    - **Property 3: Library Retrieval Produces Valid Structs**
    - **Validates: Requirements 3.1, 3.2**
    - [x] 2.6.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.6.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 2.7 Commit and push changes and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

- [x] 3. Checkpoint - Verify core PlexClient functionality
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement PlexClient user creation
  - [x] 4.1 Implement Friend user creation via inviteFriend
    - Use asyncio.to_thread() to call account.inviteFriend()
    - Return ExternalUser with email as identifier
    - Raise MediaClientError with USER_ALREADY_EXISTS on duplicate
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
    - [x] 4.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 4.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 4.2 Write property test for Friend creation
    - **Property 4: Friend Creation Returns Valid ExternalUser**
    - **Validates: Requirements 4.1, 4.2**
    - [x] 4.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 4.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 4.3 Implement Home User creation via createHomeUser
    - Use asyncio.to_thread() to call account.createHomeUser()
    - Return ExternalUser with Plex user ID as identifier
    - Raise MediaClientError with USERNAME_TAKEN on duplicate
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
    - [x] 4.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 4.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 4.4 Write property test for Home User creation
    - **Property 5: Home User Creation Returns Valid ExternalUser**
    - **Validates: Requirements 5.1, 5.2**
    - [x] 4.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 4.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 4.5 Implement create_user method with user type routing
    - Accept plex_user_type parameter (default FRIEND)
    - Route to _create_friend if FRIEND and email provided
    - Route to _create_home_user if HOME
    - Raise MediaClientError with EMAIL_REQUIRED if FRIEND without email
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
    - [x] 4.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 4.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 4.6 Write property test for user type routing
    - **Property 6: User Type Routing Correctness**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    - [x] 4.6.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 4.6.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 4.7 Commit and push changes and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

- [x] 5. Implement PlexClient user management
  - [x] 5.1 Implement delete_user method
    - Determine user type (Friend vs Home) from identifier
    - Use removeFriend() for Friends, appropriate method for Home Users
    - Return True on success, False if not found
    - Raise MediaClientError on other failures
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
    - [x] 5.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 5.2 Write property test for delete_user
    - **Property 7: Delete User Return Value Correctness**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
    - [x] 5.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 5.3 Implement set_library_access method
    - Use updateFriend() for Friends with section list
    - Handle Home User library access configuration
    - Return True on success, False if user not found
    - Handle empty library list as revoke all access
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4_
    - [x] 5.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 5.4 Write property test for set_library_access
    - **Property 8: Library Access Update Return Value Correctness**
    - **Validates: Requirements 8.1, 8.2, 8.3, 9.1, 9.2, 9.3**
    - [x] 5.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 5.5 Implement set_user_enabled method
    - Return False always (Plex doesn't support enable/disable)
    - Log warning about unsupported operation
    - Do not raise exception
    - _Requirements: 10.1, 10.2, 10.3_
    - [x] 5.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 5.6 Implement update_permissions method
    - Map can_download to allowSync setting
    - Return True on success, False if user not found
    - Raise MediaClientError on failure
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
    - [x] 5.6.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.6.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 5.7 Write property test for update_permissions
    - **Property 9: Permission Update Mapping and Return Value**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.5**
    - [x] 5.7.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.7.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 5.8 Implement list_users method
    - Retrieve all Friends via account.users()
    - Retrieve all Home Users
    - Map each to ExternalUser struct
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
    - [x] 5.8.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.8.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 5.9 Write property test for list_users
    - **Property 10: List Users Returns All Users as ExternalUser Structs**
    - **Validates: Requirements 12.1, 12.2, 12.3**
    - [x] 5.9.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.9.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 5.10 Commit and push changes and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

- [x] 6. Checkpoint - Verify complete PlexClient implementation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Register PlexClient in registry
  - [x] 7.1 Register PlexClient for ServerType.PLEX
    - Import PlexClient in app.py or appropriate startup location
    - Call registry.register(ServerType.PLEX, PlexClient)
    - _Requirements: 16.1, 16.2, 16.3_
    - [x] 7.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 7.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 7.2 Write unit tests for registry integration
    - Test create_client returns PlexClient instance
    - Test get_capabilities returns correct set
    - _Requirements: 16.1, 16.2, 16.3_
    - [x] 7.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 7.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 7.3 Commit and push changes and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

- [-] 8. Implement Plex OAuth service
  - [x] 8.1 Create PlexOAuthService class
    - Initialize with httpx.AsyncClient and client_id
    - Implement close() method for cleanup
    - _Requirements: 13.1_
    - [x] 8.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 8.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 8.2 Implement create_pin method
    - POST to plex.tv/api/v2/pins with X-Plex-Client-Identifier header
    - Parse response for pin id, code, and expiration
    - Return PlexOAuthPin struct with auth_url
    - _Requirements: 13.1, 13.2, 13.3, 13.4_
    - [x] 8.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 8.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 8.3 Write property test for create_pin
    - **Property 11: OAuth PIN Generation Returns Valid Response**
    - **Validates: Requirements 13.1, 13.2**
    - [x] 8.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 8.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 8.4 Implement check_pin method
    - GET plex.tv/api/v2/pins/{pin_id}
    - Check if authToken is present in response
    - If authenticated, call get_user_email to retrieve email
    - Return PlexOAuthResult with authenticated status and email
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
    - [x] 8.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 8.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 8.5 Write property test for check_pin
    - **Property 12: OAuth PIN Verification Retrieves Email on Success**
    - **Validates: Requirements 14.1, 14.2, 14.3**
    - [x] 8.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 8.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [x] 8.6 Implement get_user_email method
    - GET plex.tv/api/v2/user with X-Plex-Token header
    - Extract email from response
    - _Requirements: 14.3_
    - [x] 8.6.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 8.6.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [-] 8.7 Commit and push changes and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

- [ ] 9. Implement Plex OAuth controller
  - [ ] 9.1 Create PlexOAuthController with endpoints
    - POST /api/v1/join/plex/oauth/pin - create_pin endpoint
    - GET /api/v1/join/plex/oauth/pin/{pin_id} - check_pin endpoint
    - Mark endpoints as exclude_from_auth=True
    - _Requirements: 13.1, 13.2, 14.1_
    - [ ] 9.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [ ] 9.2 Create API schemas for OAuth responses
    - PlexOAuthPinResponse with pin_id, code, auth_url, expires_at
    - PlexOAuthCheckResponse with authenticated, email, error
    - _Requirements: 13.2, 14.2, 14.3_
    - [ ] 9.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [ ] 9.3 Add dependency injection for PlexOAuthService
    - Create provide_plex_oauth_service function
    - Register in controller dependencies
    - _Requirements: 13.1_
    - [ ] 9.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [ ] 9.4 Write unit tests for OAuth endpoints
    - Test PIN creation returns valid response
    - Test PIN check returns correct status
    - _Requirements: 13.1, 13.2, 14.1, 14.2_
    - [ ] 9.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [ ] 9.5 Commit and push changes and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

- [ ] 10. Checkpoint - Verify OAuth flow
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Integrate Plex with redemption service
  - [ ] 11.1 Update RedemptionService for Plex user types
    - Handle plex_user_type parameter in redemption
    - Pass OAuth-retrieved email for Friend invitations
    - Pass username for Home User creation
    - _Requirements: 15.1, 15.2_
    - [ ] 11.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 11.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [ ] 11.2 Verify rollback works for Plex
    - Ensure delete_user is called on rollback
    - Test multi-server rollback with Plex
    - _Requirements: 15.5_
    - [ ] 11.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 11.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [ ] 11.3 Write property test for redemption rollback
    - **Property 13: Redemption Rollback on Failure**
    - **Validates: Requirements 15.5**
    - [ ] 11.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 11.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [ ] 11.4 Commit and push changes and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

- [ ] 12. Add comprehensive error handling
  - [ ] 12.1 Implement error code mapping in PlexClient
    - Map Plex API errors to MediaClientError codes
    - Ensure all errors include operation, server_url, cause
    - _Requirements: 17.1_
    - [ ] 12.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 12.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [ ] 12.2 Write property test for error structure
    - **Property 14: Error Structure Contains Required Fields**
    - **Validates: Requirements 17.1**
    - [ ] 12.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 12.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [ ] 12.3 Add structlog logging throughout PlexClient
    - Log at info level for successful operations
    - Log at warning/error level for failures
    - Ensure no sensitive data (tokens, passwords) is logged
    - _Requirements: 17.2, 17.3, 17.4, 17.5_
    - [ ] 12.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 12.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

  - [ ] 12.4 Commit and push changes and fix all type errors following Type Safety Guidelines (no warnings, no errors, no excuses)

- [ ] 13. Final checkpoint - Complete integration testing
  - Ensure all tests pass, ask the user if questions arise.
  - Run basedpyright for type checking
  - Run ruff check and ruff format

## Notes

- All property-based tests are required for comprehensive coverage
- All python-plexapi calls must use asyncio.to_thread() to avoid blocking the event loop
- The PlexClient follows the same patterns as JellyfinClient for consistency
- OAuth flow is optional - invitations can also specify Home User creation without OAuth
- Property tests use Hypothesis with minimum 100 iterations per test
