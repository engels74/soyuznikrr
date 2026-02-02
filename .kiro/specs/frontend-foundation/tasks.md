# Implementation Plan: Frontend Foundation & Core UI

## Overview

This implementation plan breaks down the frontend foundation into discrete, incremental tasks. Each task builds on previous work, ensuring no orphaned code. The plan follows the design document architecture and integrates with the existing Litestar backend.

## Tasks

- [-] 1. Project scaffolding and configuration
  - [x] 1.1 Initialize SvelteKit project with Bun and TypeScript
    - Run `bun create svelte@latest frontend` with TypeScript, ESLint options
    - Configure `svelte.config.js` with `svelte-adapter-bun`
    - Update `tsconfig.json` for strict mode
    - _Requirements: 1.1, 1.2_
    - [x] 1.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 1.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 1.2 Configure UnoCSS with required presets
    - Install UnoCSS and presets: `bun add -D unocss @unocss/preset-icons unocss-preset-animations unocss-preset-shadcn`
    - Create `uno.config.ts` with presetWind4, presetShadcn (neutral, .dark), presetIcons, presetAnimations
    - Configure `vite.config.ts` with UnoCSS plugin before sveltekit
    - Create `src/app.css` with UnoCSS directives
    - _Requirements: 1.3_
    - [x] 1.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 1.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 1.3 Install and configure shadcn-svelte
    - Run `bunx shadcn-svelte@latest init` with neutral theme
    - Add core components: button, card, dialog, form, input, label, select, table, badge, skeleton, toast
    - Verify components in `$lib/components/ui/`
    - _Requirements: 1.4_
    - [x] 1.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 1.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 1.4 Install remaining dependencies
    - Install form handling: `bun add sveltekit-superforms zod`
    - Install API client: `bun add openapi-fetch`
    - Install dev tools: `bun add -D openapi-typescript`
    - Install utilities: `bun add mode-watcher svelte-sonner @lucide/svelte`
    - _Requirements: 1.5, 1.7, 1.8, 1.9, 1.10_
    - [ ] 1.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 1.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 1.5 Configure custom fonts and design tokens
    - Add JetBrains Mono and IBM Plex Sans/Mono via Google Fonts or local files
    - Update `uno.config.ts` with custom theme colors (Control Room palette)
    - Create CSS custom properties for design tokens
    - _Requirements: 13.1, 13.2, 13.3_
    - [ ] 1.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 1.5.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 1.6 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 2. API client setup and type generation
  - [ ] 2.1 Generate TypeScript types from OpenAPI spec
    - Create `scripts/generate-api-types.ts` script
    - Add npm script: `"generate:api": "openapi-typescript http://localhost:8000/docs/openapi.json -o src/lib/api/types.d.ts"`
    - Generate initial types from running backend
    - _Requirements: 1.6, 2.1_
    - [ ] 2.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 2.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 2.2 Create API client with typed wrappers
    - Create `$lib/api/client.ts` with openapi-fetch client
    - Create typed wrapper functions for all endpoints (invitations, users, servers, join)
    - Configure base URL from environment variable
    - _Requirements: 2.2, 2.6, 2.7_
    - [ ] 2.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 2.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 2.3 Create error handling utilities
    - Create `$lib/api/errors.ts` with ApiError class
    - Implement error transformation from API responses
    - Create helper functions: `getErrorMessage`, `isNetworkError`
    - _Requirements: 2.3, 2.4, 2.5_
    - [ ] 2.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 2.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 2.4 Write property tests for API client
    - **Property 3: API Error Transformation**
    - **Property 4: Pagination Parameter Passing**
    - **Property 5: Filter Parameter Passing**
    - **Validates: Requirements 2.4, 2.5, 2.6, 2.7**
    - [ ] 2.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 2.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 2.5 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 3. Root layout and dark mode
  - [ ] 3.1 Create root layout with ModeWatcher and Toaster
    - Update `src/routes/+layout.svelte` with ModeWatcher component
    - Add Toaster from svelte-sonner
    - Import app.css
    - Use `{@render children()}` pattern (Svelte 5)
    - _Requirements: 1.8, 1.9, 3.4_
    - [ ] 3.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 3.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 3.2 Write property test for dark mode persistence
    - **Property 7: Dark Mode Persistence**
    - **Validates: Requirements 3.4**
    - [ ] 3.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 3.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 3.3 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 4. Admin layout and navigation
  - [ ] 4.1 Create admin route group layout
    - Create `src/routes/(admin)/+layout.svelte`
    - Implement sidebar navigation with NavItem components
    - Implement header with PageTitle and ThemeToggle
    - Use responsive design with mobile menu
    - _Requirements: 3.1, 3.2, 3.5, 3.7_
    - [ ] 4.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 4.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 4.2 Create shared UI components
    - Create `$lib/components/StatusBadge.svelte` with color mapping
    - Create `$lib/components/Pagination.svelte` for list views
    - Create `$lib/components/EmptyState.svelte` for empty lists
    - Create `$lib/components/ErrorState.svelte` for error display
    - Create `$lib/components/ConfirmDialog.svelte` for destructive actions
    - _Requirements: 4.5, 7.5, 13.4, 14.4, 14.6_
    - [ ] 4.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 4.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 4.3 Write property tests for shared components
    - **Property 12: Status Badge Color Mapping**
    - **Property 38: Empty State Display**
    - **Validates: Requirements 4.5, 7.5, 13.4, 14.6**
    - [ ] 4.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 4.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 4.4 Write property test for responsive sidebar
    - **Property 8: Responsive Sidebar Collapse**
    - **Validates: Requirements 3.5**
    - [ ] 4.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 4.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 4.5 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 5. Checkpoint - Verify foundation
  - Ensure all tests pass, ask the user if questions arise.
  - Verify dark mode toggle works
  - Verify navigation between sections works
  - Verify API client can connect to backend

