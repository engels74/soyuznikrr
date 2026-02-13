"""Plex media server provider.

Implements ProviderDescriptor for Plex, declaring metadata,
client class, admin auth, join flow, and OAuth support.
"""

from typing import TYPE_CHECKING

from zondarr.media.provider import (
    AdminAuthDescriptor,
    AuthFlowType,
    JoinFlowDescriptor,
    JoinFlowType,
    MediaClientClass,
    OAuthCheckResult,
    OAuthPinResult,
    ProviderMetadata,
)

from .auth import PlexAdminAuth
from .client import PlexClient
from .oauth_service import PlexOAuthError, PlexOAuthService

if TYPE_CHECKING:
    from zondarr.config import Settings

# Plex logo SVG path data (simplified play button triangle)
_PLEX_ICON_SVG = "M5.5 3L18.5 12L5.5 21V3Z"

# Default client identifier for Plex OAuth
_DEFAULT_PLEX_CLIENT_ID = "zondarr-oauth-client"


class _PlexOAuthFlowAdapter:
    """Adapts PlexOAuthService to the OAuthFlowProvider protocol."""

    _service: PlexOAuthService

    def __init__(self, service: PlexOAuthService) -> None:
        self._service = service

    async def create_pin(self) -> OAuthPinResult:
        """Generate a Plex OAuth PIN."""
        pin = await self._service.create_pin()
        return OAuthPinResult(
            pin_id=pin.pin_id,
            code=pin.code,
            auth_url=pin.auth_url,
            expires_at=pin.expires_at,
        )

    async def check_pin(self, pin_id: int, /) -> OAuthCheckResult:
        """Check if a Plex PIN has been authenticated."""
        try:
            result = await self._service.check_pin(pin_id)
            return OAuthCheckResult(
                authenticated=result.authenticated,
                auth_token=result.auth_token,
                email=result.email,
                error=result.error,
            )
        except PlexOAuthError as exc:
            return OAuthCheckResult(
                authenticated=False,
                error=exc.message,
            )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._service.close()


# Module-level cached instances (immutable msgspec Structs / stateless objects)
_PLEX_METADATA = ProviderMetadata(
    server_type="plex",
    display_name="Plex",
    color="#E5A00D",
    icon_svg=_PLEX_ICON_SVG,
    env_url_var="PLEX_URL",
    env_api_key_var="PLEX_TOKEN",
    api_key_help_text="Plex authentication token (X-Plex-Token)",
)
_PLEX_ADMIN_AUTH = AdminAuthDescriptor(
    method_name="plex",
    display_name="Plex",
    flow_type=AuthFlowType.OAUTH,
)
_PLEX_ADMIN_AUTH_PROVIDER = PlexAdminAuth()
_PLEX_JOIN_FLOW = JoinFlowDescriptor(flow_type=JoinFlowType.OAUTH_LINK)


class PlexProvider:
    """Plex ProviderDescriptor implementation."""

    @property
    def metadata(self) -> ProviderMetadata:
        return _PLEX_METADATA

    @property
    def client_class(self) -> MediaClientClass:
        return PlexClient

    @property
    def admin_auth(self) -> AdminAuthDescriptor:
        return _PLEX_ADMIN_AUTH

    @property
    def admin_auth_provider(self) -> PlexAdminAuth:
        return _PLEX_ADMIN_AUTH_PROVIDER

    @property
    def join_flow(self) -> JoinFlowDescriptor:
        return _PLEX_JOIN_FLOW

    @property
    def route_handlers(self) -> list[type] | None:
        return None

    def create_oauth_flow_provider(self, settings: Settings) -> _PlexOAuthFlowAdapter:
        """Create a Plex OAuth flow provider."""
        del settings  # unused; client_id is a fixed default
        service = PlexOAuthService(client_id=_DEFAULT_PLEX_CLIENT_ID)
        return _PlexOAuthFlowAdapter(service)
