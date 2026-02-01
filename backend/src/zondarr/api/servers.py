"""ServerController for media server management endpoints.

Provides REST endpoints for media server operations including:
- POST /api/v1/servers/{id}/sync - Synchronize users with media server

Uses Litestar Controller pattern with dependency injection for services.
Implements Requirements 20.1, 20.5, 20.8.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

import structlog
from litestar import Controller, Response, post
from litestar.di import Provide
from litestar.params import Parameter
from litestar.status_codes import HTTP_503_SERVICE_UNAVAILABLE
from litestar.types import AnyCallable
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.media.exceptions import MediaClientError
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.sync import SyncService

from .schemas import ErrorResponse, SyncRequest, SyncResult

logger: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]


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


async def provide_sync_service(
    server_repository: MediaServerRepository,
    user_repository: UserRepository,
) -> SyncService:
    """Provide SyncService instance.

    Args:
        server_repository: MediaServerRepository from DI.
        user_repository: UserRepository from DI.

    Returns:
        Configured SyncService instance.
    """
    return SyncService(
        server_repository,
        user_repository,
    )


class ServerController(Controller):
    """Controller for media server management endpoints.

    Provides sync endpoint for synchronizing local user records
    with the actual state of users on media servers.
    All endpoints require authentication.
    """

    path: str = "/api/v1/servers"
    tags: Sequence[str] | None = ["Media Servers"]
    dependencies: Mapping[str, Provide | AnyCallable] | None = {
        "server_repository": Provide(provide_media_server_repository),
        "user_repository": Provide(provide_user_repository),
        "sync_service": Provide(provide_sync_service),
    }

    @post(
        "/{server_id:uuid}/sync",
        summary="Sync users with media server",
        description="Synchronize local user records with the actual state of users on the media server.",
    )
    async def sync_server(
        self,
        server_id: Annotated[
            UUID,
            Parameter(description="Media server UUID"),
        ],
        data: SyncRequest,
        sync_service: SyncService,
    ) -> Response[SyncResult] | Response[ErrorResponse]:
        """Sync users between local database and media server.

        Fetches all users from the media server and compares them with
        local User records. Identifies orphaned users (on server but not
        local) and stale users (local but not on server).

        The sync operation is read-only and idempotent - it only reports
        discrepancies without modifying any data (Requirement 20.7).

        Implements Requirements 20.1, 20.5, 20.8.

        Args:
            server_id: The UUID of the media server to sync.
            data: SyncRequest with dry_run flag.
            sync_service: SyncService from DI.

        Returns:
            SyncResult with discrepancy report on success.
            ErrorResponse with HTTP 503 if server is unreachable.

        Raises:
            NotFoundError: If the server does not exist.
        """
        try:
            result = await sync_service.sync_server(
                server_id,
                dry_run=data.dry_run,
            )
            return Response(result)
        except MediaClientError as e:
            # Return 503 if server is unreachable (Requirement 20.8)
            correlation_id = str(uuid4())

            logger.warning(
                "Media server unreachable during sync",
                correlation_id=correlation_id,
                server_id=str(server_id),
                operation=e.operation,
                cause=e.cause,
            )

            return Response(
                ErrorResponse(
                    detail=f"Media server unreachable: {e.message}",
                    error_code="SERVER_UNREACHABLE",
                    timestamp=datetime.now(UTC),
                    correlation_id=correlation_id,
                ),
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
            )
