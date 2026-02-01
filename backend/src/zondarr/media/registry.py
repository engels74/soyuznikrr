"""Client registry for media server implementations.

Provides a singleton registry that manages available media client implementations.
The registry allows:
- Registering client classes for specific server types
- Looking up client classes by server type
- Querying capabilities for a server type
- Creating client instances with connection parameters

Uses ClassVar for singleton pattern to ensure a single registry instance
throughout the application lifecycle.

Example usage:
    from zondarr.media.registry import registry
    from zondarr.models.media_server import ServerType

    # Register a client (typically done at app startup)
    registry.register(ServerType.JELLYFIN, JellyfinClient)

    # Get client class
    client_class = registry.get_client_class(ServerType.JELLYFIN)

    # Query capabilities
    caps = registry.get_capabilities(ServerType.JELLYFIN)

    # Create a client instance
    client = registry.create_client(
        ServerType.JELLYFIN,
        url="http://jellyfin.local:8096",
        api_key="secret-key",
    )
"""

from typing import ClassVar, Protocol

from zondarr.models.media_server import ServerType

from .exceptions import UnknownServerTypeError
from .protocol import MediaClient
from .types import Capability


class MediaClientClass(Protocol):
    """Protocol for media client classes that can be instantiated.

    Defines the expected constructor signature for media client implementations.
    This allows the registry to properly type-check client class registration
    and instantiation.
    """

    def __call__(self, *, url: str, api_key: str) -> MediaClient:
        """Create a new client instance.

        Args:
            url: The base URL of the media server.
            api_key: The API key for authentication.

        Returns:
            A MediaClient instance.
        """
        ...

    @classmethod
    def capabilities(cls) -> set[Capability]:
        """Return the set of capabilities this client supports."""
        ...


class ClientRegistry:
    """Singleton registry for media client implementations.

    Manages the mapping between server types and their client implementations.
    Uses ClassVar for singleton instance storage to ensure all code paths
    share the same registry state.

    The registry is typically populated at application startup by registering
    client classes for each supported server type. Client instances are then
    created on-demand when needed for specific media server operations.

    Attributes:
        _instance: Class-level singleton instance storage.
        _clients: Mapping from server types to client classes.
    """

    _instance: ClassVar[ClientRegistry | None] = None

    def __init__(self) -> None:
        """Initialize the registry's client mapping if not already done."""
        # Only initialize _clients if this is a fresh instance
        # (singleton pattern means __init__ may be called multiple times)
        if not hasattr(self, "_clients"):
            self._clients: dict[ServerType, MediaClientClass] = {}

    def __new__(cls) -> ClientRegistry:
        """Create or return the singleton instance.

        Returns:
            The singleton ClientRegistry instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(
        self,
        server_type: ServerType,
        client_class: MediaClientClass,
        /,
    ) -> None:
        """Register a client implementation for a server type.

        Associates a client class with a server type. If a client is already
        registered for the given type, it will be replaced.

        Args:
            server_type: The server type to register (positional-only).
            client_class: The client class implementing MediaClient protocol
                (positional-only).
        """
        self._clients[server_type] = client_class

    def get_client_class(self, server_type: ServerType, /) -> MediaClientClass:
        """Get the client class for a server type.

        Looks up the registered client class for the given server type.

        Args:
            server_type: The server type to look up (positional-only).

        Returns:
            The registered client class for the server type.

        Raises:
            UnknownServerTypeError: If no client is registered for the server type.
        """
        if (client_class := self._clients.get(server_type)) is None:
            raise UnknownServerTypeError(server_type)
        return client_class

    def get_capabilities(self, server_type: ServerType, /) -> set[Capability]:
        """Get capabilities for a server type.

        Queries the registered client class for its declared capabilities.

        Args:
            server_type: The server type to query (positional-only).

        Returns:
            A set of Capability enum values supported by the client.

        Raises:
            UnknownServerTypeError: If no client is registered for the server type.
        """
        return self.get_client_class(server_type).capabilities()

    def create_client(
        self,
        server_type: ServerType,
        /,
        *,
        url: str,
        api_key: str,
    ) -> MediaClient:
        """Create a client instance for a media server.

        Instantiates a client with the provided connection parameters.
        The server_type is positional-only, while url and api_key are
        keyword-only to make the intent clear at call sites.

        Args:
            server_type: The server type to create a client for (positional-only).
            url: The base URL of the media server (keyword-only).
            api_key: The API key for authentication (keyword-only).

        Returns:
            A new client instance configured for the specified server.

        Raises:
            UnknownServerTypeError: If no client is registered for the server type.
        """
        client_class = self.get_client_class(server_type)
        return client_class(url=url, api_key=api_key)

    def clear(self) -> None:
        """Clear all registered clients.

        Primarily useful for testing to reset the registry state between tests.
        """
        self._clients.clear()


# Global registry instance for convenient access
registry = ClientRegistry()
