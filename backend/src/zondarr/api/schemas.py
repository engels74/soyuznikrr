"""API request/response schemas using msgspec Structs.

Provides:
- ErrorResponse: Standard error response structure
- MediaServerCreate/Response: Media server CRUD schemas
- LibraryResponse: Library response schema
- InvitationCreate/Response: Invitation CRUD schemas
- IdentityCreate/Response: Identity CRUD schemas
- UserResponse: User response schema
- HealthCheckResponse: Health endpoint response schema

Uses msgspec.Struct for high-performance serialization (10-80x faster than Pydantic).
Validation constraints are defined via Meta annotations.

Request structs use:
- kw_only=True: All fields must be passed as keyword arguments
- forbid_unknown_fields=True: Reject payloads with extra fields

Response structs use:
- omit_defaults=True: Exclude fields with default values from JSON output
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

import msgspec

# =============================================================================
# Reusable Constrained Types
# =============================================================================

# Non-empty string with max length for names and identifiers
NonEmptyStr = Annotated[str, msgspec.Meta(min_length=1, max_length=255)]

# URL string with reasonable max length
UrlStr = Annotated[str, msgspec.Meta(min_length=1, max_length=2048)]

# API key string (may be longer for some services)
ApiKeyStr = Annotated[str, msgspec.Meta(min_length=1, max_length=512)]

# Invitation code (short, unique identifier)
InvitationCode = Annotated[str, msgspec.Meta(min_length=1, max_length=20)]

# Email address (basic pattern validation)
EmailStr = Annotated[
    str, msgspec.Meta(pattern=r"^[\w.-]+@[\w.-]+\.\w+$", max_length=255)
]

# Positive integer for counts and limits
PositiveInt = Annotated[int, msgspec.Meta(gt=0)]

# Non-negative integer for use counts
NonNegativeInt = Annotated[int, msgspec.Meta(ge=0)]

# Username for redemption (lowercase, starts with letter)
Username = Annotated[
    str, msgspec.Meta(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")
]

# Password for redemption (minimum 8 characters)
Password = Annotated[str, msgspec.Meta(min_length=8, max_length=128)]


# =============================================================================
# Error Response Schemas
# =============================================================================


class ErrorResponse(msgspec.Struct, kw_only=True):
    """Standard error response structure.

    All API errors return this structure for consistent client handling.

    Attributes:
        detail: Human-readable error description.
        error_code: Machine-readable error code for programmatic handling.
        timestamp: When the error occurred (UTC).
        correlation_id: Optional unique ID for tracing errors in logs.
    """

    detail: str
    error_code: str
    timestamp: datetime
    correlation_id: str | None = None


class FieldError(msgspec.Struct, kw_only=True):
    """Field-level validation error detail.

    Attributes:
        field: Name of the field that failed validation.
        messages: List of validation error messages for this field.
    """

    field: str
    messages: list[str]


class ValidationErrorResponse(msgspec.Struct, kw_only=True):
    """Validation error response with field-level details.

    Extends ErrorResponse with field-specific error information.

    Attributes:
        detail: Human-readable error description.
        error_code: Always "VALIDATION_ERROR" for this type.
        timestamp: When the error occurred (UTC).
        correlation_id: Optional unique ID for tracing errors in logs.
        field_errors: List of field-level validation errors.
    """

    detail: str
    error_code: str
    timestamp: datetime
    correlation_id: str | None = None
    field_errors: list[FieldError]


# =============================================================================
# Media Server Schemas
# =============================================================================


class MediaServerCreate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create a media server.

    Attributes:
        name: Human-readable name for the server.
        server_type: Type of media server ("jellyfin" or "plex").
        url: Base URL for the media server API.
        api_key: Authentication token for the media server.
    """

    name: NonEmptyStr
    server_type: Annotated[str, msgspec.Meta(pattern=r"^(jellyfin|plex)$")]
    url: UrlStr
    api_key: ApiKeyStr


class MediaServerUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update a media server.

    All fields are optional - only provided fields will be updated.

    Attributes:
        name: Human-readable name for the server.
        url: Base URL for the media server API.
        api_key: Authentication token for the media server.
        enabled: Whether the server is active for user management.
    """

    name: NonEmptyStr | None = None
    url: UrlStr | None = None
    api_key: ApiKeyStr | None = None
    enabled: bool | None = None


class MediaServerResponse(msgspec.Struct, omit_defaults=True):
    """Media server response.

    Attributes:
        id: Unique identifier for the server.
        name: Human-readable name for the server.
        server_type: Type of media server ("jellyfin" or "plex").
        url: Base URL for the media server API.
        enabled: Whether the server is active for user management.
        created_at: When the server was added.
        updated_at: When the server was last modified.
    """

    id: UUID
    name: str
    server_type: str
    url: str
    enabled: bool
    created_at: datetime
    updated_at: datetime | None = None


# =============================================================================
# Library Schemas
# =============================================================================


class LibraryResponse(msgspec.Struct, omit_defaults=True):
    """Library response.

    Attributes:
        id: Unique identifier for the library.
        name: Human-readable name of the library.
        library_type: Type of content (movies, tvshows, music, etc.).
        external_id: The library's ID on the media server.
        created_at: When the library was synced.
        updated_at: When the library was last synced.
    """

    id: UUID
    name: str
    library_type: str
    external_id: str
    created_at: datetime
    updated_at: datetime | None = None


class MediaServerWithLibrariesResponse(msgspec.Struct, omit_defaults=True):
    """Media server response including libraries.

    Attributes:
        id: Unique identifier for the server.
        name: Human-readable name for the server.
        server_type: Type of media server ("jellyfin" or "plex").
        url: Base URL for the media server API.
        enabled: Whether the server is active for user management.
        created_at: When the server was added.
        updated_at: When the server was last modified.
        libraries: List of libraries on this server.
    """

    id: UUID
    name: str
    server_type: str
    url: str
    enabled: bool
    created_at: datetime
    libraries: list[LibraryResponse]
    updated_at: datetime | None = None


# =============================================================================
# Wizard Schemas
# =============================================================================

# Interaction type pattern for validation
InteractionTypeStr = Annotated[
    str, msgspec.Meta(pattern=r"^(click|timer|tos|text_input|quiz)$")
]

# Step order (non-negative integer)
StepOrder = Annotated[int, msgspec.Meta(ge=0)]


class WizardCreate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create a wizard.

    Implements Requirements 2.1: Create wizard via API.

    Attributes:
        name: Human-readable name for the wizard.
        description: Optional detailed description.
        enabled: Whether the wizard is active. Defaults to True.
    """

    name: NonEmptyStr
    description: str | None = None
    enabled: bool = True


class WizardUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update a wizard.

    All fields are optional - only provided fields will be updated.
    Implements Requirements 2.4: Update wizard via API.

    Attributes:
        name: Human-readable name for the wizard.
        description: Optional detailed description.
        enabled: Whether the wizard is active.
    """

    name: NonEmptyStr | None = None
    description: str | None = None
    enabled: bool | None = None


class WizardStepCreate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create a wizard step.

    Implements Requirements 3.1: Create step via API.

    Attributes:
        interaction_type: Type of interaction (click, timer, tos, text_input, quiz).
        title: Display title for the step.
        content_markdown: Markdown content to display.
        config: Type-specific configuration (button_text, duration_seconds, etc.).
        step_order: Position in the wizard sequence. Auto-assigned if not provided.
    """

    interaction_type: InteractionTypeStr
    title: NonEmptyStr
    content_markdown: str
    config: dict[str, str | int | bool | list[str] | None] = {}
    step_order: StepOrder | None = None


class WizardStepUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update a wizard step.

    All fields are optional - only provided fields will be updated.
    Implements Requirements 3.2: Update step via API.

    Attributes:
        title: Display title for the step.
        content_markdown: Markdown content to display.
        config: Type-specific configuration.
    """

    title: NonEmptyStr | None = None
    content_markdown: str | None = None
    config: dict[str, str | int | bool | list[str] | None] | None = None


class StepReorderRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to reorder a wizard step.

    Implements Requirements 3.5: Reorder step via API.

    Attributes:
        new_order: The new position for the step (0-indexed).
    """

    new_order: StepOrder


class StepValidationRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to validate a step completion.

    Implements Requirements 9.1: Validate step completion via API.

    Attributes:
        step_id: The UUID of the step being validated.
        response: Type-specific response data (acknowledged, accepted, text, answer_index).
        started_at: When the step was started (required for timer validation).
    """

    step_id: UUID
    response: dict[str, str | int | bool | None]
    started_at: datetime | None = None


class WizardStepResponse(msgspec.Struct, omit_defaults=True):
    """Wizard step response.

    Implements Requirements 3.1: Step response schema.

    Attributes:
        id: Unique identifier for the step.
        wizard_id: ID of the parent wizard.
        step_order: Position in the wizard sequence.
        interaction_type: Type of interaction.
        title: Display title for the step.
        content_markdown: Markdown content to display.
        config: Type-specific configuration.
        created_at: When the step was created.
        updated_at: When the step was last modified.
    """

    id: UUID
    wizard_id: UUID
    step_order: int
    interaction_type: str
    title: str
    content_markdown: str
    config: dict[str, str | int | bool | list[str] | None]
    created_at: datetime
    updated_at: datetime | None = None


class WizardResponse(msgspec.Struct, omit_defaults=True):
    """Wizard response (without steps).

    Implements Requirements 2.2: Wizard list response schema.

    Attributes:
        id: Unique identifier for the wizard.
        name: Human-readable name for the wizard.
        enabled: Whether the wizard is active.
        created_at: When the wizard was created.
        description: Optional detailed description.
        updated_at: When the wizard was last modified.
    """

    id: UUID
    name: str
    enabled: bool
    created_at: datetime
    description: str | None = None
    updated_at: datetime | None = None


class WizardDetailResponse(msgspec.Struct, omit_defaults=True):
    """Wizard response with steps.

    Implements Requirements 2.3: Wizard detail response schema.

    Attributes:
        id: Unique identifier for the wizard.
        name: Human-readable name for the wizard.
        enabled: Whether the wizard is active.
        created_at: When the wizard was created.
        steps: List of wizard steps in order.
        description: Optional detailed description.
        updated_at: When the wizard was last modified.
    """

    id: UUID
    name: str
    enabled: bool
    created_at: datetime
    steps: list[WizardStepResponse]
    description: str | None = None
    updated_at: datetime | None = None


class WizardListResponse(msgspec.Struct, kw_only=True):
    """Paginated wizard list response.

    Implements Requirements 2.2: Paginated wizard list.

    Attributes:
        items: List of wizards for the current page.
        total: Total number of wizards matching the query.
        page: Current page number (1-indexed).
        page_size: Number of items per page.
        has_next: Whether there are more pages available.
    """

    items: list[WizardResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class StepValidationResponse(msgspec.Struct, kw_only=True):
    """Response from step validation endpoint.

    Implements Requirements 9.5, 9.6: Validation response schema.

    Attributes:
        valid: Whether the step completion was valid.
        completion_token: Token proving completion (only if valid).
        error: Error message (only if invalid).
    """

    valid: bool
    completion_token: str | None = None
    error: str | None = None


# =============================================================================
# Invitation Schemas
# =============================================================================


class CreateInvitationRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create an invitation.

    Attributes:
        server_ids: List of media server IDs this invitation grants access to.
        code: Unique invitation code (if not provided, one will be generated).
        expires_at: Optional expiration timestamp.
        max_uses: Optional maximum number of redemptions.
        duration_days: Optional duration in days for user access after redemption.
        library_ids: Optional list of specific library IDs to grant access to.
        permissions: Optional permission overrides (can_download, can_stream, etc.).
        pre_wizard_id: Optional wizard ID to run before account creation.
        post_wizard_id: Optional wizard ID to run after account creation.
    """

    server_ids: list[UUID]
    code: InvitationCode | None = None
    expires_at: datetime | None = None
    max_uses: PositiveInt | None = None
    duration_days: PositiveInt | None = None
    library_ids: list[UUID] | None = None
    permissions: dict[str, bool] | None = None
    pre_wizard_id: UUID | None = None
    post_wizard_id: UUID | None = None


# Alias for backwards compatibility
InvitationCreate = CreateInvitationRequest


class UpdateInvitationRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update an invitation (mutable fields only).

    All fields are optional - only provided fields will be updated.
    Immutable fields (code, use_count, created_at, created_by) cannot be updated.

    Attributes:
        expires_at: Optional expiration timestamp.
        max_uses: Optional maximum number of redemptions.
        duration_days: Optional duration in days for user access after redemption.
        enabled: Whether the invitation is currently active.
        server_ids: List of media server IDs this invitation grants access to.
        library_ids: Optional list of specific library IDs to grant access to.
        permissions: Optional permission overrides (can_download, can_stream, etc.).
        pre_wizard_id: Optional wizard ID to run before account creation.
        post_wizard_id: Optional wizard ID to run after account creation.
    """

    expires_at: datetime | None = None
    max_uses: PositiveInt | None = None
    duration_days: PositiveInt | None = None
    enabled: bool | None = None
    server_ids: list[UUID] | None = None
    library_ids: list[UUID] | None = None
    permissions: dict[str, bool] | None = None
    pre_wizard_id: UUID | None = None
    post_wizard_id: UUID | None = None


# Alias for backwards compatibility
InvitationUpdate = UpdateInvitationRequest


class InvitationResponse(msgspec.Struct, omit_defaults=True):
    """Invitation response with computed fields.

    Attributes:
        id: Unique identifier for the invitation.
        code: Unique invitation code.
        use_count: Current number of times the invitation has been redeemed.
        enabled: Whether the invitation is currently active.
        created_at: When the invitation was created.
        expires_at: Optional expiration timestamp.
        max_uses: Optional maximum number of redemptions.
        duration_days: Optional duration in days for user access after redemption.
        created_by: Optional identifier of who created the invitation.
        updated_at: When the invitation was last modified.
        is_active: Computed field: enabled AND not expired AND use_count < max_uses.
        remaining_uses: Computed field: max_uses - use_count if max_uses set.
    """

    id: UUID
    code: str
    use_count: int
    enabled: bool
    created_at: datetime
    expires_at: datetime | None = None
    max_uses: int | None = None
    duration_days: int | None = None
    created_by: str | None = None
    updated_at: datetime | None = None
    is_active: bool = True
    remaining_uses: int | None = None


class InvitationDetailResponse(msgspec.Struct, omit_defaults=True):
    """Detailed invitation response including related servers and libraries.

    Attributes:
        id: Unique identifier for the invitation.
        code: Unique invitation code.
        use_count: Current number of times the invitation has been redeemed.
        enabled: Whether the invitation is currently active.
        created_at: When the invitation was created.
        target_servers: List of media servers this invitation grants access to.
        allowed_libraries: List of specific libraries this invitation grants access to.
        expires_at: Optional expiration timestamp.
        max_uses: Optional maximum number of redemptions.
        duration_days: Optional duration in days for user access after redemption.
        created_by: Optional identifier of who created the invitation.
        updated_at: When the invitation was last modified.
        is_active: Computed field: enabled AND not expired AND use_count < max_uses.
        remaining_uses: Computed field: max_uses - use_count if max_uses set.
        pre_wizard: Optional wizard to run before account creation.
        post_wizard: Optional wizard to run after account creation.
    """

    id: UUID
    code: str
    use_count: int
    enabled: bool
    created_at: datetime
    target_servers: list[MediaServerResponse]
    allowed_libraries: list[LibraryResponse]
    expires_at: datetime | None = None
    max_uses: int | None = None
    duration_days: int | None = None
    created_by: str | None = None
    updated_at: datetime | None = None
    is_active: bool = True
    remaining_uses: int | None = None
    pre_wizard: WizardResponse | None = None
    post_wizard: WizardResponse | None = None


class InvitationListResponse(msgspec.Struct, kw_only=True):
    """Paginated invitation list response.

    Attributes:
        items: List of invitations for the current page.
        total: Total number of invitations matching the query.
        page: Current page number (1-indexed).
        page_size: Number of items per page.
        has_next: Whether there are more pages available.
    """

    items: list[InvitationResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


# =============================================================================
# Invitation Validation/Redemption Schemas
# =============================================================================


class InvitationValidationResponse(msgspec.Struct, omit_defaults=True):
    """Response from invitation validation endpoint.

    Attributes:
        valid: Whether the invitation code is valid for redemption.
        failure_reason: Specific reason if invalid (not_found, disabled, expired, max_uses_reached).
        target_servers: List of media servers the invitation grants access to (if valid).
        allowed_libraries: List of specific libraries the invitation grants access to (if valid).
        duration_days: Duration in days for user access after redemption (if valid).
        pre_wizard: Optional wizard to run before account creation (if valid).
        post_wizard: Optional wizard to run after account creation (if valid).
    """

    valid: bool
    failure_reason: str | None = None
    target_servers: list[MediaServerResponse] | None = None
    allowed_libraries: list[LibraryResponse] | None = None
    duration_days: int | None = None
    pre_wizard: WizardDetailResponse | None = None
    post_wizard: WizardDetailResponse | None = None


class RedeemInvitationRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to redeem an invitation.

    Attributes:
        username: Username for the new accounts (3-32 chars, lowercase, starts with letter).
        password: Password for the new accounts (minimum 8 characters).
        email: Optional email address for the identity.
    """

    username: Username
    password: Password
    email: EmailStr | None = None


