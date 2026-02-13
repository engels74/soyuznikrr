"""Generic OAuth controller for provider-agnostic OAuth flows.

Provides endpoints for OAuth PIN-based authentication during invitation
redemption, delegating to provider-specific OAuth implementations via the
registry:
- POST /api/v1/join/{provider}/oauth/pin - Create a new OAuth PIN
- GET /api/v1/join/{provider}/oauth/pin/{pin_id} - Check PIN status

These endpoints are publicly accessible without authentication.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

import msgspec
from litestar import Controller, get, post
from litestar.datastructures import State
from litestar.params import Parameter
from litestar.status_codes import HTTP_200_OK

from zondarr.config import Settings
from zondarr.core.exceptions import NotFoundError
from zondarr.media.exceptions import UnknownServerTypeError
from zondarr.media.registry import registry

if TYPE_CHECKING:
    from zondarr.media.provider import OAuthFlowProvider


class OAuthPinResponse(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Response from OAuth PIN creation.

    Attributes:
        pin_id: The PIN identifier for status checking.
        code: The PIN code to display to the user.
        auth_url: URL where user authenticates.
        expires_at: When the PIN expires.
    """

    pin_id: int
    code: str
    auth_url: str
    expires_at: datetime


class OAuthCheckResponse(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Response from OAuth PIN status check.

    Attributes:
        authenticated: Whether the PIN has been authenticated.
        auth_token: Auth token (only if authenticated).
        email: User's email (only if authenticated).
        error: Error message (only if failed).
    """

    authenticated: bool
    auth_token: str | None = None
    email: str | None = None
    error: str | None = None


def _resolve_flow(provider: str, state: State) -> OAuthFlowProvider:
    """Resolve an OAuth flow provider or raise NotFoundError.

    Args:
        provider: The provider name.
        state: Application state containing settings.

    Returns:
        An OAuthFlowProvider instance.

    Raises:
        NotFoundError: If the provider is unknown or doesn't support OAuth.
    """
    settings = state.get("settings")
    if not isinstance(settings, Settings):
        msg = "Settings not found in application state"
        raise RuntimeError(msg)

    try:
        flow = registry.create_oauth_flow_provider(provider, settings)
    except UnknownServerTypeError:
        raise NotFoundError("OAuthProvider", provider) from None

    if flow is None:
        raise NotFoundError("OAuthProvider", provider)

    return flow


class OAuthController(Controller):
    """Controller for generic OAuth flow endpoints.

    Delegates to provider-specific OAuth implementations via the
    registry's create_oauth_flow_provider() method.
    """

    path: str = "/api/v1/join/{provider:str}/oauth"
    tags: Sequence[str] | None = ["OAuth"]

    @post(
        "/pin",
        status_code=HTTP_200_OK,
        summary="Create OAuth PIN",
        description=(
            "Generate a PIN for OAuth authentication. "
            "The user should be directed to the auth_url to complete authentication."
        ),
        exclude_from_auth=True,
    )
    async def create_pin(
        self,
        state: State,
        provider: Annotated[str, Parameter(description="Provider name")],
    ) -> OAuthPinResponse:
        """Generate OAuth PIN and return auth URL.

        Args:
            state: Application state.
            provider: Provider name from URL path.

        Returns:
            OAuthPinResponse with pin_id, code, auth_url, and expires_at.
        """
        flow = _resolve_flow(provider, state)
        try:
            pin = await flow.create_pin()
            return OAuthPinResponse(
                pin_id=pin.pin_id,
                code=pin.code,
                auth_url=pin.auth_url,
                expires_at=pin.expires_at,
            )
        finally:
            await flow.close()

    @get(
        "/pin/{pin_id:int}",
        status_code=HTTP_200_OK,
        summary="Check OAuth PIN status",
        description=(
            "Check if a PIN has been authenticated. "
            "Returns the user's email if authentication is complete."
        ),
        exclude_from_auth=True,
    )
    async def check_pin(
        self,
        state: State,
        provider: Annotated[str, Parameter(description="Provider name")],
        pin_id: Annotated[int, Parameter(description="PIN ID to check")],
    ) -> OAuthCheckResponse:
        """Check if PIN has been authenticated.

        Args:
            state: Application state.
            provider: Provider name from URL path.
            pin_id: The PIN ID to check.

        Returns:
            OAuthCheckResponse with authenticated status and email if successful.
        """
        flow = _resolve_flow(provider, state)
        try:
            result = await flow.check_pin(pin_id)
            return OAuthCheckResponse(
                authenticated=result.authenticated,
                auth_token=result.auth_token,
                email=result.email,
                error=result.error,
            )
        finally:
            await flow.close()
