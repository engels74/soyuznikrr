"""ServerController for media server management endpoints.

Provides REST endpoints for media server operations including:
- POST /api/v1/servers - Create a new media server
- GET /api/v1/servers/{id} - Get media server details
- DELETE /api/v1/servers/{id} - Delete a media server
- POST /api/v1/servers/{id}/sync - Synchronize users with media server

Uses Litestar Controller pattern with dependency injection for services.
Implements Requirements 20.1, 20.5, 20.8.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

import structlog
from litestar import Controller, Response, delete, get, post
from litestar.di import Provide
from litestar.params import Parameter
from litestar.status_codes import HTTP_503_SERVICE_UNAVAILABLE
from litestar.types import AnyCallable
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.media.exceptions import MediaClientError
from zondarr.media.registry import registry
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.media_server import MediaServerService
from zondarr.services.sync import SyncService

from .schemas import (
    ConnectionTestRequest,
    ConnectionTestResponse,
    ErrorResponse,
    LibraryResponse,
    MediaServerCreate,
    MediaServerResponse,
    MediaServerWithLibrariesResponse,
    SyncRequest,
    SyncResult,
)

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


async def provide_sync_service(
    server_repository: MediaServerRepository,
    user_repository: UserRepository,
    identity_repository: IdentityRepository,
) -> SyncService:
    """Provide SyncService instance.

    Args:
        server_repository: MediaServerRepository from DI.
        user_repository: UserRepository from DI.
        identity_repository: IdentityRepository from DI.

    Returns:
        Configured SyncService instance.
    """
    return SyncService(
        server_repository,
        user_repository,
        identity_repository,
    )


async def provide_media_server_service(
    server_repository: MediaServerRepository,
) -> MediaServerService:
    """Provide MediaServerService instance.

    Args:
        server_repository: MediaServerRepository from DI.

    Returns:
        Configured MediaServerService instance.
    """
    return MediaServerService(server_repository)


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
        "identity_repository": Provide(provide_identity_repository),
        "sync_service": Provide(provide_sync_service),
        "media_server_service": Provide(provide_media_server_service),
    }

    @get(
        "/",
        summary="List media servers",
        description="List all media servers with their libraries.",
    )
    async def list_servers(
        self,
        media_server_service: MediaServerService,
        enabled: Annotated[
            bool | None,
            Parameter(description="Filter by enabled status"),
        ] = None,
    ) -> list[MediaServerWithLibrariesResponse]:
        """List all media servers with libraries.

        Returns all configured media servers with their associated libraries.
        Optionally filter by enabled status.

        Args:
            media_server_service: MediaServerService from DI.
            enabled: Optional filter for enabled/disabled servers.

        Returns:
            List of media servers with their libraries.
        """
        if enabled is True:
            servers = await media_server_service.get_enabled()
        elif enabled is False:
            # Need to get all and filter disabled
            all_servers = await media_server_service.get_all()
            servers = [s for s in all_servers if not s.enabled]
        else:
            servers = await media_server_service.get_all()

        return [
            MediaServerWithLibrariesResponse(
                id=server.id,
                name=server.name,
                server_type=server.server_type,
                url=server.url,
                enabled=server.enabled,
                created_at=server.created_at,
                updated_at=server.updated_at,
                libraries=[
                    LibraryResponse(
                        id=lib.id,
                        name=lib.name,
                        library_type=lib.library_type,
                        external_id=lib.external_id,
                        created_at=lib.created_at,
                        updated_at=lib.updated_at,
                    )
                    for lib in server.libraries
                ],
                supported_permissions=sorted(
                    registry.get_supported_permissions(server.server_type)
                ),
            )
            for server in servers
        ]

    @post(
        "/",
        status_code=201,
        summary="Create media server",
        description="Add a new media server with connection validation.",
    )
    async def create_server(
        self,
        data: MediaServerCreate,
        media_server_service: MediaServerService,
    ) -> MediaServerWithLibrariesResponse:
        """Create a new media server.

        Validates the connection to the media server before persisting.
        If the connection test fails, returns a validation error.

        Args:
            data: MediaServerCreate with server configuration.
            media_server_service: MediaServerService from DI.

        Returns:
            Created media server details.

        Raises:
            ValidationError: If connection validation fails.
        """
        server = await media_server_service.add(
            name=data.name,
            server_type=data.server_type,
            url=data.url,
            api_key=data.api_key,
        )

        # Sync libraries after creation (best-effort — don't fail server creation)
        libraries: list[LibraryResponse] = []
        try:
            synced = await media_server_service.sync_libraries(server.id)
            libraries = [
                LibraryResponse(
                    id=lib.id,
                    name=lib.name,
                    library_type=lib.library_type,
                    external_id=lib.external_id,
                    created_at=lib.created_at,
                    updated_at=lib.updated_at,
                )
                for lib in synced
            ]
        except Exception as exc:
            logger.warning(
                "Failed to sync libraries after server creation",
                server_id=str(server.id),
                error=str(exc),
            )

        return MediaServerWithLibrariesResponse(
            id=server.id,
            name=server.name,
            server_type=server.server_type,
            url=server.url,
            enabled=server.enabled,
            created_at=server.created_at,
            updated_at=server.updated_at,
            libraries=libraries,
            supported_permissions=sorted(
                registry.get_supported_permissions(server.server_type)
            ),
        )

    @get(
        "/{server_id:uuid}",
        summary="Get media server",
        description="Retrieve details for a specific media server.",
    )
    async def get_server(
        self,
        server_id: Annotated[
            UUID,
            Parameter(description="Media server UUID"),
        ],
        media_server_service: MediaServerService,
    ) -> MediaServerResponse:
        """Get media server details by ID.

        Args:
            server_id: The UUID of the media server.
            media_server_service: MediaServerService from DI.

        Returns:
            Media server details.

        Raises:
            NotFoundError: If the server does not exist.
        """
        server = await media_server_service.get_by_id(server_id)

        return MediaServerResponse(
            id=server.id,
            name=server.name,
            server_type=server.server_type,
            url=server.url,
            enabled=server.enabled,
            created_at=server.created_at,
            updated_at=server.updated_at,
            supported_permissions=sorted(
                registry.get_supported_permissions(server.server_type)
            ),
        )

    @delete(
        "/{server_id:uuid}",
        status_code=204,
        summary="Delete media server",
        description="Remove a media server and all associated data.",
    )
    async def delete_server(
        self,
        server_id: Annotated[
            UUID,
            Parameter(description="Media server UUID"),
        ],
        media_server_service: MediaServerService,
    ) -> None:
        """Delete a media server.

        Removes the server and all associated libraries and users via cascade.

        Args:
            server_id: The UUID of the media server to delete.
            media_server_service: MediaServerService from DI.

        Returns:
            None (HTTP 204 No Content on success).

        Raises:
            NotFoundError: If the server does not exist.
        """
        await media_server_service.remove(server_id)

    @post(
        "/test-connection",
        summary="Test media server connection",
        description="Test connectivity and auto-detect server type. If server_type is omitted, probes all registered providers.",
    )
    async def test_connection(
        self,
        data: ConnectionTestRequest,
        media_server_service: MediaServerService,
    ) -> ConnectionTestResponse:
        """Test media server connection and optionally auto-detect type.

        Args:
            data: ConnectionTestRequest with url, api_key, and optional server_type.
            media_server_service: MediaServerService from DI.

        Returns:
            ConnectionTestResponse with success status, detected type, and server info.
        """
        success, detected_type, info = await media_server_service.detect_and_test(
            url=data.url,
            api_key=data.api_key,
            server_type=data.server_type,
        )

        if success:
            return ConnectionTestResponse(
                success=True,
                message="Connection successful",
                server_type=detected_type,
                server_name=info.server_name if info else None,
                version=info.version if info else None,
            )

        return ConnectionTestResponse(
            success=False,
            message="Unable to connect to the media server. Check the URL and API key.",
            server_type=detected_type,
        )

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