- [ ] 6. Invitation management - List view
  - [ ] 6.1 Create invitation list page with data loading
    - Create `src/routes/(admin)/invitations/+page.svelte`
    - Create `src/routes/(admin)/invitations/+page.ts` for load function
    - Implement loading skeleton state
    - Implement error state with retry
    - Implement empty state
    - _Requirements: 4.1, 14.1, 14.5, 14.6_
    - [ ] 6.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 6.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 6.2 Create invitation table component
    - Create `$lib/components/invitations/InvitationTable.svelte`
    - Create `$lib/components/invitations/InvitationRow.svelte`
    - Display code, use_count, max_uses, expires_at, enabled, is_active
    - Display remaining_uses when available
    - Use StatusBadge for status display
    - Use monospace font for code display
    - _Requirements: 4.2, 4.5, 4.6, 13.3_
    - [ ] 6.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 6.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 6.3 Create invitation filters component
    - Create `$lib/components/invitations/InvitationFilters.svelte`
    - Implement enabled filter (all/enabled/disabled)
    - Implement expired filter (all/active/expired)
    - Implement sort_by select (created_at, expires_at, use_count)
    - Implement sort_order toggle (asc/desc)
    - Sync filters with URL search params
    - _Requirements: 4.3, 4.4_
    - [ ] 6.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 6.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 6.4 Write property tests for invitation list
    - **Property 9: Invitation Field Display**
    - **Property 10: Invitation Filter Application**
    - **Property 11: Invitation Sort Application**
    - **Property 13: Remaining Uses Display**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.6**
    - [ ] 6.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 6.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 6.5 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)


- [ ] 7. Invitation management - Create and edit
  - [ ] 7.1 Create invitation form schema
    - Create `$lib/schemas/invitation.ts` with Zod schemas
    - Define createInvitationSchema with all fields
    - Define updateInvitationSchema for mutable fields only
    - _Requirements: 5.10_
    - [ ] 7.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 7.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 7.2 Create invitation form component
    - Create `$lib/components/invitations/InvitationForm.svelte`
    - Use Superforms with zodClient adapter
    - Implement server multi-select for target servers
    - Implement library multi-select (filtered by selected servers)
    - Implement optional fields: code, expires_at, max_uses, duration_days
    - Display inline validation errors
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.9, 5.10_
    - [ ] 7.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 7.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 7.3 Create invitation dialog
    - Create `$lib/components/invitations/CreateInvitationDialog.svelte`
    - Wire form submission to API client
    - Display success toast on creation
    - Display error toast on failure
    - Close dialog and refresh list on success
    - _Requirements: 5.1, 5.8_
    - [ ] 7.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 7.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 7.4 Create invitation detail page
    - Create `src/routes/(admin)/invitations/[id]/+page.svelte`
    - Create `src/routes/(admin)/invitations/[id]/+page.ts` for load function
    - Display all invitation fields including target_servers and allowed_libraries
    - Display immutable fields as read-only (code, use_count, created_at, created_by)
    - Implement edit form for mutable fields
    - Implement delete button with confirmation dialog
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_
    - [ ] 7.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 7.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 7.5 Write property tests for invitation forms
    - **Property 14: Form Validation Error Display**
    - **Property 15: Invitation Detail Field Display**
    - **Property 16: Immutable Field Protection**
    - **Validates: Requirements 5.9, 6.2, 6.4, 14.3**
    - [ ] 7.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 7.5.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 7.6 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 8. Checkpoint - Verify invitation management
  - Ensure all tests pass, ask the user if questions arise.
  - Verify invitation list displays correctly
  - Verify filters and sorting work
  - Verify create invitation flow works
  - Verify edit invitation flow works
  - Verify delete invitation flow works

