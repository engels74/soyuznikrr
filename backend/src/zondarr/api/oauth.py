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
from typing import TYPE_CHECKING, Annotated, cast

import structlog
from litestar import Controller, Response, get, post
from litestar.datastructures import State
from litestar.openapi.datastructures import ResponseSpec
from litestar.params import Parameter
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from zondarr.api.schemas import ErrorResponse, OAuthCheckResponse, OAuthPinResponse
from zondarr.config import Settings
from zondarr.core.exceptions import ExternalServiceError, NotFoundError
from zondarr.media.exceptions import UnknownServerTypeError
from zondarr.media.providers.plex.oauth_service import PlexOAuthError
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
        responses={
            502: ResponseSpec(
                data_container=ErrorResponse,
                description="External provider unavailable.",
            ),
        },
    )
    async def create_pin(
        self,
        settings: Settings,
        state: State,
        provider: Annotated[str, Parameter(description="Provider name")],
    ) -> OAuthPinResponse:
        """Generate OAuth PIN and return auth URL with opaque handle.

        Args:
            settings: Application settings (injected via DI).
            state: Application state containing session factory (injected via DI).
            provider: Provider name from URL path.

        Returns:
            OAuthPinResponse with handle, code, auth_url, and expires_at.
        """
        # Phase 1: External HTTP call (no DB session held)
        flow = _resolve_flow(provider, settings)
        try:
            pin = await flow.create_pin()
        except PlexOAuthError as exc:
            logger.warning(
                "oauth_create_pin_external_failure",
                provider=provider,
                operation=exc.operation,
                error=exc.message,
            )
            raise ExternalServiceError(provider, exc.message, original=exc) from exc
        finally:
            await flow.close()

        # Phase 2: Store session in DB (short-lived session)
        session_factory = cast(async_sessionmaker[AsyncSession], state.session_factory)
        async with session_factory() as session:
            handle = await _store.create(
                session,
                provider,
                pin.pin_id,
            )
            await session.commit()

        return OAuthPinResponse(
            handle=handle,
            code=pin.code,
            auth_url=pin.auth_url,
            expires_at=pin.expires_at,
        )

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
        responses={
            502: ResponseSpec(
                data_container=ErrorResponse,
                description="External provider unavailable.",
            ),
        },
    )
    async def check_pin(
        self,
        settings: Settings,
        state: State,
        provider: Annotated[str, Parameter(description="Provider name")],
        handle: Annotated[str, Parameter(description="Opaque PIN handle")],
    ) -> OAuthCheckResponse:
        """Check if PIN has been authenticated.

        Uses short-lived database sessions to avoid holding SQLite's write lock
        across the external HTTP call to the provider. Three phases:
        1. Read session data (short-lived DB session)
        2. Check PIN with provider (no DB session held)
        3. Write authentication result (short-lived DB session)

        Args:
            settings: Application settings (injected via DI).
            state: Application state containing session factory (injected via DI).
            provider: Provider name from URL path.
            handle: The opaque PIN handle from create_pin.

        Returns:
            OAuthCheckResponse with authenticated status and redemption_token if successful.
        """
        session_factory = cast(async_sessionmaker[AsyncSession], state.session_factory)

        # Phase 1: Read session data (short-lived, may write if expired)
        async with session_factory() as read_session:
            oauth_session = await _store.get(read_session, handle)
            if oauth_session is None:
                await read_session.commit()  # persist any expired-session cleanup
                raise NotFoundError("OAuthSession", handle)
            if oauth_session.provider != provider:
                await read_session.commit()
                raise NotFoundError("OAuthSession", handle)

            # If already authenticated, return the existing redemption token
            if (
                oauth_session.redemption_token is not None
                and not oauth_session.redeemed
            ):
                return OAuthCheckResponse(
                    authenticated=True,
                    redemption_token=oauth_session.redemption_token,
                    email=oauth_session.email,
                )
            pin_id = oauth_session.pin_id
            await read_session.commit()
        # Session closed — no write lock held

        # Phase 2: External HTTP call (no DB session)
        flow = _resolve_flow(provider, settings)
        try:
            result = await flow.check_pin(pin_id)
        except PlexOAuthError as exc:
            logger.warning(
                "oauth_check_pin_external_failure",
                provider=provider,
                handle_prefix=handle[:8],
                operation=exc.operation,
                error=exc.message,
            )
            raise ExternalServiceError(provider, exc.message, original=exc) from exc
        finally:
            await flow.close()

        # Phase 3: Write authentication result (short-lived)
        if result.authenticated and result.auth_token:
            async with session_factory() as write_session:
                redemption_token = await _store.set_authenticated(
                    write_session,
                    handle,
                    auth_token=result.auth_token,
                    email=result.email,
                )
                await write_session.commit()
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
        responses={
            200: ResponseSpec(
                data_container=OAuthCheckResponse,
                description="OAuth PIN completion result.",
            ),
            400: ResponseSpec(
                data_container=ErrorResponse,
                description="Test credentials missing or session already redeemed.",
            ),
        },
    )
    async def test_complete_pin(
        self,
        settings: Settings,
        state: State,
        provider: Annotated[str, Parameter(description="Provider name")],
        handle: Annotated[str, Parameter(description="Opaque PIN handle")],
    ) -> OAuthCheckResponse | Response[ErrorResponse]:
        """Simulate OAuth PIN completion for E2E testing.

        Only available when debug mode is enabled and test credentials
        are configured via PLEX_TEST_TOKEN and PLEX_TEST_EMAIL env vars.

        Args:
            settings: Application settings (injected via DI).
            state: Application state containing session factory (injected via DI).
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

        session_factory = cast(async_sessionmaker[AsyncSession], state.session_factory)

        # Phase 1: Read session data (short-lived)
        async with session_factory() as read_session:
            oauth_session = await _store.get(read_session, handle)
            if oauth_session is None:
                await read_session.commit()  # persist any expired-session cleanup
                raise NotFoundError("OAuthSession", handle)
            if oauth_session.provider != provider:
                await read_session.commit()
                raise NotFoundError("OAuthSession", handle)

            # If already authenticated but not yet redeemed, return existing token
            if (
                oauth_session.redemption_token is not None
                and not oauth_session.redeemed
            ):
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
            await read_session.commit()

        # Phase 2: Write authentication result (short-lived)
        async with session_factory() as write_session:
            redemption_token = await _store.set_authenticated(
                write_session,
                handle,
                auth_token=settings.plex_test_token,
                email=settings.plex_test_email,
            )
            await write_session.commit()

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
