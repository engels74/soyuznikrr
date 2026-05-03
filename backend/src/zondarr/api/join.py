"""JoinController for public invitation redemption endpoint.

Provides the public endpoints for invitation redemption:
- POST /api/v1/join/{code} - Redeem an invitation code
- GET /api/v1/join/health/{code} - Check target server reachability

These endpoints are publicly accessible without authentication.
"""

import asyncio
from collections.abc import Mapping, Sequence
from typing import Annotated

import structlog
from litestar import Controller, Response, get, post
from litestar.di import Provide
from litestar.openapi.datastructures import ResponseSpec
from litestar.params import Parameter
from litestar.status_codes import HTTP_200_OK, HTTP_404_NOT_FOUND
from litestar.types import AnyCallable
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.config import Settings
from zondarr.core.exceptions import NotFoundError
from zondarr.media.registry import registry
from zondarr.models.media_server import MediaServer
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.invitation import InvitationRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.invitation import InvitationService
from zondarr.services.oauth_session import OAuthSessionStore
from zondarr.services.redemption import RedemptionService
from zondarr.services.user import UserService

from .schemas import (
    JoinHealthResponse,
    RedeemInvitationRequest,
    RedemptionErrorResponse,
    RedemptionResponse,
    ServerHealthStatus,
    UserResponse,
)

logger = structlog.get_logger()  # pyright: ignore[reportAny]

_HEALTH_PROBE_TIMEOUT_SECONDS = 10.0


async def _probe_server(server: MediaServer) -> ServerHealthStatus:
    """Probe a single media server's reachability with a timeout.

    Wraps the entire probe — client context manager entry and
    ``test_connection()`` call — in a single ``asyncio.wait_for`` so that
    a slow ``__aenter__`` cannot block beyond the timeout budget.

    Args:
        server: The media server to probe.

    Returns:
        A ``ServerHealthStatus`` indicating whether the server is reachable.
    """
    reachable = False
    try:

        async def _connect_and_test() -> bool:
            client = registry.create_client_for_server(server)
            async with client:
                return await client.test_connection()

        reachable = await asyncio.wait_for(
            _connect_and_test(),
            timeout=_HEALTH_PROBE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.info(  # pyright: ignore[reportAny]
            "join_health_check_failed",
            server_name=server.name,
            server_type=server.server_type,
            error=str(exc),
            exc_info=True,
        )
        reachable = False

    return ServerHealthStatus(
        name=server.name,
        server_type=server.server_type,
        reachable=reachable,
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

    @get(
        "/health/{code:str}",
        status_code=HTTP_200_OK,
        summary="Check target server health",
        description="Check reachability of target media servers for an invitation code.",
        exclude_from_auth=True,
        responses={
            404: ResponseSpec(
                data_container=dict[str, str],
                description="Invalid or expired invitation code.",
            ),
        },
    )
    async def check_health(
        self,
        code: Annotated[
            str,
            Parameter(description="Invitation code to check health for"),
        ],
        invitation_service: InvitationService,
    ) -> Response[JoinHealthResponse] | Response[dict[str, str]]:
        """Check target server reachability for an invitation code.

        Validates the invitation code, then probes each target server's
        connectivity concurrently with a per-server timeout. Returns
        per-server health status without exposing sensitive server details.

        Args:
            code: The invitation code to check.
            invitation_service: InvitationService from DI.

        Returns:
            JoinHealthResponse with per-server reachability status,
            or 404 if the invitation code is invalid.
        """
        is_valid, _ = await invitation_service.validate(code)
        if not is_valid:
            return Response(
                content={"detail": "Invalid invitation code"},
                status_code=HTTP_404_NOT_FOUND,
            )

        try:
            invitation = await invitation_service.get_by_code(code)
        except NotFoundError:
            return Response(
                content={"detail": "Invalid invitation code"},
                status_code=HTTP_404_NOT_FOUND,
            )

        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(_probe_server(server))
                for server in invitation.target_servers
            ]

        statuses = [task.result() for task in tasks]

        return Response(
            content=JoinHealthResponse(
                all_reachable=bool(statuses) and all(s.reachable for s in statuses),
                servers=statuses,
            ),
            status_code=HTTP_200_OK,
        )

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
        settings: Settings,
        session: AsyncSession,
    ) -> Response[RedemptionResponse]:
        """Redeem an invitation code to create user accounts.

        Creates user accounts on all target media servers specified by the
        invitation. Applies library restrictions and permissions as configured.
        Creates a local Identity linking all User records.

        This endpoint is publicly accessible without authentication.

        The redemption request requires username and password, with optional
        email. If the invitation has a pre-wizard configured,
        ``pre_wizard_token`` must contain a valid signed completion token.

        On failure, ``RedemptionError`` propagates to the DI layer which
        rolls back the DB transaction, then the registered
        ``redemption_error_handler`` returns HTTP 400 with
        ``RedemptionErrorResponse``.

        Args:
            code: The invitation code to redeem.
            data: The redemption request with username, password, and optional email.
            redemption_service: RedemptionService from DI.
            settings: Application settings from DI.

        Returns:
            RedemptionResponse on success with identity_id and users_created.
        """
        # Resolve redemption_token to a real auth_token (and provider-supplied
        # email) server-side. The email is consumed below as a fallback when
        # the redemption form did not include one — important for the OAuth
        # path where the user never types an email but Plex returned one.
        auth_token: str | None = None
        oauth_email: str | None = None
        if data.redemption_token:
            store = OAuthSessionStore()
            result = await store.redeem(session, data.redemption_token)
            if result is not None:
                _provider, auth_token, oauth_email = result

        identity, users = await redemption_service.redeem(
            code,
            username=data.username,
            password=data.password,
            email=data.email or oauth_email,
            auth_token=auth_token,
            pre_wizard_token=data.pre_wizard_token,
            secret_key=settings.secret_key,
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
                email=identity.email,
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
