# Requirements Document

## Introduction

The Wizard System enables administrators to configure multi-step wizard flows that users must complete during invitation redemption. Wizards can be configured to run before account creation (pre-registration), after account creation (post-registration), or both. Each wizard consists of ordered steps with different interaction types: click confirmation, timed delays, terms of service acceptance, text input collection, and quiz questions.

## Glossary

- **Wizard**: A configurable sequence of steps that users must complete during invitation redemption
- **Wizard_Step**: A single step within a wizard with a specific interaction type and content
- **Interaction_Type**: The type of user interaction required for a step (click, timer, tos, text_input, quiz)
- **Pre_Registration_Wizard**: A wizard that runs before account creation
- **Post_Registration_Wizard**: A wizard that runs after account creation
- **Step_Validation**: Server-side verification that a step was completed correctly
- **Wizard_Shell**: The frontend component that orchestrates step display and navigation
- **Wizard_Builder**: The admin UI for creating and editing wizards

## Requirements

### Requirement 1: Wizard Data Model

**User Story:** As a system architect, I want wizard and step data persisted in the database, so that wizard configurations survive restarts and can be managed via the API.

#### Acceptance Criteria

1. THE Wizard model SHALL store id, name, description, enabled status, and timestamps
2. THE Wizard_Step model SHALL store id, wizard_id, step_order, interaction_type, title, content_markdown, and configuration JSON
3. WHEN a Wizard is deleted, THE system SHALL cascade delete all associated Wizard_Steps
4. THE Wizard_Step model SHALL enforce unique step_order within each wizard
5. THE Wizard_Step interaction_type field SHALL only accept values: click, timer, tos, text_input, quiz

### Requirement 2: Wizard CRUD API

**User Story:** As an administrator, I want to create, read, update, and delete wizards via the API, so that I can manage wizard configurations programmatically.

#### Acceptance Criteria

1. WHEN a POST request is made to /api/v1/wizards with valid data, THE system SHALL create a new wizard and return HTTP 201
2. WHEN a GET request is made to /api/v1/wizards, THE system SHALL return a paginated list of wizards
3. WHEN a GET request is made to /api/v1/wizards/{id}, THE system SHALL return the wizard with all its steps
4. WHEN a PATCH request is made to /api/v1/wizards/{id} with valid data, THE system SHALL update the wizard
5. WHEN a DELETE request is made to /api/v1/wizards/{id}, THE system SHALL delete the wizard and all its steps
6. IF a wizard with the specified id does not exist, THEN THE system SHALL return HTTP 404

### Requirement 3: Wizard Step CRUD API

**User Story:** As an administrator, I want to manage individual wizard steps, so that I can customize the user onboarding experience.

#### Acceptance Criteria

1. WHEN a POST request is made to /api/v1/wizards/{wizard_id}/steps with valid data, THE system SHALL create a new step and return HTTP 201
2. WHEN a PATCH request is made to /api/v1/wizards/{wizard_id}/steps/{step_id}, THE system SHALL update the step
3. WHEN a DELETE request is made to /api/v1/wizards/{wizard_id}/steps/{step_id}, THE system SHALL delete the step
4. WHEN a step is deleted, THE system SHALL reorder remaining steps to maintain contiguous ordering
5. WHEN a POST request is made to /api/v1/wizards/{wizard_id}/steps/{step_id}/reorder with new_order, THE system SHALL move the step to the new position

### Requirement 4: Click Interaction Type

**User Story:** As an administrator, I want to create steps that require users to click a button to proceed, so that I can ensure users acknowledge information.

#### Acceptance Criteria

1. WHEN a step has interaction_type "click", THE Wizard_Shell SHALL display the content and a confirmation button
2. WHEN the user clicks the confirmation button, THE system SHALL mark the step as complete
3. THE click step configuration SHALL support a custom button_text field with default "I Understand"

### Requirement 5: Timer Interaction Type

**User Story:** As an administrator, I want to create steps that require users to wait a specified duration, so that I can ensure users spend time reading important content.

#### Acceptance Criteria

1. WHEN a step has interaction_type "timer", THE Wizard_Shell SHALL display the content and a countdown timer
2. WHILE the timer is counting down, THE system SHALL disable the proceed button
3. WHEN the timer reaches zero, THE system SHALL enable the proceed button
4. THE timer step configuration SHALL require a duration_seconds field (minimum 1, maximum 300)
5. THE Wizard_Shell SHALL display the remaining time in a human-readable format

### Requirement 6: Terms of Service Interaction Type

**User Story:** As an administrator, I want to create steps that require users to accept terms of service, so that I can ensure legal compliance.

#### Acceptance Criteria

1. WHEN a step has interaction_type "tos", THE Wizard_Shell SHALL display the terms content and a checkbox
2. THE tos step SHALL require users to check the acceptance checkbox before proceeding
3. THE tos step configuration SHALL support a checkbox_label field with default "I accept the terms of service"
4. WHEN the user checks the checkbox and clicks proceed, THE system SHALL record the acceptance timestamp

### Requirement 7: Text Input Interaction Type

**User Story:** As an administrator, I want to create steps that collect text input from users, so that I can gather additional information during onboarding.

#### Acceptance Criteria

