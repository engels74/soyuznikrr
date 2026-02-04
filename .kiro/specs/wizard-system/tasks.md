# Implementation Plan: Wizard System

## Overview

This plan implements the wizard system for configurable multi-step onboarding flows during invitation redemption. The implementation follows Zondarr's layered architecture with backend (Python/Litestar) and frontend (SvelteKit/Svelte 5) components.

## Tasks

- [x] 1. Create database models and migration
  - [x] 1.1 Create Wizard and WizardStep SQLAlchemy models in `backend/src/zondarr/models/wizard.py`
    - Define InteractionType StrEnum with click, timer, tos, text_input, quiz values
    - Create Wizard model with name, description, enabled fields and TimestampMixin
    - Create WizardStep model with wizard_id FK, step_order, interaction_type, title, content_markdown, config JSON
    - Add cascade delete relationship and unique constraint on (wizard_id, step_order)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
    - [x] 1.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/`
    - [x] 1.1.2 Run type checking with `uv run basedpyright` and fix all type errors (no warnings, no errors)

  - [x] 1.2 Update Invitation model with wizard foreign keys
    - Add pre_wizard_id and post_wizard_id nullable FKs with ON DELETE SET NULL
    - Add pre_wizard and post_wizard relationships with selectin loading
    - _Requirements: 10.1, 10.4_
    - [x] 1.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/`
    - [x] 1.2.2 Run type checking with `uv run basedpyright` and fix all type errors (no warnings, no errors)

  - [x] 1.3 Create Alembic migration for wizard tables
    - Generate migration with `alembic revision --autogenerate`
    - Verify cascade delete and SET NULL behaviors
    - _Requirements: 1.1, 1.2, 10.1_
    - [x] 1.3.1 Verify migration script is correct and applies cleanly

  - [x] 1.4 Write property tests for model constraints
    - **Property 3: Cascade Delete Integrity**
    - **Property 4: Step Order Uniqueness**
    - **Validates: Requirements 1.3, 1.4**
    - [x] 1.4.1 Run tests with `uv run pytest tests/property/` and ensure all pass

  - [x] 1.5 Commit and push changes, fix all type errors (no warnings, no errors, no excuses)

