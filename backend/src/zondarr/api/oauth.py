"""Generic OAuth controller for provider-agnostic OAuth flows.

Provides endpoints for OAuth PIN-based authentication during invitation
redemption, delegating to provider-specific OAuth implementations via the
registry:
- POST /api/v1/join/{provider}/oauth/pin - Create a new OAuth PIN
- GET /api/v1/join/{provider}/oauth/pin/{handle} - Check PIN status

PIN sessions are tracked server-side with opaque handles. Raw provider
auth_tokens are never exposed to the frontend; instead, a one-time
redemption token is returned on successful authentication.

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
from zondarr.services.oauth_session import oauth_session_store

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
    registry's create_oauth_flow_provider() method. PIN sessions are
    tracked server-side with opaque handles to prevent enumeration.
    """

    path: str = "/api/v1/join/{provider:str}/oauth"
    tags: Sequence[str] | None = ["OAuth"]

    @post(
        "/pin",
        status_code=HTTP_200_OK,
        summary="Create OAuth PIN",
        description=(
            "Generate a PIN for OAuth authentication. "
            "The user should be directed to the auth_url to complete authentication. "
            "Returns an opaque handle for polling the PIN status."
        ),
        exclude_from_auth=True,
    )
    async def create_pin(
        self,
        settings: Settings,
        provider: Annotated[str, Parameter(description="Provider name")],
    ) -> OAuthPinResponse:
        """Generate OAuth PIN and return auth URL with opaque handle.

        Args:
            settings: Application settings (injected via DI).
            provider: Provider name from URL path.

        Returns:
            OAuthPinResponse with handle, code, auth_url, and expires_at.
        """
        flow = _resolve_flow(provider, settings)
        try:
            pin = await flow.create_pin()
            handle = oauth_session_store.create(
                provider,
                pin.pin_id,
            )
            return OAuthPinResponse(
                handle=handle,
                code=pin.code,
                auth_url=pin.auth_url,
                expires_at=pin.expires_at,
            )
        finally:
            await flow.close()

    @get(
        "/pin/{handle:str}",
        status_code=HTTP_200_OK,
        summary="Check OAuth PIN status",
        description=(
            "Check if a PIN has been authenticated. "
            "Returns a one-time redemption token (not the raw auth token) "
            "if authentication is complete."
        ),
        exclude_from_auth=True,
    )
    async def check_pin(
        self,
        settings: Settings,
        provider: Annotated[str, Parameter(description="Provider name")],
        handle: Annotated[str, Parameter(description="Opaque PIN handle")],
    ) -> OAuthCheckResponse:
        """Check if PIN has been authenticated.

        Looks up the session by opaque handle, verifies the provider matches,
        then delegates to the provider to check the PIN status. If authenticated,
        the raw auth_token is stored server-side and a one-time redemption token
        is returned instead.

        Args:
            settings: Application settings (injected via DI).
            provider: Provider name from URL path.
            handle: The opaque PIN handle from create_pin.

        Returns:
            OAuthCheckResponse with authenticated status and redemption_token if successful.
        """
        session = oauth_session_store.get(handle)
        if session is None:
            raise NotFoundError("OAuthSession", handle)
        if session.provider != provider:
            raise NotFoundError("OAuthSession", handle)

        # If already authenticated, return the existing redemption token
        if session.redemption_token is not None and not session.redeemed:
            return OAuthCheckResponse(
                authenticated=True,
                redemption_token=session.redemption_token,
                email=session.email,
            )

        flow = _resolve_flow(provider, settings)
        try:
            result = await flow.check_pin(session.pin_id)
            if result.authenticated and result.auth_token:
                redemption_token = oauth_session_store.set_authenticated(
                    handle,
                    auth_token=result.auth_token,
                    email=result.email,
                )
                return OAuthCheckResponse(
                    authenticated=True,
                    redemption_token=redemption_token,
                    email=result.email,
                )
            return OAuthCheckResponse(
                authenticated=result.authenticated,
                error=result.error,
            )
        finally:
            await flow.close()
