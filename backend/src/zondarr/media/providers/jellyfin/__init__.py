"""Jellyfin media server provider.

Implements ProviderDescriptor for Jellyfin, declaring metadata,
client class, admin auth, join flow, and route handlers.
"""

from typing import TYPE_CHECKING

from zondarr.media.provider import (
    AdminAuthDescriptor,
    AuthFieldDescriptor,
    AuthFlowType,
    JoinFlowDescriptor,
    JoinFlowType,
    MediaClientClass,
    ProviderMetadata,
)

if TYPE_CHECKING:
    from zondarr.config import Settings

from .auth import JellyfinAdminAuth
from .client import JellyfinClient

# Jellyfin logo SVG path data (simplified)
_JELLYFIN_ICON_SVG = (
    "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2"
    " 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"
)


# Module-level cached instances (immutable msgspec Structs / stateless objects)
_JELLYFIN_METADATA = ProviderMetadata(
    server_type="jellyfin",
    display_name="Jellyfin",
    color="#00A4DC",
    icon_svg=_JELLYFIN_ICON_SVG,
    env_url_var="JELLYFIN_URL",
    env_api_key_var="JELLYFIN_API_KEY",
    api_key_help_text="Jellyfin API key (from Dashboard > API Keys)",
)
_JELLYFIN_ADMIN_AUTH = AdminAuthDescriptor(
    method_name="jellyfin",
    display_name="Jellyfin",
    flow_type=AuthFlowType.CREDENTIALS,
    fields=[
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
_JELLYFIN_ADMIN_AUTH_PROVIDER = JellyfinAdminAuth()
_JELLYFIN_JOIN_FLOW = JoinFlowDescriptor(flow_type=JoinFlowType.CREDENTIAL_CREATE)


class JellyfinProvider:
    """Jellyfin ProviderDescriptor implementation."""

    @property
    def metadata(self) -> ProviderMetadata:
        return _JELLYFIN_METADATA

    @property
    def client_class(self) -> MediaClientClass:
        return JellyfinClient

    @property
    def admin_auth(self) -> AdminAuthDescriptor:
        return _JELLYFIN_ADMIN_AUTH

    @property
    def admin_auth_provider(self) -> JellyfinAdminAuth:
        return _JELLYFIN_ADMIN_AUTH_PROVIDER

    @property
    def join_flow(self) -> JoinFlowDescriptor:
        return _JELLYFIN_JOIN_FLOW

    @property
    def route_handlers(self) -> list[type] | None:
        return None

    def create_oauth_flow_provider(
        self,
        settings: Settings,
    ) -> None:
        """Jellyfin does not support OAuth flows."""
        del settings  # required by ProviderDescriptor protocol
        return None
