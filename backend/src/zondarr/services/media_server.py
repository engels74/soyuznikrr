"""MediaServer service for business logic orchestration.

Provides methods to add, update, remove, and test media server connections.
Validates connections before persisting to ensure only reachable servers
are stored in the database.

Implements Property 10: Service Validates Before Persisting - for any media
server configuration where test_connection() returns False, the service
SHALL NOT persist the server and SHALL raise a validation error.
"""

from collections.abc import Sequence
from uuid import UUID

from zondarr.core.exceptions import NotFoundError, ValidationError
from zondarr.media.registry import ClientRegistry
from zondarr.models.media_server import Library, MediaServer
from zondarr.repositories.media_server import MediaServerRepository


class MediaServerService:
    """Service for managing media server operations.

    Orchestrates business logic for media server management including:
    - Adding new servers with connection validation
    - Updating existing server configurations
    - Removing servers from the system
    - Testing server connectivity
    - Syncing libraries from media servers

    All add operations validate the connection before persisting to ensure
    only reachable, properly configured servers are stored.

    Attributes:
        repository: The MediaServerRepository for data access.
        registry: The ClientRegistry for creating media clients.
    """

    repository: MediaServerRepository
    registry: ClientRegistry

    def __init__(
        self,
        repository: MediaServerRepository,
        /,
        *,
        registry: ClientRegistry | None = None,
    ) -> None:
        """Initialize the MediaServerService.

        Args:
            repository: The MediaServerRepository for data access (positional-only).
            registry: Optional ClientRegistry for creating media clients.
                Defaults to the global registry instance (keyword-only).
        """
        self.repository = repository
        # Import here to avoid circular imports and allow injection for testing
        if registry is None:
            from zondarr.media.registry import registry as global_registry

            self.registry = global_registry
        else:
            self.registry = registry

    async def add(
        self,
        *,
        name: str,
        server_type: str,
        url: str,
        api_key: str,
        enabled: bool = True,
    ) -> MediaServer:
        """Add a new media server after validating the connection.

        Creates a new MediaServer entity and validates the connection
        before persisting. If the connection test fails, raises a
        ValidationError and does not persist the server.

        Args:
            name: Human-readable name for the server (keyword-only).
            server_type: Type of media server (keyword-only). Must be a
                registered provider type.
            url: Base URL for the media server API (keyword-only).
            api_key: Authentication token for the server (keyword-only).
            enabled: Whether the server should be active (keyword-only).

        Returns:
            The created MediaServer entity with generated ID.

        Raises:
            ValidationError: If server_type is unknown or connection test fails.
            RepositoryError: If the database operation fails.
        """
        # Validate server_type against registry
        if server_type not in self.registry.registered_types():
            raise ValidationError(
                f"Unknown server type: {server_type}",
                field_errors={
                    "server_type": [
                        f"Unsupported server type '{server_type}'. Supported types: {', '.join(sorted(self.registry.registered_types()))}"
                    ],
                },
            )

        # Validate connection before persisting (Property 10)
        connection_valid = await self.test_connection(
            server_type=server_type,
            url=url,
            api_key=api_key,
        )

        if not connection_valid:
            raise ValidationError(
                "Failed to connect to media server",
                field_errors={
                    "url": ["Unable to establish connection to the media server"],
                    "api_key": ["Connection test failed - verify API key is valid"],
                },
            )

        # Create and persist the server
        server = MediaServer(
            name=name,
            server_type=server_type,
            url=url,
            api_key=api_key,
            enabled=enabled,
        )

        return await self.repository.create(server)

    async def update(
        self,
        server_id: UUID,
        /,
        *,
        name: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
        enabled: bool | None = None,
    ) -> MediaServer:
        """Update an existing media server configuration.

        Updates only the provided fields. If url or api_key are changed,
        validates the new connection before persisting.

        Args:
            server_id: The UUID of the server to update (positional-only).
            name: New name for the server (keyword-only, optional).
            url: New URL for the server (keyword-only, optional).
            api_key: New API key for the server (keyword-only, optional).
            enabled: New enabled status (keyword-only, optional).

        Returns:
            The updated MediaServer entity.

        Raises:
            NotFoundError: If the server does not exist.
            ValidationError: If connection validation fails after url/api_key change.
            RepositoryError: If the database operation fails.
        """
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise NotFoundError("MediaServer", str(server_id))

        # Determine if we need to revalidate connection
        new_url = url if url is not None else server.url
        new_api_key = api_key if api_key is not None else server.api_key
        needs_validation = url is not None or api_key is not None

        if needs_validation:
            connection_valid = await self.test_connection(
                server_type=server.server_type,
                url=new_url,
                api_key=new_api_key,
            )

            if not connection_valid:
                raise ValidationError(
                    "Failed to connect to media server with new configuration",
                    field_errors={
                        "url": ["Unable to establish connection to the media server"],
                        "api_key": ["Connection test failed - verify API key is valid"],
                    },
                )

        # Apply updates
        if name is not None:
            server.name = name
        if url is not None:
            server.url = url
        if api_key is not None:
            server.api_key = api_key
        if enabled is not None:
            server.enabled = enabled

        # Flush changes
        await self.repository.session.flush()

        return server

    async def remove(self, server_id: UUID, /) -> None:
        """Remove a media server from the system.

        Deletes the server and all associated libraries via cascade.

        Args:
            server_id: The UUID of the server to remove (positional-only).

        Raises:
            NotFoundError: If the server does not exist.
            RepositoryError: If the database operation fails.
        """
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise NotFoundError("MediaServer", str(server_id))

        await self.repository.delete(server)

    async def test_connection(
        self,
        *,
        server_type: str,
        url: str,
        api_key: str,
    ) -> bool:
        """Test connectivity to a media server.

        Creates a temporary client and tests the connection without
        persisting anything to the database.

        Args:
            server_type: Type of media server (keyword-only).
            url: Base URL for the media server API (keyword-only).
            api_key: Authentication token for the server (keyword-only).

        Returns:
            True if the connection is successful, False otherwise.
        """
        try:
            client = self.registry.create_client(
                server_type,
                url=url,
                api_key=api_key,
            )
            async with client:
                return await client.test_connection()
        except Exception:
            # Any exception during connection test means failure
            return False

    async def get_by_id(self, server_id: UUID, /) -> MediaServer:
        """Retrieve a media server by ID.

        Args:
            server_id: The UUID of the server to retrieve (positional-only).

        Returns:
            The MediaServer entity.

        Raises:
            NotFoundError: If the server does not exist.
            RepositoryError: If the database operation fails.
        """
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise NotFoundError("MediaServer", str(server_id))
        return server

    async def get_all(self) -> Sequence[MediaServer]:
        """Retrieve all media servers.

        Returns:
            A sequence of all MediaServer entities.

        Raises:
            RepositoryError: If the database operation fails.
        """
        return await self.repository.get_all()

    async def get_enabled(self) -> Sequence[MediaServer]:
        """Retrieve all enabled media servers.

        Returns:
            A sequence of enabled MediaServer entities.

        Raises:
            RepositoryError: If the database operation fails.
        """
        return await self.repository.get_enabled()

    async def sync_libraries(self, server_id: UUID, /) -> Sequence[Library]:
        """Sync libraries from a media server.

        Fetches the current list of libraries from the media server
        and updates the local database to match. New libraries are
        added, existing libraries are updated, and removed libraries
        are deleted.

        Args:
            server_id: The UUID of the server to sync (positional-only).

        Returns:
            The updated list of Library entities for the server.

        Raises:
            NotFoundError: If the server does not exist.
            ValidationError: If the connection to the server fails.
            RepositoryError: If the database operation fails.
        """
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise NotFoundError("MediaServer", str(server_id))

        # Fetch libraries from the media server
        try:
            client = self.registry.create_client_for_server(server)
            async with client:
                remote_libraries = await client.get_libraries()
        except Exception as e:
            raise ValidationError(
                f"Failed to fetch libraries from media server: {e}",
                field_errors={
                    "server_id": [
                        "Unable to connect to media server to sync libraries"
                    ],
                },
            ) from e

        # Build a map of existing libraries by external_id
        existing_by_external_id: dict[str, Library] = {
            lib.external_id: lib for lib in server.libraries
        }

        # Track which external_ids we've seen from remote
        seen_external_ids: set[str] = set()

        # Update or create libraries
        updated_libraries: list[Library] = []
        for remote_lib in remote_libraries:
            seen_external_ids.add(remote_lib.external_id)

            if remote_lib.external_id in existing_by_external_id:
                # Update existing library
                existing = existing_by_external_id[remote_lib.external_id]
                existing.name = remote_lib.name
                existing.library_type = remote_lib.library_type
                updated_libraries.append(existing)
            else:
                # Create new library
                new_library = Library(
                    media_server_id=server.id,
                    external_id=remote_lib.external_id,
                    name=remote_lib.name,
                    library_type=remote_lib.library_type,
                )
                server.libraries.append(new_library)
                updated_libraries.append(new_library)

        # Remove libraries that no longer exist on the server
        for external_id, library in existing_by_external_id.items():
            if external_id not in seen_external_ids:
                server.libraries.remove(library)

        # Flush changes
        await self.repository.session.flush()

        return server.libraries
