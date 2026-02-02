"""Plex OAuth service for PIN-based authentication.

Implements the Plex PIN-based OAuth flow:
1. Generate PIN via POST to plex.tv/api/v2/pins
2. User authenticates at plex.tv/link with PIN code
3. Poll PIN status to retrieve auth token
4. Use token to fetch user email

Uses httpx for async HTTP requests to Plex.tv API.
"""

from datetime import datetime

import httpx
import msgspec
import structlog

log: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]

# Plex.tv API endpoints
PLEX_TV_PINS_URL = "https://plex.tv/api/v2/pins"
PLEX_TV_USER_URL = "https://plex.tv/api/v2/user"
PLEX_TV_AUTH_URL = "https://app.plex.tv/auth#"


class PlexOAuthPin(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Response from PIN creation.

    Attributes:
        pin_id: The PIN identifier for status checking.
        code: The PIN code to display to the user.
        auth_url: URL where user authenticates (plex.tv/link).
        expires_at: When the PIN expires.
    """

    pin_id: int
    code: str
    auth_url: str
    expires_at: datetime


class PlexOAuthResult(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Response from PIN status check.

    Attributes:
        authenticated: Whether the PIN has been authenticated.
        email: User's Plex email (only if authenticated).
        auth_token: User's Plex auth token (only if authenticated).
        error: Error message (only if failed).
    """

    authenticated: bool
    email: str | None = None
    auth_token: str | None = None
    error: str | None = None


class PlexOAuthError(Exception):
    """Raised when a Plex OAuth operation fails.

    Attributes:
        message: Human-readable error description.
        operation: The OAuth operation that failed.
        cause: The underlying cause of the failure.
    """

    message: str
    operation: str
    cause: str | None

    def __init__(
        self,
        message: str,
        /,
        *,
        operation: str,
        cause: str | None = None,
    ) -> None:
        """Initialize a PlexOAuthError.

        Args:
            message: Human-readable error description.
            operation: The OAuth operation that failed.
            cause: The underlying cause of the failure.
        """
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.cause = cause


class PlexOAuthService:
    """Service for Plex OAuth PIN-based authentication.

    Implements the Plex PIN-based OAuth flow:
    1. Generate PIN via POST to plex.tv/api/v2/pins
    2. User authenticates at plex.tv/link with PIN code
    3. Poll PIN status to retrieve auth token
    4. Use token to fetch user email

    Attributes:
        client_id: The X-Plex-Client-Identifier for API requests.
    """

    _http_client: httpx.AsyncClient
    _client_id: str

    def __init__(self, *, client_id: str) -> None:
        """Initialize the PlexOAuthService.

        Args:
            client_id: The X-Plex-Client-Identifier for API requests (keyword-only).
        """
        self._client_id = client_id
        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        await self._http_client.aclose()
        log.info("plex_oauth_service_closed")

    async def create_pin(self) -> PlexOAuthPin:
        """Generate a Plex OAuth PIN and return auth URL.

        Creates a new PIN via the Plex.tv API that can be used for
        user authentication. The user should be directed to the auth_url
        to complete authentication.

        Returns:
            PlexOAuthPin with pin_id, code, auth_url, and expires_at.

        Raises:
            PlexOAuthError: If PIN generation fails.
        """
        headers = {
            "X-Plex-Client-Identifier": self._client_id,
            "X-Plex-Product": "Zondarr",
            "Accept": "application/json",
        }

        try:
            response = await self._http_client.post(
                PLEX_TV_PINS_URL,
                headers=headers,
                data={"strong": "true"},
            )
            _ = response.raise_for_status()

            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            pin_id: int = int(data["id"])  # pyright: ignore[reportArgumentType]
            code: str = str(data["code"])
            expires_at_str: str = str(data["expiresAt"])

            # Parse the expiration timestamp
            # Plex returns ISO 8601 format: "2024-01-15T12:00:00Z"
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))

            # Build the auth URL
            # Format: https://app.plex.tv/auth#?clientID=xxx&code=xxx&context[device][product]=Zondarr
            auth_url = (
                f"{PLEX_TV_AUTH_URL}?clientID={self._client_id}"
                f"&code={code}"
                f"&context%5Bdevice%5D%5Bproduct%5D=Zondarr"
            )

            log.info(
                "plex_oauth_pin_created",
                pin_id=pin_id,
                expires_at=expires_at.isoformat(),
            )

            return PlexOAuthPin(
                pin_id=pin_id,
                code=code,
                auth_url=auth_url,
                expires_at=expires_at,
            )

        except httpx.HTTPStatusError as exc:
            log.error(
                "plex_oauth_pin_creation_failed",
                status_code=exc.response.status_code,
                error=str(exc),
            )
            raise PlexOAuthError(
                f"Failed to create Plex OAuth PIN: HTTP {exc.response.status_code}",
                operation="create_pin",
                cause=str(exc),
            ) from exc
        except httpx.RequestError as exc:
            log.error(
                "plex_oauth_pin_creation_failed",
                error=str(exc),
            )
            raise PlexOAuthError(
                f"Failed to create Plex OAuth PIN: {exc}",
                operation="create_pin",
                cause=str(exc),
            ) from exc
        except (KeyError, ValueError) as exc:
            log.error(
                "plex_oauth_pin_creation_failed",
                error=str(exc),
            )
            raise PlexOAuthError(
                f"Failed to parse Plex OAuth PIN response: {exc}",
                operation="create_pin",
                cause=str(exc),
            ) from exc

    async def check_pin(self, pin_id: int, /) -> PlexOAuthResult:
        """Check if a PIN has been authenticated.

        Polls the Plex.tv API to check if the user has completed
        authentication for the given PIN. If authenticated, retrieves
        the user's email address.

        Args:
            pin_id: The PIN ID to check (positional-only).

        Returns:
            PlexOAuthResult with authenticated status and email if successful.

        Raises:
            PlexOAuthError: If the PIN check fails.
        """
        headers = {
            "X-Plex-Client-Identifier": self._client_id,
            "Accept": "application/json",
        }

        try:
            response = await self._http_client.get(
                f"{PLEX_TV_PINS_URL}/{pin_id}",
                headers=headers,
            )
            _ = response.raise_for_status()

            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            # Check if authToken is present (indicates successful authentication)
            auth_token_value = data.get("authToken")
            auth_token: str | None = str(auth_token_value) if auth_token_value else None

            if not auth_token:
                # Not yet authenticated
                log.debug(
                    "plex_oauth_pin_not_authenticated",
                    pin_id=pin_id,
                )
                return PlexOAuthResult(authenticated=False)

            # Authenticated - fetch user email
            email = await self.get_user_email(auth_token)

            log.info(
                "plex_oauth_pin_authenticated",
                pin_id=pin_id,
                email=email,
            )

            return PlexOAuthResult(
                authenticated=True,
                email=email,
                auth_token=auth_token,
            )

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                log.warning(
                    "plex_oauth_pin_not_found",
                    pin_id=pin_id,
                )
                return PlexOAuthResult(
                    authenticated=False,
                    error="PIN not found",
                )
            log.error(
                "plex_oauth_pin_check_failed",
                pin_id=pin_id,
                status_code=exc.response.status_code,
                error=str(exc),
            )
            raise PlexOAuthError(
                f"Failed to check Plex OAuth PIN: HTTP {exc.response.status_code}",
                operation="check_pin",
                cause=str(exc),
            ) from exc
        except httpx.RequestError as exc:
            log.error(
                "plex_oauth_pin_check_failed",
                pin_id=pin_id,
                error=str(exc),
            )
            raise PlexOAuthError(
                f"Failed to check Plex OAuth PIN: {exc}",
                operation="check_pin",
                cause=str(exc),
            ) from exc
        except PlexOAuthError:
            # Re-raise PlexOAuthError from get_user_email
            raise

    async def get_user_email(self, auth_token: str, /) -> str:
        """Retrieve user's Plex email from auth token.

        Fetches the user's account information from Plex.tv using
        the provided auth token and extracts the email address.

        Args:
            auth_token: The Plex auth token (positional-only).

        Returns:
            The user's email address.

        Raises:
            PlexOAuthError: If email retrieval fails.
        """
        headers = {
            "X-Plex-Client-Identifier": self._client_id,
            "X-Plex-Token": auth_token,
            "Accept": "application/json",
        }

        try:
            response = await self._http_client.get(
                PLEX_TV_USER_URL,
                headers=headers,
            )
            _ = response.raise_for_status()

            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
            email: str = str(data["email"])

            log.debug(
                "plex_oauth_user_email_retrieved",
                email=email,
            )

            return email

        except httpx.HTTPStatusError as exc:
            log.error(
                "plex_oauth_user_email_failed",
                status_code=exc.response.status_code,
                error=str(exc),
            )
            raise PlexOAuthError(
                f"Failed to retrieve user email: HTTP {exc.response.status_code}",
                operation="get_user_email",
                cause=str(exc),
            ) from exc
        except httpx.RequestError as exc:
            log.error(
                "plex_oauth_user_email_failed",
                error=str(exc),
            )
            raise PlexOAuthError(
                f"Failed to retrieve user email: {exc}",
                operation="get_user_email",
                cause=str(exc),
            ) from exc
        except KeyError as exc:
            log.error(
                "plex_oauth_user_email_failed",
                error=str(exc),
            )
            raise PlexOAuthError(
                "Failed to retrieve user email: email not found in response",
                operation="get_user_email",
                cause=str(exc),
            ) from exc