- [ ] 9. User management - List view
  - [ ] 9.1 Create user list page with data loading
    - Create `src/routes/(admin)/users/+page.svelte`
    - Create `src/routes/(admin)/users/+page.ts` for load function
    - Implement loading skeleton state
    - Implement error state with retry
    - Implement empty state
    - _Requirements: 7.1, 14.1, 14.5, 14.6_
    - [ ] 9.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 9.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 9.2 Create user table component
    - Create `$lib/components/users/UserTable.svelte`
    - Create `$lib/components/users/UserRow.svelte`
    - Display username, media_server name, enabled, expires_at, created_at
    - Display source invitation code when available
    - Use StatusBadge for status display
    - _Requirements: 7.2, 7.5, 7.7_
    - [ ] 9.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 9.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 9.3 Create user filters component
    - Create `$lib/components/users/UserFilters.svelte`
    - Implement server_id filter (select from available servers)
    - Implement invitation_id filter (select from available invitations)
    - Implement enabled filter (all/enabled/disabled)
    - Implement expired filter (all/active/expired)
    - Implement sort_by select (created_at, username, expires_at)
    - Implement sort_order toggle (asc/desc)
    - Sync filters with URL search params
    - _Requirements: 7.3, 7.4_
    - [ ] 9.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 9.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 9.4 Write property tests for user list
    - **Property 17: User Field Display**
    - **Property 18: User Filter Application**
    - **Property 19: User Sort Application**
    - **Property 20: User Invitation Code Display**
    - **Validates: Requirements 7.2, 7.3, 7.4, 7.7**
    - [ ] 9.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 9.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 9.5 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 10. User management - Detail and actions
  - [ ] 10.1 Create user detail page
    - Create `src/routes/(admin)/users/[id]/+page.svelte`
    - Create `src/routes/(admin)/users/[id]/+page.ts` for load function
    - Display user information (username, external_user_id, enabled, expires_at)
    - Display identity information with all linked users
    - Display media server information
    - Display source invitation if available
    - _Requirements: 8.1, 8.2, 8.3_
    - [ ] 10.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 10.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 10.2 Implement user action buttons
    - Add Enable button (visible when user.enabled === false)
    - Add Disable button (visible when user.enabled === true)
    - Add Delete button with confirmation dialog
    - Wire buttons to API endpoints
    - Display success/error toasts
    - _Requirements: 8.4, 8.5, 8.6, 8.7, 8.8, 8.9_
    - [ ] 10.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 10.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 10.3 Write property tests for user detail
    - **Property 21: User Detail Relationship Display**
    - **Property 22: Linked Users Display**
    - **Property 23: Enable Button Visibility**
    - **Property 24: Disable Button Visibility**
    - **Property 37: Confirmation Dialog Display**
    - **Validates: Requirements 8.2, 8.3, 8.4, 8.5, 14.4**
    - [ ] 10.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 10.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 10.4 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 11. Server management
  - [ ] 11.1 Create server list page
    - Create `src/routes/(admin)/servers/+page.svelte`
    - Create `src/routes/(admin)/servers/+page.ts` for load function
    - Display servers as cards with name, server_type, url, enabled, library count
    - Implement loading and error states
    - _Requirements: 9.1, 9.2_
    - [ ] 11.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 11.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 11.2 Create server detail page with sync
    - Create `src/routes/(admin)/servers/[id]/+page.svelte`
    - Create `src/routes/(admin)/servers/[id]/+page.ts` for load function
    - Display server details and library list
    - Implement Sync button
    - Create SyncResultsDialog to display sync results
    - Display orphaned_users, stale_users, matched_users
    - Handle sync errors with appropriate messaging
    - _Requirements: 9.3, 9.4, 9.5, 9.6, 9.7_
    - [ ] 11.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 11.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 11.3 Write property tests for server management
    - **Property 25: Server Field Display**
    - **Property 26: Sync Result Display**
    - **Validates: Requirements 9.2, 9.6**
    - [ ] 11.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 11.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 11.4 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 12. Checkpoint - Verify admin features
  - Ensure all tests pass, ask the user if questions arise.
  - Verify user list displays correctly
  - Verify user filters and sorting work
  - Verify user enable/disable/delete works
  - Verify server list displays correctly
  - Verify server sync works

