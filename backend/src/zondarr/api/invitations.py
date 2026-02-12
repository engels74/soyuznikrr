"""InvitationController for invitation management endpoints.

Provides REST endpoints for invitation CRUD operations:
- POST /api/v1/invitations - Create a new invitation
- GET /api/v1/invitations - List invitations with pagination
- GET /api/v1/invitations/{id} - Get invitation details
- PATCH /api/v1/invitations/{id} - Update an invitation
- DELETE /api/v1/invitations/{id} - Delete an invitation
- GET /api/v1/invitations/validate/{code} - Validate an invitation code (public)

Uses Litestar Controller pattern with dependency injection for services.
Implements Requirements 9.1, 10.1, 10.4, 11.1, 12.1, 13.1-13.6.
"""

from collections.abc import Mapping, Sequence
from typing import Annotated
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Parameter
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT
from litestar.types import AnyCallable
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.media.registry import registry
from zondarr.models.invitation import Invitation
from zondarr.models.wizard import Wizard, WizardStep
from zondarr.repositories.invitation import InvitationRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.services.invitation import InvitationService, InvitationValidationFailure

from .schemas import (
    CreateInvitationRequest,
    InvitationDetailResponse,
    InvitationListResponse,
    InvitationResponse,
    InvitationValidationResponse,
    LibraryResponse,
    MediaServerResponse,
    UpdateInvitationRequest,
    WizardDetailResponse,
    WizardResponse,
    WizardStepResponse,
)


async def provide_invitation_repository(
    session: AsyncSession,
) -> InvitationRepository:
    """Provide InvitationRepository instance.

    Args:
        session: Database session from DI.

    Returns:
        Configured InvitationRepository instance.
    """
    return InvitationRepository(session)


async def provide_media_server_repository(
    session: AsyncSession,
) -> MediaServerRepository:
    """Provide MediaServerRepository instance.

    Args:
        session: Database session from DI.

    Returns:
        Configured MediaServerRepository instance.
    """
    return MediaServerRepository(session)


async def provide_invitation_service(
    invitation_repository: InvitationRepository,
    server_repository: MediaServerRepository,
) -> InvitationService:
    """Provide InvitationService instance.

    Args:
        invitation_repository: InvitationRepository from DI.
        server_repository: MediaServerRepository from DI.

    Returns:
        Configured InvitationService instance.
    """
    return InvitationService(
        invitation_repository,
        server_repository=server_repository,
    )