- [x] 2. Implement wizard repository and service layer
  - [x] 2.1 Create WizardRepository in `backend/src/zondarr/repositories/wizard.py`
    - Implement CRUD operations extending base Repository
    - Add get_with_steps method with eager loading
    - Add list_paginated method
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
    - [x] 2.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/`
    - [x] 2.1.2 Run type checking with `uv run basedpyright` and fix all type errors (no warnings, no errors)

  - [x] 2.2 Create WizardStepRepository in `backend/src/zondarr/repositories/wizard_step.py`
    - Implement CRUD operations
    - Add reorder_steps method for contiguous ordering
    - Add get_max_order method for auto-assignment
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
    - [x] 2.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/`
    - [x] 2.2.2 Run type checking with `uv run basedpyright` and fix all type errors (no warnings, no errors)

  - [x] 2.3 Create WizardService in `backend/src/zondarr/services/wizard.py`
    - Implement wizard CRUD with validation
    - Implement step CRUD with auto-ordering
    - Implement step reordering with contiguity maintenance
    - Implement step validation logic for each interaction type
    - _Requirements: 2.1-2.6, 3.1-3.5, 9.1-9.6_
    - [x] 2.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/`
    - [x] 2.3.2 Run type checking with `uv run basedpyright` and fix all type errors (no warnings, no errors)

  - [x] 2.4 Write property tests for service validation logic
    - **Property 5: Interaction Type Validation**
    - **Property 6: Step Order Contiguity**
    - **Property 7: Timer Duration Bounds**
    - **Property 8: Quiz Configuration Completeness**
    - **Validates: Requirements 1.5, 3.4, 3.5, 5.4, 8.2, 8.3**
    - [x] 2.4.1 Run tests with `uv run pytest tests/property/` and ensure all pass

  - [x] 2.5 Commit and push changes, fix all type errors (no warnings, no errors, no excuses)

- [x] 3. Checkpoint - Backend models and services
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement wizard API endpoints
  - [x] 4.1 Add wizard msgspec schemas to `backend/src/zondarr/api/schemas.py`
    - Add WizardCreate, WizardUpdate request structs
    - Add WizardStepCreate, WizardStepUpdate request structs
    - Add StepReorderRequest, StepValidationRequest structs
    - Add WizardResponse, WizardDetailResponse, WizardStepResponse, StepValidationResponse structs
    - _Requirements: 2.1-2.6, 3.1-3.5, 9.1-9.6_
    - [x] 4.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/`
    - [x] 4.1.2 Run type checking with `uv run basedpyright` and fix all type errors (no warnings, no errors)

  - [x] 4.2 Create WizardController in `backend/src/zondarr/api/wizards.py`
    - Implement POST /api/v1/wizards (create wizard)
    - Implement GET /api/v1/wizards (list wizards with pagination)
    - Implement GET /api/v1/wizards/{id} (get wizard with steps)
    - Implement PATCH /api/v1/wizards/{id} (update wizard)
    - Implement DELETE /api/v1/wizards/{id} (delete wizard)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
    - [x] 4.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/`
    - [x] 4.2.2 Run type checking with `uv run basedpyright` and fix all type errors (no warnings, no errors)

  - [x] 4.3 Add step management endpoints to WizardController
    - Implement POST /api/v1/wizards/{id}/steps (create step)
    - Implement PATCH /api/v1/wizards/{id}/steps/{step_id} (update step)
    - Implement DELETE /api/v1/wizards/{id}/steps/{step_id} (delete step)
    - Implement POST /api/v1/wizards/{id}/steps/{step_id}/reorder (reorder step)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
    - [x] 4.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/`
    - [x] 4.3.2 Run type checking with `uv run basedpyright` and fix all type errors (no warnings, no errors)

  - [x] 4.4 Add step validation endpoint
    - Implement POST /api/v1/wizards/validate-step (public, no auth)
    - Validate timer elapsed time, quiz answers, text input constraints
    - Return completion token on success
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_
    - [x] 4.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/`
    - [x] 4.4.2 Run type checking with `uv run basedpyright` and fix all type errors (no warnings, no errors)

  - [x] 4.5 Update invitation endpoints to include wizard fields
    - Update CreateInvitationRequest with optional pre_wizard_id, post_wizard_id
    - Update InvitationDetailResponse to include pre_wizard, post_wizard
    - Update validation endpoint response to include wizard details
    - _Requirements: 10.2, 10.3_
    - [x] 4.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/`
    - [x] 4.5.2 Run type checking with `uv run basedpyright` and fix all type errors (no warnings, no errors)

  - [x] 4.6 Write property tests for validation endpoint
    - **Property 9: Quiz Answer Validation**
    - **Property 10: Text Input Constraint Validation**
    - **Property 11: Timer Duration Validation**
    - **Validates: Requirements 8.4, 8.5, 7.3, 7.4, 9.2, 9.3, 9.4**
    - [x] 4.6.1 Run tests with `uv run pytest tests/property/` and ensure all pass

  - [x] 4.7 Register WizardController in app.py
    - Add controller to route_handlers list
    - Add dependency providers for wizard service
    - _Requirements: 2.1-2.6_
    - [x] 4.7.1 Verify implementation adheres to coding guidelines in `.augment/rules/`
    - [x] 4.7.2 Run type checking with `uv run basedpyright` and fix all type errors (no warnings, no errors)

  - [x] 4.8 Commit and push changes, fix all type errors (no warnings, no errors, no excuses)

- [x] 5. Checkpoint - Backend API complete
  - Ensure all tests pass, ask the user if questions arise.