- [ ] 13. Public join flow - Code validation
  - [ ] 13.1 Create public route group layout
    - Create `src/routes/(public)/+layout.svelte`
    - Implement minimal layout for public pages
    - Include ModeWatcher for dark mode support
    - _Requirements: 10.1_
    - [ ] 13.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 13.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 13.2 Create join page with code validation
    - Create `src/routes/(public)/join/[code]/+page.svelte`
    - Create `src/routes/(public)/join/[code]/+page.ts` for load function
    - Call validation endpoint on page load
    - Display loading state during validation
    - Display target servers and allowed libraries for valid codes
    - Display duration_days if set
    - Display error message for invalid codes with failure_reason
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
    - [ ] 13.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 13.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 13.3 Write property tests for code validation
    - **Property 27: Valid Code Display**
    - **Property 28: Invalid Code Error Display**
    - **Property 29: Duration Display**
    - **Validates: Requirements 10.2, 10.3, 10.4**
    - [ ] 13.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 13.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 13.4 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 14. Public join flow - Jellyfin registration
  - [ ] 14.1 Create Jellyfin registration form schema
    - Create `$lib/schemas/join.ts` with jellyfinRegistrationSchema
    - Validate username (3-32 chars, lowercase, starts with letter)
    - Validate password (minimum 8 characters)
    - Validate optional email
    - _Requirements: 11.2, 11.3, 11.4, 11.5_
    - [ ] 14.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 14.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 14.2 Create Jellyfin registration form component
    - Create `$lib/components/join/JellyfinRegistrationForm.svelte`
    - Use Superforms with zodClient adapter
    - Display inline validation errors
    - Submit to redeem endpoint
    - _Requirements: 11.1, 11.5, 11.6_
    - [ ] 14.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 14.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 14.3 Create success and error pages
    - Create `$lib/components/join/SuccessPage.svelte`
    - Display server access instructions
    - Create error handling for USERNAME_TAKEN and SERVER_ERROR
    - Display failed_server name on server errors
    - _Requirements: 11.7, 11.8, 11.9_
    - [ ] 14.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 14.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 14.4 Write property tests for Jellyfin registration
    - **Property 30: Username Validation**
    - **Property 31: Password Validation**
    - **Validates: Requirements 11.2, 11.3**
    - [ ] 14.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 14.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 14.5 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 15. Public join flow - Plex OAuth
  - [ ] 15.1 Create Plex OAuth flow component
    - Create `$lib/components/join/PlexOAuthFlow.svelte`
    - Display "Sign in with Plex" button
    - Create PIN via API on button click
    - Display PIN code to user
    - Open Plex auth URL in new window/tab
    - _Requirements: 12.1, 12.2, 12.3_
    - [ ] 15.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 15.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 15.2 Implement PIN polling
    - Create polling mechanism with setInterval
    - Poll PIN status endpoint every 2 seconds
    - Stop polling when authenticated or expired
    - Display user's Plex email when authenticated
    - Display error and retry option when expired
    - _Requirements: 12.4, 12.5, 12.6_
    - [ ] 15.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 15.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 15.3 Complete Plex redemption flow
    - Proceed to redemption after successful OAuth
    - Display success page with server access instructions
    - _Requirements: 12.7_
    - [ ] 15.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 15.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 15.4 Write property test for Plex OAuth polling
    - **Property 32: Plex OAuth Polling**
    - **Validates: Requirements 12.4**
    - [ ] 15.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 15.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 15.5 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 16. Final polish and accessibility
  - [ ] 16.1 Add loading states throughout
    - Ensure all data fetching shows skeleton loaders
    - Add loading spinners to action buttons
    - _Requirements: 14.1_
    - [ ] 16.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 16.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 16.2 Add toast notifications throughout
    - Ensure all API errors show toast notifications
    - Ensure all successful actions show success toasts
    - _Requirements: 14.2, 3.6_
    - [ ] 16.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 16.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 16.3 Write property tests for loading and error states
    - **Property 35: Loading State Display**
    - **Property 36: API Error Toast Display**
    - **Validates: Requirements 14.1, 14.2**
    - [ ] 16.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 16.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 16.4 Write accessibility tests
    - **Property 34: Accessibility Compliance**
    - Test keyboard navigation
    - Test ARIA attributes
    - **Validates: Requirements 13.8**
    - [ ] 16.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [ ] 16.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [ ] 16.5 Commit and push changes with all type errors fixed (no warnings, no errors, no excuses)

- [ ] 17. Final checkpoint - Complete verification
  - Ensure all tests pass, ask the user if questions arise.
  - Verify complete invitation management flow
  - Verify complete user management flow
  - Verify complete server management flow
  - Verify complete Jellyfin join flow
  - Verify complete Plex OAuth join flow
  - Verify dark mode works throughout
  - Verify responsive design works

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- All Svelte components use Runes-only patterns ($state, $derived, $props, snippets)
- No legacy Svelte patterns (no $:, no export let, no slots)
- Each subtask includes verification steps for coding guidelines and type checking
- Each main task ends with a commit step to ensure clean version control