class InvitationController(Controller):
    """Controller for invitation management endpoints.

    Provides CRUD operations for invitations and a public validation endpoint.
    All endpoints except validation require authentication.
    """

    path: str = "/api/v1/invitations"
    tags: Sequence[str] | None = ["Invitations"]
    dependencies: Mapping[str, Provide | AnyCallable] | None = {
        "invitation_repository": Provide(provide_invitation_repository),
        "server_repository": Provide(provide_media_server_repository),
        "invitation_service": Provide(provide_invitation_service),
    }

    @post(
        "/",
        status_code=HTTP_201_CREATED,
        summary="Create invitation",
        description="Create a new invitation with configurable settings.",
    )
    async def create_invitation(
        self,
        data: CreateInvitationRequest,
        invitation_service: InvitationService,
    ) -> InvitationDetailResponse:
        """Create a new invitation.

        Creates an invitation with the specified configuration. If no code
        is provided, a cryptographically secure 12-character code is generated.

        Args:
            data: The invitation creation request.
            invitation_service: InvitationService from DI.

        Returns:
            The created invitation with full details.

        Raises:
            ValidationError: If server_ids or library_ids are invalid.
        """
        invitation = await invitation_service.create(
            code=data.code,
            expires_at=data.expires_at,
            max_uses=data.max_uses,
            duration_days=data.duration_days,
            server_ids=data.server_ids,
            library_ids=data.library_ids,
            pre_wizard_id=data.pre_wizard_id,
            post_wizard_id=data.post_wizard_id,
        )

        return self._to_detail_response(invitation, invitation_service)

    @get(
        "/",
        summary="List invitations",
        description="List invitations with pagination, filtering, and sorting.",
    )
    async def list_invitations(
        self,
        invitation_repository: InvitationRepository,
        invitation_service: InvitationService,
        page: Annotated[
            int,
            Parameter(
                ge=1,
                description="Page number (1-indexed)",
            ),
        ] = 1,
        page_size: Annotated[
            int,
            Parameter(
                ge=1,
                le=100,
                description="Number of items per page (max 100)",
            ),
        ] = 50,
        enabled: Annotated[
            bool | None,
            Parameter(description="Filter by enabled status"),
        ] = None,
        expired: Annotated[
            bool | None,
            Parameter(description="Filter by expiration status"),
        ] = None,
        sort_by: Annotated[
            str,
            Parameter(
                description="Field to sort by (created_at, expires_at, use_count)",
            ),
        ] = "created_at",
        sort_order: Annotated[
            str,
            Parameter(description="Sort order (asc, desc)"),
        ] = "desc",
    ) -> InvitationListResponse:
        """List invitations with pagination.

        Supports filtering by enabled status and expiration status,
        with configurable sorting and pagination.

        Args:
            invitation_repository: InvitationRepository from DI.
            invitation_service: InvitationService from DI.
            page: Page number (1-indexed).
            page_size: Number of items per page.
            enabled: Filter by enabled status.
            expired: Filter by expiration status.
            sort_by: Field to sort by.
            sort_order: Sort direction.

        Returns:
            Paginated list of invitations.
        """
        # Validate sort_by parameter
        valid_sort_fields = {"created_at", "expires_at", "use_count"}
        if sort_by not in valid_sort_fields:
            sort_by = "created_at"

        # Validate sort_order parameter
        if sort_order not in {"asc", "desc"}:
            sort_order = "desc"

        items, total = await invitation_repository.list_paginated(
            page=page,
            page_size=page_size,
            enabled=enabled,
            expired=expired,
            sort_by=sort_by,  # pyright: ignore[reportArgumentType]
            sort_order=sort_order,  # pyright: ignore[reportArgumentType]
        )

        response_items = [
            self._to_response(invitation, invitation_service) for invitation in items
        ]

        return InvitationListResponse(
            items=response_items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
        )

    @get(
        "/{invitation_id:uuid}",
        summary="Get invitation details",
        description="Retrieve complete details for a specific invitation.",
    )
    async def get_invitation(
        self,
        invitation_id: Annotated[
            UUID,
            Parameter(description="Invitation UUID"),
        ],
        invitation_service: InvitationService,
    ) -> InvitationDetailResponse:
        """Get invitation details by ID.

        Args:
            invitation_id: The UUID of the invitation.
            invitation_service: InvitationService from DI.

        Returns:
            Complete invitation details including relationships.

        Raises:
            NotFoundError: If the invitation does not exist.
        """
        invitation = await invitation_service.get_by_id(invitation_id)
        return self._to_detail_response(invitation, invitation_service)

    @patch(
        "/{invitation_id:uuid}",
        summary="Update invitation",
        description="Update mutable fields of an invitation.",
    )
    async def update_invitation(
        self,
        invitation_id: Annotated[
            UUID,
            Parameter(description="Invitation UUID"),
        ],
        data: UpdateInvitationRequest,
        invitation_service: InvitationService,
    ) -> InvitationDetailResponse:
        """Update an invitation.

        Only mutable fields can be updated:
        - expires_at, max_uses, duration_days, enabled, server_ids, library_ids,
          pre_wizard_id, post_wizard_id

        Immutable fields are protected:
        - code, use_count, created_at, created_by

        Args:
            invitation_id: The UUID of the invitation.
            data: The update request with fields to modify.
            invitation_service: InvitationService from DI.

        Returns:
            The updated invitation with full details.

        Raises:
            NotFoundError: If the invitation does not exist.
            ValidationError: If server_ids or library_ids are invalid.
        """
        invitation = await invitation_service.update(
            invitation_id,
            expires_at=data.expires_at,
            max_uses=data.max_uses,
            duration_days=data.duration_days,
            enabled=data.enabled,
            server_ids=data.server_ids,
            library_ids=data.library_ids,
            pre_wizard_id=data.pre_wizard_id,
            post_wizard_id=data.post_wizard_id,
        )

        return self._to_detail_response(invitation, invitation_service)

    @delete(
        "/{invitation_id:uuid}",
        status_code=HTTP_204_NO_CONTENT,
        summary="Delete invitation",
        description="Delete an invitation without affecting users created from it.",
    )
    async def delete_invitation(
        self,
        invitation_id: Annotated[
            UUID,
            Parameter(description="Invitation UUID"),
        ],
        invitation_service: InvitationService,
    ) -> None:
        """Delete an invitation.

        Removes the invitation from the database. Users created from this
        invitation are preserved.

        Args:
            invitation_id: The UUID of the invitation.
            invitation_service: InvitationService from DI.

        Raises:
            NotFoundError: If the invitation does not exist.
        """
        await invitation_service.delete(invitation_id)

    @get(
        "/validate/{code:str}",
        summary="Validate invitation code",
        description="Validate an invitation code without redeeming it. Public endpoint.",
        exclude_from_auth=True,
    )
    async def validate_invitation(
        self,
        code: Annotated[
            str,
            Parameter(description="Invitation code to validate"),
        ],
        invitation_service: InvitationService,
    ) -> InvitationValidationResponse:
        """Validate an invitation code.

        Checks all validation conditions without incrementing use count:
        1. Code exists
        2. Invitation is enabled
        3. Invitation has not expired
        4. Invitation has not reached max uses

        This endpoint is publicly accessible without authentication.

        Args:
            code: The invitation code to validate.
            invitation_service: InvitationService from DI.

        Returns:
            Validation result with failure reason if invalid,
            or target servers, libraries, and wizards if valid.
        """
        is_valid, failure_reason = await invitation_service.validate(code)

        if not is_valid:
            return InvitationValidationResponse(
                valid=False,
                failure_reason=self._failure_reason_to_string(failure_reason),
            )

        # Get invitation details for valid response
        invitation = await invitation_service.get_by_code(code)

        target_servers = [
            MediaServerResponse(
                id=server.id,
                name=server.name,
                server_type=server.server_type.value,
                url=server.url,
                enabled=server.enabled,
                created_at=server.created_at,
                updated_at=server.updated_at,
                supported_permissions=sorted(
                    registry.get_supported_permissions(server.server_type)
                ),
            )
            for server in invitation.target_servers
        ]

        allowed_libraries = [
            LibraryResponse(
                id=lib.id,
                name=lib.name,
                library_type=lib.library_type,
                external_id=lib.external_id,
                created_at=lib.created_at,
                updated_at=lib.updated_at,
            )
            for lib in invitation.allowed_libraries
        ]

        # Convert wizards to response format
        pre_wizard = self._wizard_to_detail_response(invitation.pre_wizard)
        post_wizard = self._wizard_to_detail_response(invitation.post_wizard)

        return InvitationValidationResponse(
            valid=True,
            target_servers=target_servers if target_servers else None,
            allowed_libraries=allowed_libraries if allowed_libraries else None,
            duration_days=invitation.duration_days,
            pre_wizard=pre_wizard,
            post_wizard=post_wizard,
        )

    def _to_response(
        self,
        invitation: Invitation,
        invitation_service: InvitationService,
        /,
    ) -> InvitationResponse:
        """Convert an Invitation entity to InvitationResponse.

        Args:
            invitation: The Invitation entity.
            invitation_service: InvitationService for computed fields.

        Returns:
            InvitationResponse with computed fields.
        """
        return InvitationResponse(
            id=invitation.id,
            code=invitation.code,
            use_count=invitation.use_count,
            enabled=invitation.enabled,
            created_at=invitation.created_at,
            expires_at=invitation.expires_at,
            max_uses=invitation.max_uses,
            duration_days=invitation.duration_days,
            created_by=invitation.created_by,
            updated_at=invitation.updated_at,
            is_active=invitation_service.is_active(invitation),
            remaining_uses=invitation_service.remaining_uses(invitation),
        )

    def _to_detail_response(
        self,
        invitation: Invitation,
        invitation_service: InvitationService,
        /,
    ) -> InvitationDetailResponse:
        """Convert an Invitation entity to InvitationDetailResponse.

        Args:
            invitation: The Invitation entity.
            invitation_service: InvitationService for computed fields.

        Returns:
            InvitationDetailResponse with relationships and computed fields.
        """
        target_servers = [
            MediaServerResponse(
                id=server.id,
                name=server.name,
                server_type=server.server_type.value,
                url=server.url,
                enabled=server.enabled,
                created_at=server.created_at,
                updated_at=server.updated_at,
                supported_permissions=sorted(
                    registry.get_supported_permissions(server.server_type)
                ),
            )
            for server in invitation.target_servers
        ]

        allowed_libraries = [
            LibraryResponse(
                id=lib.id,
                name=lib.name,
                library_type=lib.library_type,
                external_id=lib.external_id,
                created_at=lib.created_at,
                updated_at=lib.updated_at,
            )
            for lib in invitation.allowed_libraries
        ]

        # Convert wizards to response format
        pre_wizard = self._wizard_to_response(invitation.pre_wizard)
        post_wizard = self._wizard_to_response(invitation.post_wizard)

        return InvitationDetailResponse(
            id=invitation.id,
            code=invitation.code,
            use_count=invitation.use_count,
            enabled=invitation.enabled,
            created_at=invitation.created_at,
            target_servers=target_servers,
            allowed_libraries=allowed_libraries,
            expires_at=invitation.expires_at,
            max_uses=invitation.max_uses,
            duration_days=invitation.duration_days,
            created_by=invitation.created_by,
            updated_at=invitation.updated_at,
            is_active=invitation_service.is_active(invitation),
            remaining_uses=invitation_service.remaining_uses(invitation),
            pre_wizard=pre_wizard,
            post_wizard=post_wizard,
        )

    def _wizard_to_response(self, wizard: Wizard | None, /) -> WizardResponse | None:
        """Convert a Wizard entity to WizardResponse.

        Args:
            wizard: The Wizard entity or None.

        Returns:
            WizardResponse or None if wizard is None.
        """
        if wizard is None:
            return None

        return WizardResponse(
            id=wizard.id,
            name=wizard.name,
            enabled=wizard.enabled,
            created_at=wizard.created_at,
            description=wizard.description,
            updated_at=wizard.updated_at,
        )

    def _wizard_to_detail_response(
        self, wizard: Wizard | None, /
    ) -> WizardDetailResponse | None:
        """Convert a Wizard entity to WizardDetailResponse with steps.

        Args:
            wizard: The Wizard entity or None.

        Returns:
            WizardDetailResponse with steps or None if wizard is None.
        """
        if wizard is None:
            return None

        steps = [self._step_to_response(step) for step in wizard.steps]

        return WizardDetailResponse(
            id=wizard.id,
            name=wizard.name,
            enabled=wizard.enabled,
            created_at=wizard.created_at,
            steps=steps,
            description=wizard.description,
            updated_at=wizard.updated_at,
        )

    def _step_to_response(self, step: WizardStep, /) -> WizardStepResponse:
        """Convert a WizardStep entity to WizardStepResponse.

        Args:
            step: The WizardStep entity.

        Returns:
            WizardStepResponse.
        """
        interaction_type = step.interaction_type
        if hasattr(interaction_type, "value"):
            interaction_type = interaction_type.value
        return WizardStepResponse(
            id=step.id,
            wizard_id=step.wizard_id,
            step_order=step.step_order,
            interaction_type=interaction_type,
            title=step.title,
            content_markdown=step.content_markdown,
            config=step.config,
            created_at=step.created_at,
            updated_at=step.updated_at,
        )

    def _failure_reason_to_string(
        self,
        failure_reason: InvitationValidationFailure | None,
        /,
    ) -> str:
        """Convert a validation failure reason to a string.

        Args:
            failure_reason: The failure reason enum value.

        Returns:
            String representation of the failure reason.
        """
        if failure_reason is None:
            return "unknown"
        return failure_reason.value
