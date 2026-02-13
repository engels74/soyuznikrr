"""Generic OAuth controller for provider-agnostic OAuth flows.

Provides endpoints for OAuth PIN-based authentication during invitation
redemption, delegating to provider-specific OAuth implementations via the
registry:
- POST /api/v1/join/{provider}/oauth/pin - Create a new OAuth PIN
- GET /api/v1/join/{provider}/oauth/pin/{pin_id} - Check PIN status

These endpoints are publicly accessible without authentication.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated

from litestar import Controller, get, post
from litestar.params import Parameter
from litestar.status_codes import HTTP_200_OK

from zondarr.api.schemas import OAuthCheckResponse, OAuthPinResponse
from zondarr.config import Settings
from zondarr.core.exceptions import NotFoundError
from zondarr.media.exceptions import UnknownServerTypeError
from zondarr.media.registry import registry

if TYPE_CHECKING:
    from zondarr.media.provider import OAuthFlowProvider


def _resolve_flow(provider: str, settings: Settings) -> OAuthFlowProvider:
    """Resolve an OAuth flow provider or raise NotFoundError.

    Args:
        provider: The provider name.
        settings: Application settings.

    Returns:
        An OAuthFlowProvider instance.

    Raises:
        NotFoundError: If the provider is unknown or doesn't support OAuth.
    """
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
        settings: Settings,
        provider: Annotated[str, Parameter(description="Provider name")],
    ) -> OAuthPinResponse:
        """Generate OAuth PIN and return auth URL.

        Args:
            settings: Application settings (injected via DI).
            provider: Provider name from URL path.

        Returns:
            OAuthPinResponse with pin_id, code, auth_url, and expires_at.
        """
        flow = _resolve_flow(provider, settings)
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
        settings: Settings,
        provider: Annotated[str, Parameter(description="Provider name")],
        pin_id: Annotated[int, Parameter(description="PIN ID to check")],
    ) -> OAuthCheckResponse:
        """Check if PIN has been authenticated.

        Args:
            settings: Application settings (injected via DI).
            provider: Provider name from URL path.
            pin_id: The PIN ID to check.

        Returns:
            OAuthCheckResponse with authenticated status and email if successful.
        """
        flow = _resolve_flow(provider, settings)
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
