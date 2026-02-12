"""Jellyfin media server provider.

Implements ProviderDescriptor for Jellyfin, declaring metadata,
client class, admin auth, join flow, and route handlers.
"""

from zondarr.media.provider import (
    AdminAuthDescriptor,
    AuthFieldDescriptor,
    AuthFlowType,
    JoinFlowDescriptor,
    JoinFlowType,
    MediaClientClass,
    ProviderMetadata,
)

from .auth import JellyfinAdminAuth
from .client import JellyfinClient

# Jellyfin logo SVG (simplified)
_JELLYFIN_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">'
    '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2'
    " 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"
    '"/>'
    "</svg>"
)


class JellyfinProvider:
    """Jellyfin ProviderDescriptor implementation."""

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            server_type="jellyfin",
            display_name="Jellyfin",
            color="#00A4DC",
            icon_svg=_JELLYFIN_ICON_SVG,
            env_url_var="JELLYFIN_URL",
            env_api_key_var="JELLYFIN_API_KEY",
            api_key_help_text="Jellyfin API key (from Dashboard > API Keys)",
        )

    @property
    def client_class(self) -> MediaClientClass:
        return JellyfinClient

    @property
    def admin_auth(self) -> AdminAuthDescriptor:
        return AdminAuthDescriptor(
            method_name="jellyfin",
            display_name="Jellyfin",
            flow_type=AuthFlowType.CREDENTIALS,
            fields=[
                AuthFieldDescriptor(
                    name="server_url",
                    label="Server URL",
                    field_type="url",
                    placeholder="http://jellyfin.local:8096",
                ),
                AuthFieldDescriptor(
                    name="username",
                    label="Username",
                    field_type="text",
                    placeholder="admin",
                ),
                AuthFieldDescriptor(
                    name="password",
                    label="Password",
                    field_type="password",
                ),
            ],
        )

    @property
    def admin_auth_provider(self) -> JellyfinAdminAuth:
        return JellyfinAdminAuth()

    @property
    def join_flow(self) -> JoinFlowDescriptor:
        return JoinFlowDescriptor(flow_type=JoinFlowType.CREDENTIAL_CREATE)

    @property
    def route_handlers(self) -> list[type] | None:
        return None
