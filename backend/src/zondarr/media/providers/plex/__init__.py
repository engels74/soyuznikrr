"""Plex media server provider.

Implements ProviderDescriptor for Plex, declaring metadata,
client class, admin auth, join flow, and route handlers.
"""

from zondarr.media.provider import (
    AdminAuthDescriptor,
    AuthFlowType,
    JoinFlowDescriptor,
    JoinFlowType,
    MediaClientClass,
    ProviderMetadata,
)

from .auth import PlexAdminAuth
from .client import PlexClient
from .controller import PlexOAuthController

# Plex logo SVG path (simplified play button triangle)
_PLEX_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">'
    '<path d="M5.5 3L18.5 12L5.5 21V3Z"/>'
    "</svg>"
)


class PlexProvider:
    """Plex ProviderDescriptor implementation."""

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            server_type="plex",
            display_name="Plex",
            color="#E5A00D",
            icon_svg=_PLEX_ICON_SVG,
            env_url_var="PLEX_URL",
            env_api_key_var="PLEX_TOKEN",
            api_key_help_text="Plex authentication token (X-Plex-Token)",
        )

    @property
    def client_class(self) -> MediaClientClass:
        return PlexClient

    @property
    def admin_auth(self) -> AdminAuthDescriptor:
        return AdminAuthDescriptor(
            method_name="plex",
            display_name="Plex",
            flow_type=AuthFlowType.OAUTH,
        )

    @property
    def admin_auth_provider(self) -> PlexAdminAuth:
        return PlexAdminAuth()

    @property
    def join_flow(self) -> JoinFlowDescriptor:
        return JoinFlowDescriptor(flow_type=JoinFlowType.OAUTH_LINK)

    @property
    def route_handlers(self) -> list[type]:
        return [PlexOAuthController]
