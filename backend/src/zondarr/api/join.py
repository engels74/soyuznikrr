"""JoinController for public invitation redemption endpoint.

Provides the public endpoint for redeeming invitation codes:
- POST /api/v1/join/{code} - Redeem an invitation code

This endpoint is publicly accessible without authentication.
"""

from collections.abc import Mapping, Sequence
from typing import Annotated

from litestar import Controller, Response, post
from litestar.di import Provide
from litestar.openapi.datastructures import ResponseSpec
from litestar.params import Parameter
from litestar.status_codes import HTTP_200_OK
from litestar.types import AnyCallable
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.invitation import InvitationRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.invitation import InvitationService
from zondarr.services.redemption import RedemptionService
from zondarr.services.user import UserService

from .schemas import (
    RedeemInvitationRequest,
    RedemptionErrorResponse,
    RedemptionResponse,
    UserResponse,
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
    return UserService(user_repository, identity_repository)


async def provide_redemption_service(
    invitation_service: InvitationService,
    user_service: UserService,
) -> RedemptionService:
    """Provide RedemptionService instance.

    Args:
        invitation_service: InvitationService from DI.
        user_service: UserService from DI.

    Returns:
        Configured RedemptionService instance.
    """
    return RedemptionService(invitation_service, user_service)


class JoinController(Controller):
    """Controller for public invitation redemption endpoint.

    Provides the public endpoint for redeeming invitation codes to create
    user accounts on target media servers. This endpoint does not require
    authentication.

    """

    path: str = "/api/v1/join"
    tags: Sequence[str] | None = ["Join"]
    dependencies: Mapping[str, Provide | AnyCallable] | None = {
        "invitation_repository": Provide(provide_invitation_repository),
        "server_repository": Provide(provide_media_server_repository),
        "user_repository": Provide(provide_user_repository),
        "identity_repository": Provide(provide_identity_repository),
        "invitation_service": Provide(provide_invitation_service),
        "user_service": Provide(provide_user_service),
        "redemption_service": Provide(provide_redemption_service),
    }

    @post(
        "/{code:str}",
        status_code=HTTP_200_OK,
        summary="Redeem invitation",
        description="Redeem an invitation code to create user accounts on target media servers.",
        exclude_from_auth=True,
        responses={
            400: ResponseSpec(
                data_container=RedemptionErrorResponse,
                description="Redemption failed due to invalid invitation or server error.",
            ),
        },
    )
    async def redeem_invitation(
        self,
        code: Annotated[
            str,
            Parameter(description="Invitation code to redeem"),
        ],
        data: RedeemInvitationRequest,
        redemption_service: RedemptionService,
    ) -> Response[RedemptionResponse]:
        """Redeem an invitation code to create user accounts.

        Creates user accounts on all target media servers specified by the
        invitation. Applies library restrictions and permissions as configured.
        Creates a local Identity linking all User records.

        This endpoint is publicly accessible without authentication.

        The redemption request requires username and password, with optional
        email.

        On failure, ``RedemptionError`` propagates to the DI layer which
        rolls back the DB transaction, then the registered
        ``redemption_error_handler`` returns HTTP 400 with
        ``RedemptionErrorResponse``.

        Args:
            code: The invitation code to redeem.
            data: The redemption request with username, password, and optional email.
            redemption_service: RedemptionService from DI.

        Returns:
            RedemptionResponse on success with identity_id and users_created.
        """
        identity, users = await redemption_service.redeem(
            code,
            username=data.username,
            password=data.password,
            email=data.email,
            auth_token=data.auth_token,
        )

        users_created = [
            UserResponse(
                id=user.id,
                identity_id=user.identity_id,
                media_server_id=user.media_server_id,
                external_user_id=user.external_user_id,
                username=user.username,
                enabled=user.enabled,
                created_at=user.created_at,
                external_user_type=user.external_user_type,
                expires_at=user.expires_at,
                updated_at=user.updated_at,
            )
            for user in users
        ]

        return Response(
            content=RedemptionResponse(
                success=True,
                identity_id=identity.id,
                users_created=users_created,
                message="Account created successfully",
            ),
            status_code=HTTP_200_OK,
        )
