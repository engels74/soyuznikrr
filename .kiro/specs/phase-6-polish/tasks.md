# Implementation Plan: Phase 6 Polish

## Overview

This plan implements production polish features: background tasks, error handling with toasts, test coverage, and documentation. All implementation MUST follow `.augment/rules/backend-dev-pro.md` for Python and `.augment/rules/frontend-dev-pro.md` for Svelte 5.

## Tasks

- [x] 1. Backend Background Tasks
  - [x] 1.1 Add task configuration to Settings
    - Add `expiration_check_interval_seconds` (default: 3600)
    - Add `sync_interval_seconds` (default: 900)
    - _Requirements: 1.3, 2.4_

  - [x] 1.2 Create BackgroundTaskManager class
    - Implement `backend/src/zondarr/core/tasks.py`
    - Use asyncio tasks with graceful shutdown
    - Follow Python 3.14+ patterns (no `from __future__ import annotations`)
    - _Requirements: 1.1, 2.1_

  - [x] 1.3 Implement invitation expiration task
    - Query expired invitations and set `enabled=false`
    - Log count of processed invitations
    - Handle individual errors without stopping batch
    - _Requirements: 1.2, 1.4, 1.5_

  - [x] 1.4 Implement media server sync task
    - Iterate all enabled servers and call sync
    - Log results per server
    - Continue on individual server failures
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [x] 1.5 Add InvitationRepository.get_expired method
    - Query invitations where `expires_at < now` and `enabled=true`
    - _Requirements: 1.1_

  - [x] 1.6 Integrate background tasks into app lifespan
    - Add `background_tasks_lifespan` to `app.py`
    - _Requirements: 1.1, 2.1_

  - [x] 1.7 Write property tests for expiration task
    - **Property 1: Expired Invitation Disabling**
    - **Property 2: Expiration Task Error Resilience**
    - **Validates: Requirements 1.1, 1.2, 1.5**

  - [x] 1.8 Write property tests for sync task
    - **Property 3: Sync Identifies Discrepancies**
    - **Property 4: Sync Task Error Resilience**
    - **Validates: Requirements 2.1, 2.5, 2.6, 2.7**

- [x] 2. Backend Error Handling Enhancements
  - [x] 2.1 Add ExternalServiceError exception
    - Add to `backend/src/zondarr/core/exceptions.py`
    - Include `service_name` and optional `original` exception
    - _Requirements: 3.5_

  - [x] 2.2 Add external service error handler
    - Add handler to `backend/src/zondarr/api/errors.py`
    - Return HTTP 502 with service identification
    - _Requirements: 3.5_

  - [x] 2.3 Register error handler in app.py
    - Add `ExternalServiceError: external_service_error_handler` to exception_handlers
    - _Requirements: 3.5_

  - [x] 2.4 Update media clients to raise ExternalServiceError
    - Wrap connection/API errors in ExternalServiceError
    - Include server name in error
    - _Requirements: 3.5_

  - [x] 2.5 Write property tests for error handling
    - **Property 5: Error Response Structure**
    - **Property 6: Validation Error Field Mapping**
    - **Property 7: NotFound Error Resource Identification**
    - **Property 8: External Service Error Mapping**
    - **Validates: Requirements 3.1, 3.3, 3.4, 3.5**

- [x] 3. Checkpoint - Backend Complete
  - All backend tests pass, background tasks and error handling implemented.

- [x] 4. Frontend Toast Notifications
  - [x] 4.1 Add Toaster to root layout
    - Update `frontend/src/routes/+layout.svelte`
    - Import and configure svelte-sonner Toaster
    - Use Svelte 5 Runes patterns only
    - _Requirements: 4.6, 4.7_

  - [x] 4.2 Create toast utility functions
    - Create `frontend/src/lib/utils/toast.ts`
    - Implement `showSuccess`, `showError`, `showApiError`, `showNetworkError`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 4.3 Create API error handling wrapper
    - Add `withErrorHandling` function to `frontend/src/lib/api/client.ts`
    - Automatically show toasts on errors
    - _Requirements: 4.4, 5.1_

  - [x] 4.4 Add toast calls to invitation operations
    - Show success toast on create/delete
    - Use `withErrorHandling` for API calls
    - _Requirements: 4.1, 4.2_

  - [x] 4.5 Add toast calls to server operations
    - Show success toast on add/delete
    - Use `withErrorHandling` for API calls
    - _Requirements: 4.3_

  - [x] 4.6 Add toast calls to user operations
    - Show success toast on enable/disable/delete
    - Use `withErrorHandling` for API calls
    - _Requirements: 4.2_

  - [x] 4.7 Write tests for toast utilities
    - **Property 9: API Error Toast Display**
    - **Validates: Requirements 4.4, 5.1**

- [x] 5. Frontend Error Handling
  - [x] 5.1 Create error boundary component
    - Create `frontend/src/lib/components/error-boundary.svelte`
    - Use Svelte 5 snippets for fallback
    - NO legacy patterns (`<slot>`, `export let`)
    - _Requirements: 5.4_

  - [x] 5.2 Add error states to data loading pages
    - Error state UI with retry button exists (`error-state.svelte`)
    - Uses shadcn-svelte Alert-style component
    - _Requirements: 5.3_

  - [x] 5.3 Ensure error messages are safe
    - Filter out stack traces and internal details
    - Show generic messages for unexpected errors
    - _Requirements: 5.5_

  - [x] 5.4 Write tests for error boundary
    - **Property 11: Error Boundary Containment**
    - **Property 12: Error Message Safety**
    - **Validates: Requirements 5.4, 5.5**

- [x] 6. Checkpoint - Frontend Complete
  - Ensure all frontend tests pass, ask the user if questions arise.

- [x] 7. Test Coverage Improvements
  - [x] 7.1 Add backend property tests for invitation flow
    - Test invitation creation with various configurations
    - Test invitation redemption validation
    - _Requirements: 6.1, 6.2_

  - [x] 7.2 Add backend property tests for user management
    - Test user enable/disable operations
    - Test user deletion cascade behavior
    - _Requirements: 6.3_

  - [x] 7.3 Add backend property tests for media server integration
    - Test client creation from registry
    - Test sync result calculation
    - _Requirements: 6.4_

  - [x] 7.4 Add frontend component tests for invitation form
    - Test form validation
    - Test submission behavior
    - _Requirements: 7.1_

  - [x] 7.5 Add frontend component tests for user table
    - Test user list rendering
    - Test action button behavior
    - _Requirements: 7.2_

  - [x] 7.6 Add frontend component tests for server management
    - Test server list rendering
    - Test add/delete flows
    - _Requirements: 7.3_

- [ ] 8. Documentation
  - [ ] 8.1 Create README.md at repository root
    - Brief project overview (1-2 sentences)
    - Quick start commands for backend and frontend
    - Concise tech stack list
    - Keep under 50 lines
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 9. Final Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All backend code must follow `.augment/rules/backend-dev-pro.md`
- All frontend code must follow `.augment/rules/frontend-dev-pro.md`
- Property tests should run minimum 100 iterations
- Each property test must reference its design document property
- Type checking commands:
  - Backend: `uv run basedpyright`
  - Frontend: `bun run check`