1. WHEN a step has interaction_type "text_input", THE Wizard_Shell SHALL display the content and an input field
2. THE text_input step configuration SHALL support label, placeholder, required, min_length, and max_length fields
3. IF required is true and the input is empty, THEN THE system SHALL prevent proceeding
4. IF min_length or max_length constraints are violated, THEN THE system SHALL display validation errors
5. WHEN the user submits valid input, THE system SHALL store the response with the step completion

### Requirement 8: Quiz Interaction Type

**User Story:** As an administrator, I want to create quiz steps that test user comprehension, so that I can verify users understand important information.

#### Acceptance Criteria

1. WHEN a step has interaction_type "quiz", THE Wizard_Shell SHALL display the question and answer options
2. THE quiz step configuration SHALL require a question field and an options array with at least 2 choices
3. THE quiz step configuration SHALL require a correct_answer_index field indicating the correct option
4. IF the user selects an incorrect answer, THEN THE system SHALL display an error and prevent proceeding
5. WHEN the user selects the correct answer, THE system SHALL mark the step as complete

### Requirement 9: Step Validation Endpoint

**User Story:** As a system architect, I want server-side validation of step completions, so that users cannot bypass wizard steps.

#### Acceptance Criteria

1. WHEN a POST request is made to /api/v1/wizards/validate-step with step_id and response data, THE system SHALL validate the response
2. THE validation endpoint SHALL verify timer steps waited the required duration
3. THE validation endpoint SHALL verify quiz steps have the correct answer
4. THE validation endpoint SHALL verify text_input steps meet length constraints
5. IF validation fails, THEN THE system SHALL return HTTP 400 with error details
6. IF validation succeeds, THEN THE system SHALL return HTTP 200 with a completion token

### Requirement 10: Invitation-Wizard Association

**User Story:** As an administrator, I want to associate wizards with invitations, so that different invitations can have different onboarding flows.

#### Acceptance Criteria

1. THE Invitation model SHALL have optional pre_wizard_id and post_wizard_id foreign keys
2. WHEN creating or updating an invitation, THE system SHALL accept optional pre_wizard_id and post_wizard_id fields
3. WHEN validating an invitation code, THE response SHALL include the associated pre_wizard and post_wizard details
4. IF a wizard is deleted that is referenced by invitations, THEN THE system SHALL set those references to null

### Requirement 11: Frontend Wizard Shell Component

**User Story:** As a user, I want a clear and intuitive wizard interface, so that I can complete the required steps easily.

#### Acceptance Criteria

1. THE Wizard_Shell component SHALL display the current step content rendered from markdown
2. THE Wizard_Shell component SHALL display a progress indicator showing current step and total steps
3. THE Wizard_Shell component SHALL provide navigation buttons (Back, Next/Complete)
4. WHEN on the first step, THE Wizard_Shell SHALL hide or disable the Back button
5. WHEN on the last step, THE Wizard_Shell SHALL change the Next button to "Complete"
6. THE Wizard_Shell component SHALL validate each step before allowing progression

### Requirement 12: Frontend Interaction Components

**User Story:** As a developer, I want reusable interaction components for each type, so that the wizard shell can render any step type.

#### Acceptance Criteria

1. THE system SHALL provide a ClickInteraction component that renders a confirmation button
2. THE system SHALL provide a TimerInteraction component that renders a countdown and disabled button
3. THE system SHALL provide a TosInteraction component that renders terms content and acceptance checkbox
4. THE system SHALL provide a TextInputInteraction component that renders a labeled input with validation
5. THE system SHALL provide a QuizInteraction component that renders a question with selectable options

### Requirement 13: Admin Wizard Builder UI

**User Story:** As an administrator, I want a visual interface to create and edit wizards, so that I can configure onboarding flows without writing code.

#### Acceptance Criteria

1. THE Wizard_Builder SHALL provide a form to create new wizards with name and description
2. THE Wizard_Builder SHALL display existing steps in a reorderable list
3. THE Wizard_Builder SHALL provide a form to add new steps with type selection and configuration
4. THE Wizard_Builder SHALL provide a markdown editor for step content authoring
5. THE Wizard_Builder SHALL provide a preview mode to test the wizard flow
6. WHEN reordering steps via drag-and-drop, THE Wizard_Builder SHALL update step_order values

### Requirement 14: Join Flow Integration

**User Story:** As a user redeeming an invitation, I want to complete any required wizard steps, so that I can gain access to the media server.

#### Acceptance Criteria

1. WHEN an invitation has a pre_wizard, THE join flow SHALL display the wizard before the registration form
2. WHEN an invitation has a post_wizard, THE join flow SHALL display the wizard after successful account creation
3. WHEN all pre_wizard steps are completed, THE join flow SHALL proceed to registration
4. WHEN all post_wizard steps are completed, THE join flow SHALL display the success page
5. IF the user abandons the wizard, THEN THE system SHALL not create any accounts
6. THE join flow SHALL persist wizard progress in session storage to survive page refreshes

### Requirement 15: Wizard Step Content Rendering

**User Story:** As an administrator, I want to write step content in markdown, so that I can format text with headings, lists, and links.

#### Acceptance Criteria

1. THE system SHALL render step content_markdown as HTML in the wizard shell
2. THE markdown renderer SHALL support headings, paragraphs, lists, bold, italic, and links
3. THE markdown renderer SHALL sanitize HTML to prevent XSS attacks
4. THE admin markdown editor SHALL provide a live preview of rendered content
