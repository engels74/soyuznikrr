"""In-memory OAuth session store with opaque handles.

Maps high-entropy opaque handles to provider PIN data, preventing
enumeration of sequential provider pin_ids and keeping raw auth_tokens
server-side.

Sessions have TTL-based expiry and auth tokens support one-time consumption
via redemption tokens.
"""

import secrets
import time
from dataclasses import dataclass, field

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]

# Default TTL: 10 minutes (matches typical OAuth PIN expiry)
DEFAULT_TTL_SECONDS = 600


@dataclass
class OAuthSession:
    """A tracked OAuth PIN session.

    Attributes:
        provider: The provider name (e.g., "plex").
        pin_id: The provider's internal PIN ID.
        created_at: Unix timestamp when the session was created.
        ttl: Time-to-live in seconds.
        auth_token: Raw provider auth token, set when PIN is authenticated.
        email: User's email, set when PIN is authenticated.
        redemption_token: One-time token for redeeming the auth_token.
        redeemed: Whether the redemption token has been consumed.
    """

    provider: str
    pin_id: int
    created_at: float = field(default_factory=time.monotonic)
    ttl: int = DEFAULT_TTL_SECONDS
    auth_token: str | None = None
    email: str | None = None
    redemption_token: str | None = None
    redeemed: bool = False

    @property
    def is_expired(self) -> bool:
        """Check if the session has exceeded its TTL."""
        return (time.monotonic() - self.created_at) > self.ttl


class OAuthSessionStore:
    """In-memory store mapping opaque handles to OAuth sessions.

    Thread-safe for single-process async use. Handles are generated
    using ``secrets.token_urlsafe(32)`` for high entropy.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, OAuthSession] = {}

    def create(
        self,
        provider: str,
        pin_id: int,
        *,
        ttl: int = DEFAULT_TTL_SECONDS,
    ) -> str:
        """Create a new session and return its opaque handle.

        Args:
            provider: The provider name.
            pin_id: The provider's internal PIN ID.
            ttl: Time-to-live in seconds.

        Returns:
            A high-entropy opaque handle string.
        """
        self._cleanup_expired()
        handle = secrets.token_urlsafe(32)
        self._sessions[handle] = OAuthSession(
            provider=provider,
            pin_id=pin_id,
            ttl=ttl,
        )
        logger.debug(
            "oauth_session_created",
            provider=provider,
            handle_prefix=handle[:8],
        )
        return handle

    def get(self, handle: str) -> OAuthSession | None:
        """Look up a session by handle.

        Returns None if the handle is unknown or the session has expired.

        Args:
            handle: The opaque session handle.

        Returns:
            The session, or None if not found/expired.
        """
        session = self._sessions.get(handle)
        if session is None:
            return None
        if session.is_expired:
            del self._sessions[handle]
            return None
        return session

    def set_authenticated(
        self,
        handle: str,
        *,
        auth_token: str,
        email: str | None,
    ) -> str | None:
        """Mark a session as authenticated and generate a redemption token.

        Args:
            handle: The opaque session handle.
            auth_token: The raw provider auth token.
            email: The user's email address.

        Returns:
            A one-time redemption token, or None if session not found.
        """
        session = self.get(handle)
        if session is None:
            return None
        session.auth_token = auth_token
        session.email = email
        session.redemption_token = secrets.token_urlsafe(32)
        logger.debug(
            "oauth_session_authenticated",
            handle_prefix=handle[:8],
            has_email=email is not None,
        )
        return session.redemption_token

    def redeem(self, redemption_token: str) -> tuple[str, str] | None:
        """Consume a redemption token and return (provider, auth_token).

        One-time use: after redemption the token is invalidated.

        Args:
            redemption_token: The one-time redemption token.

        Returns:
            A (provider, auth_token) tuple, or None if invalid/already used.
        """
        for handle, session in self._sessions.items():
            if (
                session.redemption_token == redemption_token
                and not session.redeemed
                and not session.is_expired
                and session.auth_token is not None
            ):
                session.redeemed = True
                auth_token = session.auth_token
                provider = session.provider
                # Clear the auth token from memory after redemption
                session.auth_token = None
                logger.debug(
                    "oauth_session_redeemed",
                    handle_prefix=handle[:8],
                    provider=provider,
                )
                return (provider, auth_token)
        return None

    def remove(self, handle: str) -> None:
        """Remove a session by handle.

        Args:
            handle: The opaque session handle.
        """
        _ = self._sessions.pop(handle, None)

    def _cleanup_expired(self) -> None:
        """Remove all expired sessions."""
        expired = [h for h, s in self._sessions.items() if s.is_expired]
        for h in expired:
            del self._sessions[h]


# Module-level singleton instance
oauth_session_store = OAuthSessionStore()