# =============================================================================
# Identity Schemas
# =============================================================================


class IdentityCreate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create an identity.

    Attributes:
        display_name: Human-readable name for the identity.
        email: Optional email address for notifications.
        expires_at: Optional expiration timestamp.
    """

    display_name: NonEmptyStr
    email: EmailStr | None = None
    expires_at: datetime | None = None


class IdentityUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update an identity.

    All fields are optional - only provided fields will be updated.

    Attributes:
        display_name: Human-readable name for the identity.
        email: Optional email address for notifications.
        expires_at: Optional expiration timestamp.
        enabled: Whether the identity is currently active.
    """

    display_name: NonEmptyStr | None = None
    email: EmailStr | None = None
    expires_at: datetime | None = None
    enabled: bool | None = None


class IdentityResponse(msgspec.Struct, omit_defaults=True):
    """Identity response.

    Attributes:
        id: Unique identifier for the identity.
        display_name: Human-readable name for the identity.
        email: Optional email address for notifications.
        expires_at: Optional expiration timestamp.
        enabled: Whether the identity is currently active.
        created_at: When the identity was created.
        updated_at: When the identity was last modified.
    """

    id: UUID
    display_name: str
    enabled: bool
    created_at: datetime
    email: str | None = None
    expires_at: datetime | None = None
    updated_at: datetime | None = None


# =============================================================================
# User Schemas
# =============================================================================


class UserResponse(msgspec.Struct, omit_defaults=True):
    """User response.

    Attributes:
        id: Unique identifier for the user.
        identity_id: ID of the parent identity.
        media_server_id: ID of the media server.
        external_user_id: The user's ID on the media server.
        username: The username on the media server.
        expires_at: Optional expiration timestamp.
        enabled: Whether the user account is currently active.
        created_at: When the user was created.
        updated_at: When the user was last modified.
    """

    id: UUID
    identity_id: UUID
    media_server_id: UUID
    external_user_id: str
    username: str
    enabled: bool
    created_at: datetime
    expires_at: datetime | None = None
    updated_at: datetime | None = None


class UserDetailResponse(msgspec.Struct, omit_defaults=True):
    """Detailed user response with relationships.

    Includes identity info, media server info, and invitation source
    as required by Requirements 16.4 and 17.1.

    Attributes:
        id: Unique identifier for the user.
        identity_id: ID of the parent identity.
        media_server_id: ID of the media server.
        external_user_id: The user's ID on the media server.
        username: The username on the media server.
        enabled: Whether the user account is currently active.
        created_at: When the user was created.
        identity: The parent identity with all linked users.
        media_server: The media server this user belongs to.
        expires_at: Optional expiration timestamp.
        updated_at: When the user was last modified.
        invitation_id: ID of the invitation used to create this user.
        invitation: The source invitation if available.
    """

    id: UUID
    identity_id: UUID
    media_server_id: UUID
    external_user_id: str
    username: str
    enabled: bool
    created_at: datetime
    identity: IdentityResponse
    media_server: MediaServerResponse
    expires_at: datetime | None = None
    updated_at: datetime | None = None
    invitation_id: UUID | None = None
    invitation: InvitationResponse | None = None


