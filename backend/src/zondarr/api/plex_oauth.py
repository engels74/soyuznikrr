"""PlexOAuthController for Plex OAuth PIN-based authentication.

Provides public endpoints for the Plex OAuth PIN-based authentication
flow used during invitation redemption:
- POST /api/v1/join/plex/oauth/pin - Create a new OAuth PIN
- GET /api/v1/join/plex/oauth/pin/{pin_id} - Check PIN authentication status

These endpoints are publicly accessible without authentication.
Implements Requirements 13.1, 13.2, 14.1, 14.2, 14.3.
"""

from collections.abc import Mapping, Sequence
from typing import Annotated

from litestar import Controller, get, post
from litestar.datastructures import State
from litestar.di import Provide
from litestar.params import Parameter
from litestar.status_codes import HTTP_200_OK
from litestar.types import AnyCallable

from zondarr.config import Settings
from zondarr.services.plex_oauth import PlexOAuthError, PlexOAuthService

from .schemas import PlexOAuthCheckResponse, PlexOAuthPinResponse

# Default client identifier for Plex OAuth
DEFAULT_PLEX_CLIENT_ID = "zondarr-oauth-client"


async def provide_plex_oauth_service(state: State) -> PlexOAuthService:
    """Provide PlexOAuthService instance.

    Creates a PlexOAuthService with the client_id from application settings.
    The service is created fresh for each request to ensure proper resource
    management.

    Args:
        state: Application state containing settings.

    Returns:
        Configured PlexOAuthService instance.
    """
    # Get settings from state - state.settings is typed as Any by Litestar
    # We know it's Settings from our app configuration
    settings = state.get("settings")
    if isinstance(settings, Settings):
        # Use a default client_id since Settings doesn't have plex_client_id
        # In production, this could be extended to read from settings
        client_id_attr: object = getattr(settings, "plex_client_id", None)
        if client_id_attr is not None and isinstance(client_id_attr, str):
            return PlexOAuthService(client_id=client_id_attr)
    return PlexOAuthService(client_id=DEFAULT_PLEX_CLIENT_ID)


class PlexOAuthController(Controller):
    """Controller for Plex OAuth flow endpoints.

    Provides public endpoints for the Plex OAuth PIN-based authentication
    flow used during invitation redemption. These endpoints do not require
    authentication.

    Implements Requirements 13.1, 13.2, 14.1, 14.2, 14.3.
    """

    path: str = "/api/v1/join/plex/oauth"
    tags: Sequence[str] | None = ["Plex OAuth"]
    dependencies: Mapping[str, Provide | AnyCallable] | None = {
        "oauth_service": Provide(provide_plex_oauth_service),
    }

    @post(
        "/pin",
        status_code=HTTP_200_OK,
        summary="Create Plex OAuth PIN",
        description=(
            "Generate a PIN for Plex OAuth authentication. "
            "The user should be directed to the auth_url to complete authentication."
        ),
        exclude_from_auth=True,
    )
    async def create_pin(
        self,
        oauth_service: PlexOAuthService,
    ) -> PlexOAuthPinResponse:
        """Generate OAuth PIN and return auth URL.

        Creates a new PIN via the Plex.tv API that can be used for
        user authentication. The user should be directed to the auth_url
        to complete authentication.

        Implements Requirements 13.1, 13.2.

        Args:
            oauth_service: PlexOAuthService from DI.

        Returns:
            PlexOAuthPinResponse with pin_id, code, auth_url, and expires_at.

        Raises:
            PlexOAuthError: If PIN generation fails.
        """
        try:
            pin = await oauth_service.create_pin()
            return PlexOAuthPinResponse(
                pin_id=pin.pin_id,
                code=pin.code,
                auth_url=pin.auth_url,
                expires_at=pin.expires_at,
            )
        finally:
            await oauth_service.close()

    @get(
        "/pin/{pin_id:int}",
        status_code=HTTP_200_OK,
        summary="Check Plex OAuth PIN status",
        description=(
            "Check if a PIN has been authenticated. "
            "Returns the user's email if authentication is complete."
        ),
        exclude_from_auth=True,
    )
    async def check_pin(
        self,
        pin_id: Annotated[int, Parameter(description="PIN ID to check")],
        oauth_service: PlexOAuthService,
    ) -> PlexOAuthCheckResponse:
        """Check if PIN has been authenticated.

        Polls the Plex.tv API to check if the user has completed
        authentication for the given PIN. If authenticated, retrieves
        the user's email address.

        Implements Requirements 14.1, 14.2, 14.3.

        Args:
            pin_id: The PIN ID to check.
            oauth_service: PlexOAuthService from DI.

        Returns:
            PlexOAuthCheckResponse with authenticated status and email if successful.

        Raises:
            PlexOAuthError: If the PIN check fails (non-404 errors).
        """
        try:
            result = await oauth_service.check_pin(pin_id)
            return PlexOAuthCheckResponse(
                authenticated=result.authenticated,
                auth_token=result.auth_token,
                email=result.email,
                error=result.error,
            )
        except PlexOAuthError as exc:
            # Return error response instead of raising for client-friendly handling
            return PlexOAuthCheckResponse(
                authenticated=False,
                error=exc.message,
            )
        finally:
            await oauth_service.close()
