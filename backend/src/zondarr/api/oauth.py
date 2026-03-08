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
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

import structlog
from litestar import Controller, Response, get, post
from litestar.params import Parameter
from litestar.status_codes import HTTP_200_OK, HTTP_400_BAD_REQUEST
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.api.schemas import ErrorResponse, OAuthCheckResponse, OAuthPinResponse
from zondarr.config import Settings
from zondarr.core.exceptions import NotFoundError
from zondarr.media.exceptions import UnknownServerTypeError
from zondarr.media.registry import registry
from zondarr.services.oauth_session import OAuthSessionStore

if TYPE_CHECKING:
    from zondarr.media.provider import OAuthFlowProvider

logger: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]

_store = OAuthSessionStore()


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
        session: AsyncSession,
        provider: Annotated[str, Parameter(description="Provider name")],
    ) -> OAuthPinResponse:
        """Generate OAuth PIN and return auth URL with opaque handle.

        Args:
            settings: Application settings (injected via DI).
            session: Database session (injected via DI).
            provider: Provider name from URL path.

        Returns:
            OAuthPinResponse with handle, code, auth_url, and expires_at.
        """
        flow = _resolve_flow(provider, settings)
        try:
            pin = await flow.create_pin()
            handle = await _store.create(
                session,
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
        session: AsyncSession,
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
            session: Database session (injected via DI).
            provider: Provider name from URL path.
            handle: The opaque PIN handle from create_pin.

        Returns:
            OAuthCheckResponse with authenticated status and redemption_token if successful.
        """
        oauth_session = await _store.get(session, handle)
        if oauth_session is None:
            raise NotFoundError("OAuthSession", handle)
        if oauth_session.provider != provider:
            raise NotFoundError("OAuthSession", handle)

        # If already authenticated, return the existing redemption token
        if oauth_session.redemption_token is not None and not oauth_session.redeemed:
            return OAuthCheckResponse(
                authenticated=True,
                redemption_token=oauth_session.redemption_token,
                email=oauth_session.email,
            )

        flow = _resolve_flow(provider, settings)
        try:
            result = await flow.check_pin(oauth_session.pin_id)
            if result.authenticated and result.auth_token:
                redemption_token = await _store.set_authenticated(
                    session,
                    handle,
                    auth_token=result.auth_token,
                    email=result.email,
                )
                if redemption_token is None:
                    raise NotFoundError("OAuthSession", handle)
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

    @post(
        "/pin/{handle:str}/test-complete",
        status_code=HTTP_200_OK,
        summary="Simulate OAuth PIN completion (debug only)",
        description=(
            "Debug-only endpoint that simulates OAuth PIN completion using "
            "test credentials from environment variables. Returns 404 when "
            "debug mode is disabled."
        ),
        exclude_from_auth=True,
    )
    async def test_complete_pin(
        self,
        settings: Settings,
        session: AsyncSession,
        provider: Annotated[str, Parameter(description="Provider name")],
        handle: Annotated[str, Parameter(description="Opaque PIN handle")],
    ) -> OAuthCheckResponse | Response[ErrorResponse]:
        """Simulate OAuth PIN completion for E2E testing.

        Only available when debug mode is enabled and test credentials
        are configured via PLEX_TEST_TOKEN and PLEX_TEST_EMAIL env vars.

        Args:
            settings: Application settings (injected via DI).
            session: Database session (injected via DI).
            provider: Provider name from URL path.
            handle: The opaque PIN handle from create_pin.

        Returns:
            OAuthCheckResponse with authenticated status and redemption_token.
        """
        if not settings.debug:
            raise NotFoundError("Endpoint", "test-complete")

        if not settings.plex_test_token or not settings.plex_test_email:
            return Response(
                ErrorResponse(
                    detail="PLEX_TEST_TOKEN and PLEX_TEST_EMAIL must be configured",
                    error_code="TEST_CREDENTIALS_MISSING",
                    timestamp=datetime.now(UTC),
                ),
                status_code=HTTP_400_BAD_REQUEST,
            )

        oauth_session = await _store.get(session, handle)
        if oauth_session is None:
            raise NotFoundError("OAuthSession", handle)
        if oauth_session.provider != provider:
            raise NotFoundError("OAuthSession", handle)

        # If already authenticated but not yet redeemed, return existing token
        if oauth_session.redemption_token is not None and not oauth_session.redeemed:
            return OAuthCheckResponse(
                authenticated=True,
                redemption_token=oauth_session.redemption_token,
                email=oauth_session.email,
            )

        # If already redeemed, the session has been consumed
        if oauth_session.redeemed:
            return Response(
                ErrorResponse(
                    detail="OAuth session has already been redeemed",
                    error_code="SESSION_ALREADY_REDEEMED",
                    timestamp=datetime.now(UTC),
                ),
                status_code=HTTP_400_BAD_REQUEST,
            )

        redemption_token = await _store.set_authenticated(
            session,
            handle,
            auth_token=settings.plex_test_token,
            email=settings.plex_test_email,
        )
        if redemption_token is None:
            raise NotFoundError("OAuthSession", handle)

        logger.info(
            "oauth_test_complete_used",
            provider=provider,
            handle_prefix=handle[:8],
            has_email=True,
        )

        return OAuthCheckResponse(
            authenticated=True,
            redemption_token=redemption_token,
            email=settings.plex_test_email,
        )