- [x] 6. Create frontend wizard components
  - [x] 6.1 Create wizard Zod schemas in `frontend/src/lib/schemas/wizard.ts`
    - Define wizardSchema, clickConfigSchema, timerConfigSchema
    - Define tosConfigSchema, textInputConfigSchema, quizConfigSchema
    - Export TypeScript types from schemas
    - _Requirements: 4.3, 5.4, 6.3, 7.2, 8.2, 8.3_
    - [x] 6.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 6.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 6.2 Add wizard API client functions to `frontend/src/lib/api/client.ts`
    - Add createWizard, getWizards, getWizard, updateWizard, deleteWizard
    - Add createStep, updateStep, deleteStep, reorderStep
    - Add validateStep function
    - _Requirements: 2.1-2.6, 3.1-3.5, 9.1_
    - [x] 6.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 6.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 6.3 Create wizard-shell.svelte component
    - Implement step sequencer with $state for currentStepIndex
    - Implement progress tracking with $derived
    - Implement sessionStorage persistence with $effect
    - Render markdown content with DOMPurify sanitization
    - Apply cinematic UI styling with custom CSS variables per `docs/frontend-design-skill.md`
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 14.6, 15.1, 15.3_
    - [x] 6.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 6.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 6.4 Create wizard-progress.svelte component
    - Display current step / total steps
    - Render progress bar with smooth transitions
    - Apply gold accent glow on completion per `docs/frontend-design-skill.md`
    - _Requirements: 11.2_
    - [x] 6.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 6.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 6.5 Create wizard-navigation.svelte component
    - Render Back button (disabled on first step)
    - Render Next/Complete button based on step position
    - Handle loading state during validation
    - Apply floating navigation styling with backdrop blur per `docs/frontend-design-skill.md`
    - _Requirements: 11.3, 11.4, 11.5_
    - [x] 6.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 6.5.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 6.6 Write property test for markdown sanitization
    - **Property 13: Markdown XSS Sanitization**
    - **Validates: Requirements 15.3**
    - [x] 6.6.1 Run tests with `bun run test` and ensure all pass

  - [x] 6.7 Commit and push changes, fix all type errors (no warnings, no errors, no excuses)