class UserListResponse(msgspec.Struct, kw_only=True):
    """Paginated user list response.

    Supports pagination as required by Requirement 16.1.

    Attributes:
        items: List of users for the current page.
        total: Total number of users matching the query.
        page: Current page number (1-indexed).
        page_size: Number of items per page.
        has_next: Whether there are more pages available.
    """

    items: list[UserDetailResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


# Sort field options for user listing
UserSortField = Annotated[
    str, msgspec.Meta(pattern=r"^(created_at|username|expires_at)$")
]

# Sort order options
SortOrder = Annotated[str, msgspec.Meta(pattern=r"^(asc|desc)$")]

# Page number (1-indexed, positive)
PageNumber = Annotated[int, msgspec.Meta(ge=1)]

# Page size (1-100, with default 50 as per Requirement 16.6)
PageSize = Annotated[int, msgspec.Meta(ge=1, le=100)]


class UserListFilters(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Filters for user listing.

    Supports filtering by media_server_id, invitation_id, enabled status,
    and expiration status as required by Requirement 16.2.
    Supports sorting by created_at, username, and expires_at as required
    by Requirement 16.3.

    Attributes:
        media_server_id: Filter by media server ID.
        invitation_id: Filter by invitation ID.
        enabled: Filter by enabled status.
        expired: Filter by expiration status (True = expired, False = not expired).
        sort_by: Field to sort by (created_at, username, expires_at).
        sort_order: Sort direction (asc, desc).
        page: Page number (1-indexed).
        page_size: Number of items per page (max 100, default 50).
    """

    media_server_id: UUID | None = None
    invitation_id: UUID | None = None
    enabled: bool | None = None
    expired: bool | None = None
    sort_by: UserSortField = "created_at"
    sort_order: SortOrder = "desc"
    page: PageNumber = 1
    page_size: PageSize = 50


class UpdatePermissionsRequest(
    msgspec.Struct, kw_only=True, forbid_unknown_fields=True
):
    """Request to update user permissions on the media server.

    Maps to universal permission names that are translated to server-specific
    settings by the media client implementations.

    Attributes:
        can_download: Whether the user can download content.
        can_stream: Whether the user can stream/play content.
        can_sync: Whether the user can sync content for offline use.
        can_transcode: Whether the user can use transcoding.
    """

    can_download: bool | None = None
    can_stream: bool | None = None
    can_sync: bool | None = None
    can_transcode: bool | None = None


class IdentityWithUsersResponse(msgspec.Struct, omit_defaults=True):
    """Identity response including linked users.

    Attributes:
        id: Unique identifier for the identity.
        display_name: Human-readable name for the identity.
        email: Optional email address for notifications.
        expires_at: Optional expiration timestamp.
        enabled: Whether the identity is currently active.
        created_at: When the identity was created.
        updated_at: When the identity was last modified.
        users: List of media server accounts linked to this identity.
    """

    id: UUID
    display_name: str
    enabled: bool
    created_at: datetime
    users: list[UserResponse]
    email: str | None = None
    expires_at: datetime | None = None
    updated_at: datetime | None = None


# =============================================================================
# Redemption Response Schemas
# =============================================================================


class RedemptionResponse(msgspec.Struct, omit_defaults=True):
    """Response from successful invitation redemption.

    Attributes:
        success: Always True for successful redemption.
        identity_id: ID of the created identity.
        users_created: List of users created on each target server.
        message: Optional success message.
    """

    success: bool
    identity_id: UUID
    users_created: list[UserResponse]
    message: str | None = None


class RedemptionErrorResponse(msgspec.Struct, kw_only=True):
    """Response from failed invitation redemption.

    Attributes:
        success: Always False for failed redemption.
        error_code: Machine-readable error code (e.g., USERNAME_TAKEN, SERVER_ERROR).
        message: Human-readable error description.
        failed_server: Name of the server that failed (if applicable).
        partial_users: List of users that were created before failure (for rollback info).
    """

    success: bool = False
    error_code: str
    message: str
    failed_server: str | None = None
    partial_users: list[UserResponse] | None = None


# =============================================================================
# Health Check Schemas
# =============================================================================


class HealthCheckResponse(msgspec.Struct, kw_only=True):
    """Health check response.

    Attributes:
        status: Overall health status ("healthy" or "degraded").
        checks: Individual dependency check results.
    """

    status: str
    checks: dict[str, bool]


class LivenessResponse(msgspec.Struct, kw_only=True):
    """Liveness probe response.

    Attributes:
        status: Always "alive" if the process is running.
    """

    status: str


class ReadinessResponse(msgspec.Struct, kw_only=True):
    """Readiness probe response.

    Attributes:
        status: "ready" if the application can serve traffic, "not ready" otherwise.
    """

    status: str


# =============================================================================
# Connection Test Schemas
# =============================================================================


class ConnectionTestRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to test a media server connection.

    Attributes:
        server_type: Type of media server ("jellyfin" or "plex").
        url: Base URL for the media server API.
        api_key: Authentication token for the media server.
    """

    server_type: Annotated[str, msgspec.Meta(pattern=r"^(jellyfin|plex)$")]
    url: UrlStr
    api_key: ApiKeyStr


class ConnectionTestResponse(msgspec.Struct, kw_only=True):
    """Response from a media server connection test.

    Attributes:
        success: Whether the connection test succeeded.
        message: Human-readable result message.
        server_name: Name of the server (if connection succeeded).
        version: Server version (if connection succeeded).
    """

    success: bool
    message: str
    server_name: str | None = None
    version: str | None = None


# =============================================================================
# Authentication Schemas
# =============================================================================

# Admin username: 3-32 chars, lowercase, starts with letter
AdminUsername = Annotated[
    str, msgspec.Meta(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")
]

# Admin password: 15+ chars for strong security
AdminPassword = Annotated[str, msgspec.Meta(min_length=15, max_length=128)]


class AuthMethodsResponse(msgspec.Struct, kw_only=True):
    """Response listing available authentication methods.

    Attributes:
        methods: List of available auth methods (local, plex, jellyfin).
        setup_required: True if no admin accounts exist yet.
    """

    methods: list[str]
    setup_required: bool


class AdminSetupRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create the first admin account.

    Attributes:
        username: Admin username (3-32 chars, lowercase).
        password: Admin password (15+ chars).
        email: Optional email address.
    """

    username: AdminUsername
    password: AdminPassword
    email: EmailStr | None = None


class LoginRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Local username/password login request.

    Attributes:
        username: Admin username.
        password: Admin password.
    """

    username: str
    password: str


class PlexLoginRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Plex OAuth token login request.

    Attributes:
        auth_token: Plex auth token from OAuth flow.
    """

    auth_token: str


class JellyfinLoginRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Jellyfin credential login request.

    Attributes:
        server_url: Jellyfin server URL.
        username: Jellyfin username.
        password: Jellyfin password.
    """

    server_url: UrlStr
    username: str
    password: str


class RefreshRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Refresh token request.

    Attributes:
        refresh_token: The refresh token string.
    """

    refresh_token: str


class AdminMeResponse(msgspec.Struct, kw_only=True):
    """Current admin info response.

    Attributes:
        id: Admin account UUID.
        username: Admin username.
        email: Optional email address.
        auth_method: Authentication method used.
    """

    id: UUID
    username: str
    email: str | None = None
    auth_method: str = "local"


class AuthTokenResponse(msgspec.Struct, kw_only=True):
    """Authentication token response.

    Attributes:
        refresh_token: Refresh token for obtaining new access tokens.
    """

    refresh_token: str


# =============================================================================
# Sync Schemas
# =============================================================================


class SyncRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to sync a server (optional parameters).

    Attributes:
        dry_run: If True, only report discrepancies without making changes.
            Defaults to True for safety.
    """

    dry_run: bool = True


class SyncResult(msgspec.Struct, kw_only=True):
    """Result of a server sync operation.

    Reports discrepancies between local user records and the actual
    state of users on the media server.

    Attributes:
        server_id: ID of the media server that was synced.
        server_name: Name of the media server.
        synced_at: Timestamp when the sync was performed.
        orphaned_users: Usernames that exist on the server but not locally.
        stale_users: Usernames that exist locally but not on the server.
        matched_users: Count of users that match between local and server.
        imported_users: Count of orphaned users imported into local DB.
    """

    server_id: UUID
    server_name: str
    synced_at: datetime
    orphaned_users: list[str]
    stale_users: list[str]
    matched_users: int
    imported_users: int = 0


# =============================================================================
# Plex OAuth Schemas
# =============================================================================


class PlexOAuthPinResponse(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Response from Plex OAuth PIN creation.

    Implements Requirements 13.2: PIN creation returns valid response.

    Attributes:
        pin_id: The PIN identifier for status checking.
        code: The PIN code to display to the user.
        auth_url: URL where user authenticates (plex.tv/link).
        expires_at: When the PIN expires.
    """

    pin_id: int
    code: str
    auth_url: str
    expires_at: datetime


class PlexOAuthCheckResponse(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Response from Plex OAuth PIN status check.

    Implements Requirements 14.2, 14.3: PIN verification returns status and email.

    Attributes:
        authenticated: Whether the PIN has been authenticated.
        email: User's Plex email (only if authenticated).
        error: Error message (only if failed).
    """

    authenticated: bool
    auth_token: str | None = None
    email: str | None = None
    error: str | None = None
