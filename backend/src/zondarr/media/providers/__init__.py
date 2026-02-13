"""Media server provider registration.

Imports and registers all available provider implementations.
Called during application startup before settings are loaded.
"""

from zondarr.media.registry import registry

from .jellyfin import JellyfinProvider
from .plex import PlexProvider


def register_all_providers() -> None:
    """Register all media server provider implementations.

    Idempotent: skips registration if providers are already registered.
    """
    if registry.registered_types():
        return
    registry.register(PlexProvider())
    registry.register(JellyfinProvider())