- [x] 7. Create interaction components
  - [x] 7.1 Create click-interaction.svelte
    - Render confirmation button with configurable text
    - Call onComplete with acknowledgment data
    - Apply accent button styling per `docs/frontend-design-skill.md`
    - _Requirements: 4.1, 4.2, 4.3, 12.1_
    - [x] 7.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 7.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 7.2 Create timer-interaction.svelte
    - Implement countdown with $state and setInterval
    - Render circular progress indicator with gradient stroke
    - Disable button until timer completes
    - Add pulse animation on final 5 seconds per `docs/frontend-design-skill.md`
    - Track startedAt timestamp for validation
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 12.2_
    - [x] 7.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 7.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 7.3 Create tos-interaction.svelte
    - Render terms content and acceptance checkbox
    - Require checkbox before enabling proceed
    - Record acceptance timestamp
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 12.3_
    - [x] 7.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 7.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 7.4 Create text-input-interaction.svelte
    - Render labeled input with placeholder
    - Implement client-side validation for required, min_length, max_length
    - Display validation errors inline
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 12.4_
    - [x] 7.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 7.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 7.5 Create quiz-interaction.svelte
    - Render question and selectable options
    - Apply border glow on hover, checkmark animation on selection per `docs/frontend-design-skill.md`
    - Call onComplete with selected answer_index
    - _Requirements: 8.1, 8.2, 8.3, 12.5_
    - [x] 7.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 7.5.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 7.6 Create interactions/index.ts barrel export
    - Export all interaction components
    - _Requirements: 12.1-12.5_
    - [x] 7.6.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`

  - [x] 7.7 Write unit tests for interaction components
    - Test click interaction button rendering
    - Test timer countdown and button state
    - Test TOS checkbox requirement
    - Test text input validation
    - Test quiz option selection
    - _Requirements: 4.1-4.3, 5.1-5.5, 6.1-6.4, 7.1-7.5, 8.1-8.5_
    - [x] 7.7.1 Run tests with `bun run test` and ensure all pass

  - [x] 7.8 Commit and push changes, fix all type errors (no warnings, no errors, no excuses)

- [x] 8. Checkpoint - Frontend wizard components
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Create admin wizard builder UI
  - [x] 9.1 Create wizard-builder.svelte component
    - Implement wizard metadata form (name, description, enabled)
    - Display step list with reorder capability
    - Add step creation with type selection
    - _Requirements: 13.1, 13.2, 13.3_
    - [x] 9.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 9.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 9.2 Create step-editor.svelte component
    - Render type-specific configuration forms
    - Validate config against Zod schemas
    - _Requirements: 13.3_
    - [x] 9.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 9.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 9.3 Create markdown-editor.svelte component
    - Implement textarea with markdown input
    - Render live preview with sanitized HTML
    - _Requirements: 13.4, 15.4_
    - [x] 9.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 9.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 9.4 Add preview mode to wizard-builder
    - Render WizardShell in preview mode
    - Allow testing wizard flow without saving
    - _Requirements: 13.5_
    - [x] 9.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 9.4.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 9.5 Create admin wizard routes
    - Create `frontend/src/routes/(admin)/wizards/+page.svelte` for wizard list
    - Create `frontend/src/routes/(admin)/wizards/[id]/+page.svelte` for wizard editor
    - Create `frontend/src/routes/(admin)/wizards/new/+page.svelte` for wizard creation
    - _Requirements: 13.1-13.6_
    - [x] 9.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 9.5.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 9.6 Commit and push changes, fix all type errors (no warnings, no errors, no excuses)

- [x] 10. Integrate wizards into invitation management
  - [x] 10.1 Update invitation form components
    - Add pre_wizard_id and post_wizard_id select fields
    - Fetch available wizards for dropdown options
    - _Requirements: 10.2_
    - [x] 10.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 10.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 10.2 Update invitation detail display
    - Show associated pre_wizard and post_wizard names
    - Link to wizard editor
    - _Requirements: 10.3_
    - [x] 10.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 10.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 10.3 Commit and push changes, fix all type errors (no warnings, no errors, no excuses)

- [x] 11. Integrate wizards into join flow
  - [x] 11.1 Update join page to handle pre-wizard
    - Check invitation validation response for pre_wizard
    - Display WizardShell before registration form
    - Track wizard completion state
    - _Requirements: 14.1, 14.3_
    - [x] 11.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 11.1.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 11.2 Update join page to handle post-wizard
    - Check invitation for post_wizard after successful redemption
    - Display WizardShell before success page
    - _Requirements: 14.2, 14.4_
    - [x] 11.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 11.2.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 11.3 Implement wizard abandonment handling
    - Ensure no accounts created if pre-wizard abandoned
    - Clear session storage on abandonment
    - _Requirements: 14.5_
    - [x] 11.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/frontend-dev-pro.md`
    - [x] 11.3.2 Run type checking with `bun run check` and fix all type errors (no warnings, no errors)

  - [x] 11.4 Write integration tests for join flow with wizards
    - Test pre-wizard completion before registration
    - Test post-wizard completion after registration
    - Test abandonment handling
    - _Requirements: 14.1-14.5_
    - [x] 11.4.1 Run tests with `bun run test` and ensure all pass

  - [x] 11.5 Commit and push changes, fix all type errors (no warnings, no errors, no excuses)

- [x] 12. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.
  - Run `bun run generate:api` to regenerate OpenAPI types
  - Run `uv run basedpyright` for backend type checking
  - Run `bun run check` for frontend type checking
  - Run `uv run pytest` for all backend tests
  - Run `bun run test` for all frontend tests

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Quality control steps ensure adherence to coding guidelines
- Commit steps ensure changes are properly versioned
