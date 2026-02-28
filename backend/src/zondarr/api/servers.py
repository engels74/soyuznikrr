"""ServerController for media server management endpoints.

Provides REST endpoints for media server operations including:
- POST /api/v1/servers - Create a new media server
- GET /api/v1/servers/{id} - Get media server details
- DELETE /api/v1/servers/{id} - Delete a media server
- POST /api/v1/servers/{id}/sync-libraries - Synchronize libraries with media server
- POST /api/v1/servers/{id}/sync - Synchronize users with media server

Uses Litestar Controller pattern with dependency injection for services.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast
from uuid import UUID, uuid4

import structlog
from litestar import Controller, Request, Response, delete, get, post
from litestar.datastructures import State
from litestar.di import Provide
from litestar.params import Parameter
from litestar.status_codes import HTTP_503_SERVICE_UNAVAILABLE
from litestar.types import AnyCallable
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.config import Settings
from zondarr.core.exceptions import ValidationError
from zondarr.core.tasks import BackgroundTaskManager
from zondarr.media.exceptions import MediaClientError
from zondarr.media.registry import registry
from zondarr.models.sync_run import SyncRun
from zondarr.repositories.admin import AdminAccountRepository
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.sync_exclusion import SyncExclusionRepository
from zondarr.repositories.sync_run import SyncRunRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.media_server import MediaServerService
from zondarr.services.onboarding import OnboardingService
from zondarr.services.sync import SyncService

from .schemas import (
    ConnectionTestRequest,
    ConnectionTestResponse,
    EnvCredentialResponse,
    EnvCredentialsResponse,
    ErrorResponse,
    LibraryResponse,
    LibrarySyncResult,
    MediaServerCreate,
    MediaServerDetailResponse,
    MediaServerWithLibrariesResponse,
    ServerSyncStatusResponse,
    SyncChannelStatusResponse,
    SyncRequest,
    SyncResult,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]


def mask_api_key(api_key: str) -> str:
    """Mask an API key for safe display.

    Shows first 4 + last 4 chars for keys >= 12 chars,
    first 2 + last 2 for 6-11 chars, all asterisks for < 6.
    """
    length = len(api_key)
    if length >= 12:
        return f"{api_key[:4]}{'*' * (length - 8)}{api_key[-4:]}"
    if length >= 6:
        return f"{api_key[:2]}{'*' * (length - 4)}{api_key[-2:]}"
    return "*" * length


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


async def provide_sync_exclusion_repository(
    session: AsyncSession,
) -> SyncExclusionRepository:
    """Provide SyncExclusionRepository instance.

    Args:
        session: Database session from DI.

    Returns:
        Configured SyncExclusionRepository instance.
    """
    return SyncExclusionRepository(session)


async def provide_sync_run_repository(
    session: AsyncSession,
) -> SyncRunRepository:
    """Provide SyncRunRepository instance."""
    return SyncRunRepository(session)


async def provide_sync_service(
    server_repository: MediaServerRepository,
    user_repository: UserRepository,
    identity_repository: IdentityRepository,
    sync_exclusion_repository: SyncExclusionRepository,
) -> SyncService:
    """Provide SyncService instance.

    Args:
        server_repository: MediaServerRepository from DI.
        user_repository: UserRepository from DI.
        identity_repository: IdentityRepository from DI.
        sync_exclusion_repository: SyncExclusionRepository from DI.

    Returns:
        Configured SyncService instance.
    """
    return SyncService(
        server_repository,
        user_repository,
        identity_repository,
        sync_exclusion_repo=sync_exclusion_repository,
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
        "sync_exclusion_repository": Provide(provide_sync_exclusion_repository),
        "sync_run_repository": Provide(provide_sync_run_repository),
        "sync_service": Provide(provide_sync_service),
        "media_server_service": Provide(provide_media_server_service),
    }

    @staticmethod
    def _resolve_api_key(
        api_key: str | None,
        use_env_credentials: bool,
        server_type: str | None,
        settings: Settings,
    ) -> str:
        """Resolve API key from request body or environment credentials.

        Args:
            api_key: Explicit API key from the request body.
            use_env_credentials: Whether to look up the key from env vars.
            server_type: Provider type (needed for env lookup).
            settings: Application settings containing provider_credentials.

        Returns:
            The resolved API key string.

        Raises:
            ValidationError: If no API key can be resolved.
        """
        if use_env_credentials:
            if server_type is None:
                raise ValidationError(
                    "server_type is required when using environment credentials",
                    field_errors={
                        "server_type": ["Required when use_env_credentials is true"]
                    },
                )
            provider_creds = settings.provider_credentials.get(server_type, {})
            env_key = provider_creds.get("api_key")
            if not env_key:
                raise ValidationError(
                    f"No API key found in environment for provider '{server_type}'",
                    field_errors={
                        "api_key": [
                            f"No environment API key configured for {server_type}"
                        ]
                    },
                )
            return env_key

        if not api_key:
            raise ValidationError(
                "API key is required",
                field_errors={"api_key": ["API key is required"]},
            )
        return api_key

    @staticmethod
    def _to_library_response(
        library_id: UUID,
        name: str,
        library_type: str,
        external_id: str,
        created_at: datetime,
        updated_at: datetime | None,
    ) -> LibraryResponse:
        """Build a LibraryResponse from model field values."""
        return LibraryResponse(
            id=library_id,
            name=name,
            library_type=library_type,
            external_id=external_id,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _resolve_next_scheduled_at(
        manager: BackgroundTaskManager | None,
        *,
        last_completed_at: datetime | None,
        settings: Settings,
    ) -> datetime | None:
        """Resolve next scheduled sync time from runtime state or fallback."""
        if manager is not None:
            next_run = manager.get_next_sync_run_at()
            if next_run is not None:
                return next_run

        if last_completed_at is None:
            return None
        return last_completed_at + timedelta(seconds=settings.sync_interval_seconds)

    async def _build_sync_status(
        self,
        *,
        server_id: UUID,
        settings: Settings,
        sync_run_repository: SyncRunRepository,
        manager: BackgroundTaskManager | None,
    ) -> ServerSyncStatusResponse:
        """Build server sync status response for users and libraries."""
        libraries_success = await sync_run_repository.get_latest_success_by_type(
            server_id, "libraries"
        )
        users_success = await sync_run_repository.get_latest_success_by_type(
            server_id, "users"
        )

        libraries_last_completed = (
            libraries_success.finished_at if libraries_success is not None else None
        )
        users_last_completed = (
            users_success.finished_at if users_success is not None else None
        )

        libraries_in_progress = (
            manager.is_libraries_sync_in_progress(server_id)
            if manager is not None
            else False
        )
        users_in_progress = (
            manager.is_users_sync_in_progress(server_id)
            if manager is not None
            else False
        )

        libraries_next = self._resolve_next_scheduled_at(
            manager,
            last_completed_at=libraries_last_completed,
            settings=settings,
        )
        users_next = self._resolve_next_scheduled_at(
            manager,
            last_completed_at=users_last_completed,
            settings=settings,
        )

        return ServerSyncStatusResponse(
            libraries=SyncChannelStatusResponse(
                in_progress=libraries_in_progress,
                last_completed_at=libraries_last_completed,
                next_scheduled_at=libraries_next,
            ),
            users=SyncChannelStatusResponse(
                in_progress=users_in_progress,
                last_completed_at=users_last_completed,
                next_scheduled_at=users_next,
            ),
        )

    async def _record_sync_run(
        self,
        *,
        sync_run_repository: SyncRunRepository,
        media_server_id: UUID,
        sync_type: str,
        trigger: str,
        status: str,
        started_at: datetime,
        error_message: str | None = None,
    ) -> None:
        """Persist a sync run row without bubbling failures to callers."""
        try:
            _ = await sync_run_repository.create(
                SyncRun(
                    media_server_id=media_server_id,
                    sync_type=sync_type,
                    trigger=trigger,
                    status=status,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    error_message=error_message,
                )
            )
        except Exception as exc:
            logger.warning(
                "Failed to persist sync run",
                media_server_id=str(media_server_id),
                sync_type=sync_type,
                trigger=trigger,
                status=status,
                error=str(exc),
            )

    @get(
        "/env-credentials",
        cache=False,
        summary="Get detected environment credentials",
        description="Returns media server credentials detected from environment variables.",
    )
    async def get_env_credentials(
        self,
        settings: Settings,
    ) -> EnvCredentialsResponse:
        """Get detected environment variable credentials for media server providers.

        Iterates all registered providers and checks if their env vars are set.
        Only includes providers that have at least one credential (URL or API key).

        Args:
            settings: Application settings from DI.

        Returns:
            EnvCredentialsResponse with detected credentials.
        """
        credentials: list[EnvCredentialResponse] = []

        for meta in registry.get_all_metadata():
            provider_creds = settings.provider_credentials.get(meta.server_type, {})
            url = provider_creds.get("url")
            api_key = provider_creds.get("api_key")

            if not url and not api_key:
                continue

            credentials.append(
                EnvCredentialResponse(
                    server_type=meta.server_type,
                    display_name=meta.display_name,
                    url=url,
                    masked_api_key=mask_api_key(api_key) if api_key else None,
                    has_url=bool(url),
                    has_api_key=bool(api_key),
                )
            )

        return EnvCredentialsResponse(credentials=credentials)

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
        sync_run_repository: SyncRunRepository,
        settings: Settings,
        session: AsyncSession,
    ) -> MediaServerWithLibrariesResponse:
        """Create a new media server.

        Validates the connection to the media server before persisting.
        If the connection test fails, returns a validation error.

        Args:
            data: MediaServerCreate with server configuration.
            media_server_service: MediaServerService from DI.
            settings: Application settings from DI.

        Returns:
            Created media server details.

        Raises:
            ValidationError: If connection validation fails.
        """
        # Resolve API key: from env credentials or from the request body
        api_key = self._resolve_api_key(
            data.api_key, data.use_env_credentials, data.server_type, settings
        )

        server = await media_server_service.add(
            name=data.name,
            server_type=data.server_type,
            url=data.url,
            api_key=api_key,
        )

        # Sync libraries after creation (best-effort — don't fail server creation)
        libraries: list[LibraryResponse] = []
        started_at = datetime.now(UTC)
        try:
            sync_result = await media_server_service.sync_libraries_detailed(server.id)
            libraries = [
                self._to_library_response(
                    lib.id,
                    lib.name,
                    lib.library_type,
                    lib.external_id,
                    lib.created_at,
                    lib.updated_at,
                )
                for lib in sync_result.libraries
            ]
            await self._record_sync_run(
                sync_run_repository=sync_run_repository,
                media_server_id=server.id,
                sync_type="libraries",
                trigger="onboarding",
                status="success",
                started_at=started_at,
            )
        except Exception as exc:
            await self._record_sync_run(
                sync_run_repository=sync_run_repository,
                media_server_id=server.id,
                sync_type="libraries",
                trigger="onboarding",
                status="failed",
                started_at=started_at,
                error_message=str(exc),
            )
            logger.warning(
                "Failed to sync libraries after server creation",
                server_id=str(server.id),
                error=str(exc),
            )

        onboarding_service = OnboardingService(
            admin_repo=AdminAccountRepository(session),
            app_setting_repo=AppSettingRepository(session),
        )
        _ = await onboarding_service.complete_server_step()

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
        request: Request[object, object, State],
        settings: Settings,
        sync_run_repository: SyncRunRepository,
        media_server_service: MediaServerService,
    ) -> MediaServerDetailResponse:
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

        manager = cast(
            BackgroundTaskManager | None,
            getattr(request.app.state, "background_task_manager", None),
        )
        sync_status = await self._build_sync_status(
            server_id=server_id,
            settings=settings,
            sync_run_repository=sync_run_repository,
            manager=manager,
        )

        return MediaServerDetailResponse(
            id=server.id,
            name=server.name,
            server_type=server.server_type,
            url=server.url,
            enabled=server.enabled,
            created_at=server.created_at,
            updated_at=server.updated_at,
            libraries=[
                self._to_library_response(
                    lib.id,
                    lib.name,
                    lib.library_type,
                    lib.external_id,
                    lib.created_at,
                    lib.updated_at,
                )
                for lib in server.libraries
            ],
            sync_status=sync_status,
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
        status_code=200,
        summary="Test media server connection",
        description="Test connectivity and auto-detect server type. If server_type is omitted, probes all registered providers.",
    )
    async def test_connection(
        self,
        data: ConnectionTestRequest,
        media_server_service: MediaServerService,
        settings: Settings,
    ) -> ConnectionTestResponse:
        """Test media server connection and optionally auto-detect type.

        Args:
            data: ConnectionTestRequest with url, api_key, and optional server_type.
            media_server_service: MediaServerService from DI.
            settings: Application settings from DI.

        Returns:
            ConnectionTestResponse with success status, detected type, and server info.
        """
        # Resolve API key: from env credentials or from the request body
        try:
            api_key = self._resolve_api_key(
                data.api_key, data.use_env_credentials, data.server_type, settings
            )
        except ValidationError as exc:
            return ConnectionTestResponse(
                success=False,
                message=exc.message,
            )

        success, detected_type, info = await media_server_service.detect_and_test(
            url=data.url,
            api_key=api_key,
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
        "/{server_id:uuid}/sync-libraries",
        status_code=200,
        summary="Sync libraries with media server",
        description="Synchronize server libraries immediately and return change counts.",
    )
    async def sync_libraries(
        self,
        server_id: Annotated[
            UUID,
            Parameter(description="Media server UUID"),
        ],
        media_server_service: MediaServerService,
        sync_run_repository: SyncRunRepository,
    ) -> LibrarySyncResult:
        """Sync libraries between local database and media server immediately."""
        server = await media_server_service.get_by_id(server_id)
        started_at = datetime.now(UTC)

        try:
            result = await media_server_service.sync_libraries_detailed(server_id)
            synced_at = datetime.now(UTC)
            await self._record_sync_run(
                sync_run_repository=sync_run_repository,
                media_server_id=server_id,
                sync_type="libraries",
                trigger="manual",
                status="success",
                started_at=started_at,
            )
            return LibrarySyncResult(
                server_id=server_id,
                server_name=server.name,
                synced_at=synced_at,
                total_libraries=len(result.libraries),
                added_count=result.added_count,
                updated_count=result.updated_count,
                removed_count=result.removed_count,
            )
        except Exception as exc:
            await self._record_sync_run(
                sync_run_repository=sync_run_repository,
                media_server_id=server_id,
                sync_type="libraries",
                trigger="manual",
                status="failed",
                started_at=started_at,
                error_message=str(exc),
            )
            raise

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
        sync_run_repository: SyncRunRepository,
    ) -> Response[SyncResult] | Response[ErrorResponse]:
        """Sync users between local database and media server.

        Fetches all users from the media server and compares them with
        local User records. Identifies orphaned users (on server but not
        local) and stale users (local but not on server).

        The sync operation is read-only and idempotent - it only reports
        discrepancies without modifying any data.

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
        started_at = datetime.now(UTC)
        try:
            result = await sync_service.sync_server(
                server_id,
                dry_run=data.dry_run,
            )
            if not data.dry_run:
                await self._record_sync_run(
                    sync_run_repository=sync_run_repository,
                    media_server_id=server_id,
                    sync_type="users",
                    trigger="manual",
                    status="success",
                    started_at=started_at,
                )
            return Response(result)
        except MediaClientError as e:
            if not data.dry_run:
                await self._record_sync_run(
                    sync_run_repository=sync_run_repository,
                    media_server_id=server_id,
                    sync_type="users",
                    trigger="manual",
                    status="failed",
                    started_at=started_at,
                    error_message=e.message,
                )
            # Return 503 if server is unreachable
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
