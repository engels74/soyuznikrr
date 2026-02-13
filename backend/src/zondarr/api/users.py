"""UserController for user management endpoints.

Provides REST endpoints for user listing, detail retrieval, and management:
- GET /api/v1/users - List users with pagination, filtering, sorting
- GET /api/v1/users/{id} - Get user details with relationships
- POST /api/v1/users/{id}/enable - Enable a user
- POST /api/v1/users/{id}/disable - Disable a user
- DELETE /api/v1/users/{id} - Delete a user

Uses Litestar Controller pattern with dependency injection for services.
Implements Requirements 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 17.1, 17.2, 17.3, 17.4, 17.5,
18.1, 18.2, 18.5, 18.6, 19.1, 19.6, 19.7.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Parameter
from litestar.types import AnyCallable
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.media.registry import registry
from zondarr.models.identity import User
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.user import UserService

from .schemas import (
    IdentityResponse,
    InvitationResponse,
    MediaServerResponse,
    UpdatePermissionsRequest,
    UserDetailResponse,
    UserListResponse,
)


async def provide_user_repository(
    session: AsyncSession,
) -> UserRepository:
    """Provide UserRepository instance.

    Args:
        session: Database session from DI.

    Returns:
        Configured UserRepository instance.
    """
    return UserRepository(session)


async def provide_identity_repository(
    session: AsyncSession,
) -> IdentityRepository:
    """Provide IdentityRepository instance.

    Args:
        session: Database session from DI.

    Returns:
        Configured IdentityRepository instance.
    """
    return IdentityRepository(session)


async def provide_user_service(
    user_repository: UserRepository,
    identity_repository: IdentityRepository,
) -> UserService:
    """Provide UserService instance.

    Args:
        user_repository: UserRepository from DI.
        identity_repository: IdentityRepository from DI.

    Returns:
        Configured UserService instance.
    """
    return UserService(
        user_repository,
        identity_repository,
    )


class UserController(Controller):
    """Controller for user management endpoints.

    Provides list and detail endpoints for users with pagination,
    filtering, and sorting support. All endpoints require authentication.
    """

    path: str = "/api/v1/users"
    tags: Sequence[str] | None = ["Users"]
    dependencies: Mapping[str, Provide | AnyCallable] | None = {
        "user_repository": Provide(provide_user_repository),
        "identity_repository": Provide(provide_identity_repository),
        "user_service": Provide(provide_user_service),
    }

    @get(
        "/",
        summary="List users",
        description="List users with pagination, filtering, and sorting.",
    )
    async def list_users(
        self,
        user_service: UserService,
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
                description="Number of items per page (default 50, max 100)",
            ),
        ] = 50,
        server_id: Annotated[
            UUID | None,
            Parameter(
                description="Filter by media server ID",
                query="server_id",
            ),
        ] = None,
        invitation_id: Annotated[
            UUID | None,
            Parameter(
                description="Filter by invitation ID",
                query="invitation_id",
            ),
        ] = None,
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
                description="Field to sort by (created_at, username, expires_at)",
            ),
        ] = "created_at",
        sort_order: Annotated[
            str,
            Parameter(description="Sort order (asc, desc)"),
        ] = "desc",
    ) -> UserListResponse:
        """List users with pagination.

        Supports filtering by media_server_id, invitation_id, enabled status,
        and expiration status. Supports sorting by created_at, username, and
        expires_at. Enforces page_size max of 100 (Requirement 16.6).

        Args:
            user_service: UserService from DI.
            page: Page number (1-indexed). Defaults to 1.
            page_size: Number of items per page. Defaults to 50, max 100.
            server_id: Filter by media server ID.
            invitation_id: Filter by invitation ID.
            enabled: Filter by enabled status.
            expired: Filter by expiration status.
            sort_by: Field to sort by.
            sort_order: Sort direction.

        Returns:
            Paginated list of users with relationships.
        """
        # Validate sort_by parameter (Requirement 16.3)
        valid_sort_fields = {"created_at", "username", "expires_at"}
        if sort_by not in valid_sort_fields:
            sort_by = "created_at"

        # Validate sort_order parameter
        if sort_order not in {"asc", "desc"}:
            sort_order = "desc"

        # Enforce page_size max of 100 (Requirement 16.6)
        # The Parameter annotation already enforces le=100, but the service
        # also caps it for defense in depth
        capped_page_size = min(page_size, 100)

        items, total = await user_service.list_users(
            page=page,
            page_size=capped_page_size,
            media_server_id=server_id,
            invitation_id=invitation_id,
            enabled=enabled,
            expired=expired,
            sort_by=sort_by,  # pyright: ignore[reportArgumentType]
            sort_order=sort_order,  # pyright: ignore[reportArgumentType]
        )

        response_items = [self._to_detail_response(user) for user in items]

        return UserListResponse(
            items=response_items,
            total=total,
            page=page,
            page_size=capped_page_size,
            has_next=(page * capped_page_size) < total,
        )

    @get(
        "/{user_id:uuid}",
        summary="Get user details",
        description="Retrieve complete details for a specific user.",
    )
    async def get_user(
        self,
        user_id: Annotated[
            UUID,
            Parameter(description="User UUID"),
        ],
        user_service: UserService,
    ) -> UserDetailResponse:
        """Get user details by ID.

        Returns complete user details including:
        - Parent Identity with all linked Users (Requirement 17.2)
        - Source Invitation if available (Requirement 17.3)
        - Media Server details (Requirement 17.4)

        Args:
            user_id: The UUID of the user.
            user_service: UserService from DI.

        Returns:
            Complete user details including relationships.

        Raises:
            NotFoundError: If the user does not exist (Requirement 17.5).
        """
        user = await user_service.get_user_detail(user_id)
        return self._to_detail_response(user)

    @post(
        "/{user_id:uuid}/enable",
        summary="Enable user",
        description="Enable a user account on both local database and media server.",
    )
    async def enable_user(
        self,
        user_id: Annotated[
            UUID,
            Parameter(description="User UUID"),
        ],
        user_service: UserService,
    ) -> UserDetailResponse:
        """Enable a user account.

        Enables the user on the external media server first, then updates
        the local record. Returns the updated user details.

        Implements Requirements 18.1, 18.5, 18.6.

        Args:
            user_id: The UUID of the user to enable.
            user_service: UserService from DI.

        Returns:
            Updated user details including relationships.

        Raises:
            NotFoundError: If the user does not exist (Requirement 18.6).
            ValidationError: If the media server operation fails.
        """
        user = await user_service.set_enabled(user_id, enabled=True)
        # Reload with full relationships for response
        user = await user_service.get_user_detail(user_id)
        return self._to_detail_response(user)

    @post(
        "/{user_id:uuid}/disable",
        summary="Disable user",
        description="Disable a user account on both local database and media server.",
    )
    async def disable_user(
        self,
        user_id: Annotated[
            UUID,
            Parameter(description="User UUID"),
        ],
        user_service: UserService,
    ) -> UserDetailResponse:
        """Disable a user account.

        Disables the user on the external media server first, then updates
        the local record. Returns the updated user details.

        Implements Requirements 18.2, 18.5, 18.6.

        Args:
            user_id: The UUID of the user to disable.
            user_service: UserService from DI.

        Returns:
            Updated user details including relationships.

        Raises:
            NotFoundError: If the user does not exist (Requirement 18.6).
            ValidationError: If the media server operation fails.
        """
        user = await user_service.set_enabled(user_id, enabled=False)
        # Reload with full relationships for response
        user = await user_service.get_user_detail(user_id)
        return self._to_detail_response(user)

    @patch(
        "/{user_id:uuid}/permissions",
        summary="Update user permissions",
        description="Update user permissions on the media server.",
    )
    async def update_permissions(
        self,
        user_id: Annotated[
            UUID,
            Parameter(description="User UUID"),
        ],
        data: UpdatePermissionsRequest,
        user_service: UserService,
    ) -> UserDetailResponse:
        """Update user permissions on the media server.

        Updates the specified permissions on the external media server.
        Only provided permissions are changed; others remain unchanged.

        Args:
            user_id: The UUID of the user to update.
            data: UpdatePermissionsRequest with permission values.
            user_service: UserService from DI.

        Returns:
            Updated user details including relationships.

        Raises:
            NotFoundError: If the user does not exist.
            ValidationError: If no valid permissions provided or media server fails.
        """
        # Build permissions dict from request, excluding None values
        permissions: dict[str, bool] = {}
        if data.can_download is not None:
            permissions["can_download"] = data.can_download
        if data.can_stream is not None:
            permissions["can_stream"] = data.can_stream
        if data.can_sync is not None:
            permissions["can_sync"] = data.can_sync
        if data.can_transcode is not None:
            permissions["can_transcode"] = data.can_transcode

        _ = await user_service.update_permissions(user_id, permissions=permissions)
        # Reload with full relationships for response
        user = await user_service.get_user_detail(user_id)
        return self._to_detail_response(user)

    @delete(
        "/{user_id:uuid}",
        status_code=204,
        summary="Delete user",
        description="Delete a user from both local database and media server.",
    )
    async def delete_user(
        self,
        user_id: Annotated[
            UUID,
            Parameter(description="User UUID"),
        ],
        user_service: UserService,
    ) -> None:
        """Delete a user account.

        Deletes the user from the external media server first, then deletes
        the local record. If this is the last user for an identity, the
        identity is also deleted.

        Implements Requirements 19.1, 19.6, 19.7.

        Args:
            user_id: The UUID of the user to delete.
            user_service: UserService from DI.

        Returns:
            None (HTTP 204 No Content on success).

        Raises:
            NotFoundError: If the user does not exist (Requirement 19.7).
            ValidationError: If the media server operation fails.
        """
        await user_service.delete(user_id)

    def _to_detail_response(self, user: User, /) -> UserDetailResponse:
        """Convert a User entity to UserDetailResponse.

        Args:
            user: The User entity with relationships loaded.

        Returns:
            UserDetailResponse with all relationship data.
        """
        # Build identity response (Requirement 17.2)
        identity_response = IdentityResponse(
            id=user.identity.id,
            display_name=user.identity.display_name,
            enabled=user.identity.enabled,
            created_at=user.identity.created_at,
            email=user.identity.email,
            expires_at=user.identity.expires_at,
            updated_at=user.identity.updated_at,
        )

        # Build media server response (Requirement 17.4)
        media_server_response = MediaServerResponse(
            id=user.media_server.id,
            name=user.media_server.name,
            server_type=user.media_server.server_type,
            url=user.media_server.url,
            enabled=user.media_server.enabled,
            created_at=user.media_server.created_at,
            updated_at=user.media_server.updated_at,
            supported_permissions=sorted(
                registry.get_supported_permissions(user.media_server.server_type)
            ),
        )

        # Build invitation response if available (Requirement 17.3)
        invitation_response: InvitationResponse | None = None
        if user.invitation is not None:
            inv = user.invitation
            is_active = inv.enabled
            if is_active and inv.expires_at is not None:
                # Compare naive-to-naive: DB column is DateTime without
                # timezone, so expires_at comes back naive from the ORM.
                now_utc = datetime.now(UTC).replace(tzinfo=None)
                is_active = inv.expires_at > now_utc
            if is_active and inv.max_uses is not None:
                is_active = inv.use_count < inv.max_uses
            remaining_uses = (
                max(0, inv.max_uses - inv.use_count)
                if inv.max_uses is not None
                else None
            )

            invitation_response = InvitationResponse(
                id=inv.id,
                code=inv.code,
                use_count=inv.use_count,
                enabled=inv.enabled,
                created_at=inv.created_at,
                expires_at=inv.expires_at,
                max_uses=inv.max_uses,
                duration_days=inv.duration_days,
                created_by=inv.created_by,
                updated_at=inv.updated_at,
                is_active=is_active,
                remaining_uses=remaining_uses,
            )

        return UserDetailResponse(
            id=user.id,
            identity_id=user.identity_id,
            media_server_id=user.media_server_id,
            external_user_id=user.external_user_id,
            username=user.username,
            enabled=user.enabled,
            created_at=user.created_at,
            identity=identity_response,
            media_server=media_server_response,
            expires_at=user.expires_at,
            updated_at=user.updated_at,
            invitation_id=user.invitation_id,
            invitation=invitation_response,
        )
