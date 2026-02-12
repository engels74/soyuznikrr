"""Provider registry for media server implementations.

Provides a singleton registry that manages available media server providers.
The registry stores ProviderDescriptor instances keyed by server_type string,
enabling:
- Dynamic provider registration
- Provider metadata queries
- Client class lookups
- Capability queries
- Client instance creation with credential resolution
- Admin auth provider lookups

Example usage:
    from zondarr.media.registry import registry

    # Register providers (typically done at app startup)
    registry.register(PlexProvider())
    registry.register(JellyfinProvider())

    # Get client class
    client_class = registry.get_client_class("plex")

    # Query capabilities
    caps = registry.get_capabilities("plex")

    # Create a client instance
    client = registry.create_client("plex", url="http://...", api_key="...")
"""

import os
from typing import TYPE_CHECKING, ClassVar

from .exceptions import UnknownServerTypeError

if TYPE_CHECKING:
    from zondarr.config import Settings
    from zondarr.models.media_server import MediaServer

    from .protocol import MediaClient
    from .provider import (
        AdminAuthDescriptor,
        AdminAuthProvider,
        MediaClientClass,
        ProviderDescriptor,
        ProviderMetadata,
    )
    from .types import Capability


class ClientRegistry:
    """Singleton registry for media server provider implementations.

    Manages the mapping between server types (strings) and their
    ProviderDescriptor instances. Supports both the legacy register(type, class)
    API and the new register(descriptor) API.

    Attributes:
        _instance: Class-level singleton instance storage.
        _providers: Mapping from server type strings to ProviderDescriptors.
        _clients: Legacy mapping for backwards compatibility.
    """

    _instance: ClassVar[ClientRegistry | None] = None

    def __init__(self) -> None:
        """Initialize the registry if not already done."""
        if not hasattr(self, "_providers"):
            self._providers: dict[str, ProviderDescriptor] = {}
            self._clients: dict[str, MediaClientClass] = {}
            self._settings: Settings | None = None

    def __new__(cls) -> ClientRegistry:
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(
        self,
        descriptor_or_type: ProviderDescriptor | str,
        client_class: MediaClientClass | None = None,
        /,
    ) -> None:
        """Register a provider or client implementation.

        Supports two call signatures:
        - register(descriptor) — new ProviderDescriptor-based registration
        - register(server_type, client_class) — legacy registration

        Args:
            descriptor_or_type: A ProviderDescriptor instance, or a server type
                string/enum for legacy usage.
            client_class: Client class for legacy registration (only used when
                first arg is a string/enum).
        """
        if client_class is not None:
            # Legacy call: register(server_type, client_class)
            key = str(descriptor_or_type)
            self._clients[key] = client_class
        else:
            # New call: register(descriptor)
            descriptor: ProviderDescriptor = descriptor_or_type  # pyright: ignore[reportAssignmentType]
            key = descriptor.metadata.server_type
            self._providers[key] = descriptor
            self._clients[key] = descriptor.client_class

    def registered_types(self) -> frozenset[str]:
        """Return all registered server type strings."""
        return frozenset(self._clients.keys())

    def get_provider(self, server_type: str, /) -> ProviderDescriptor:
        """Get the ProviderDescriptor for a server type.

        Args:
            server_type: The server type string.

        Returns:
            The registered ProviderDescriptor.

        Raises:
            UnknownServerTypeError: If no provider is registered.
        """
        key = str(server_type)
        if (provider := self._providers.get(key)) is None:
            raise UnknownServerTypeError(key)
        return provider

    def get_client_class(self, server_type: str, /) -> MediaClientClass:
        """Get the client class for a server type.

        Args:
            server_type: The server type string or enum.

        Returns:
            The registered client class.

        Raises:
            UnknownServerTypeError: If no client is registered.
        """
        key = str(server_type)
        if (client_class := self._clients.get(key)) is None:
            raise UnknownServerTypeError(key)
        return client_class

    def get_capabilities(self, server_type: str, /) -> set[Capability]:
        """Get capabilities for a server type."""
        return self.get_client_class(server_type).capabilities()

    def get_supported_permissions(self, server_type: str, /) -> frozenset[str]:
        """Get supported permissions for a server type."""
        return self.get_client_class(server_type).supported_permissions()

    def get_all_metadata(self) -> list[ProviderMetadata]:
        """Get metadata for all registered providers."""
        return [desc.metadata for desc in self._providers.values()]

    def get_all_descriptors(self) -> list[ProviderDescriptor]:
        """Get all registered ProviderDescriptor instances."""
        return list(self._providers.values())

    def get_admin_auth_descriptors(self) -> list[AdminAuthDescriptor]:
        """Get admin auth descriptors for all providers that support it."""
        result: list[AdminAuthDescriptor] = []
        for desc in self._providers.values():
            if desc.admin_auth is not None:
                result.append(desc.admin_auth)
        return result

    def get_admin_auth_provider(self, method: str) -> AdminAuthProvider | None:
        """Get the admin auth provider for a given method name.

        Args:
            method: The auth method name (e.g., "plex", "jellyfin").

        Returns:
            The AdminAuthProvider instance, or None if not found.
        """
        for desc in self._providers.values():
            if desc.admin_auth is not None and desc.admin_auth.method_name == method:
                return desc.admin_auth_provider
        return None

    def create_client(
        self,
        server_type: str,
        /,
        *,
        url: str,
        api_key: str,
    ) -> MediaClient:
        """Create a client instance for a media server.

        Args:
            server_type: The server type string or enum.
            url: The base URL of the media server.
            api_key: The API key for authentication.

        Returns:
            A new client instance.

        Raises:
            UnknownServerTypeError: If no client is registered.
        """
        client_class = self.get_client_class(server_type)
        return client_class(url=url, api_key=api_key)

    def set_settings(self, settings: Settings) -> None:
        """Inject application settings for env var credential overrides.

        If provider_credentials is not already populated, populate it
        from env vars using registry metadata + legacy fields.
        """
        if not settings.provider_credentials:
            self._populate_provider_credentials(settings)

        self._settings = settings

    def _populate_provider_credentials(self, settings: Settings) -> None:
        """Populate provider_credentials from env vars using registry metadata.

        Reads each registered provider's declared env var names and populates
        the provider_credentials dict. Falls back to legacy fields for
        backwards compatibility.
        """
        provider_creds: dict[str, dict[str, str]] = {}

        for meta in self.get_all_metadata():
            creds: dict[str, str] = {}

            url_val = os.environ.get(meta.env_url_var) or None
            if url_val:
                creds["url"] = url_val

            api_key_val = os.environ.get(meta.env_api_key_var) or None
            if api_key_val:
                creds["api_key"] = api_key_val

            if creds:
                provider_creds[meta.server_type] = creds

        # Backwards compatibility: also check legacy fields
        # Only use legacy values when the provider doesn't already have that key
        if settings.plex_url:
            _ = provider_creds.setdefault("plex", {}).setdefault(
                "url", settings.plex_url
            )
        if settings.plex_token:
            _ = provider_creds.setdefault("plex", {}).setdefault(
                "api_key", settings.plex_token
            )
        if settings.jellyfin_url:
            _ = provider_creds.setdefault("jellyfin", {}).setdefault(
                "url", settings.jellyfin_url
            )
        if settings.jellyfin_api_key:
            _ = provider_creds.setdefault("jellyfin", {}).setdefault(
                "api_key", settings.jellyfin_api_key
            )

        settings.provider_credentials = provider_creds

    def _get_effective_credentials(
        self,
        server_type: str,
        *,
        db_url: str,
        db_api_key: str,
    ) -> tuple[str, str]:
        """Resolve effective credentials (env vars > DB).

        Dynamically reads env var names from provider metadata,
        removing the need for per-provider if/else branches.

        Args:
            server_type: The server type string.
            db_url: The URL stored in the database.
            db_api_key: The API key stored in the database.

        Returns:
            A tuple of (effective_url, effective_api_key).
        """
        if self._settings is None:
            return db_url, db_api_key

        key = str(server_type)

        # Try provider credentials from settings first
        provider_creds = self._settings.provider_credentials.get(key, {})
        url = provider_creds.get("url") or db_url
        api_key = provider_creds.get("api_key") or db_api_key

        return url, api_key

    def create_client_for_server(self, server: MediaServer, /) -> MediaClient:
        """Create a client for a media server, applying env var overrides.

        Args:
            server: The MediaServer entity.

        Returns:
            A new client instance with effective credentials.

        Raises:
            UnknownServerTypeError: If no client is registered.
        """
        server_type = str(server.server_type)
        url, api_key = self._get_effective_credentials(
            server_type,
            db_url=server.url,
            db_api_key=server.api_key,
        )
        return self.create_client(server_type, url=url, api_key=api_key)

    def clear(self) -> None:
        """Clear all registered providers and clients."""
        self._providers.clear()
        self._clients.clear()
        self._settings = None


# Global registry instance for convenient access
registry = ClientRegistry()
