"""Database-backed OAuth session store with opaque handles.

Maps high-entropy opaque handles to provider PIN data, preventing
enumeration of sequential provider pin_ids and keeping raw auth_tokens
server-side.

Sessions have TTL-based expiry and auth tokens support one-time consumption
via redemption tokens. All data is persisted to the database so sessions
survive across Granian workers/subinterpreters.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import final

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.models.oauth_session import OAuthSessionModel

logger: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]

# Default TTL: 10 minutes (matches typical OAuth PIN expiry)
DEFAULT_TTL_SECONDS = 600


@final
class OAuthSessionData:
    """Read-only view of an OAuth session for callers.

    Attributes:
        provider: The provider name (e.g., "plex").
        pin_id: The provider's internal PIN ID.
        auth_token: Raw provider auth token, set when PIN is authenticated.
        email: User's email, set when PIN is authenticated.
        redemption_token: One-time token for redeeming the auth_token.
        redeemed: Whether the redemption token has been consumed.
    """

    __slots__ = (
        "auth_token",
        "email",
        "pin_id",
        "provider",
        "redeemed",
        "redemption_token",
    )

    def __init__(
        self,
        *,
        provider: str,
        pin_id: int,
        auth_token: str | None = None,
        email: str | None = None,
        redemption_token: str | None = None,
        redeemed: bool = False,
    ) -> None:
        self.provider = provider
        self.pin_id = pin_id
        self.auth_token = auth_token
        self.email = email
        self.redemption_token = redemption_token
        self.redeemed = redeemed


class OAuthSessionStore:
    """Database-backed store mapping opaque handles to OAuth sessions.

    All methods require an ``AsyncSession`` parameter so sessions are
    shared across Granian workers via the database.
    """

    async def create(
        self,
        session: AsyncSession,
        provider: str,
        pin_id: int,
        *,
        ttl: int = DEFAULT_TTL_SECONDS,
    ) -> str:
        """Create a new session and return its opaque handle.

        Args:
            session: SQLAlchemy async session.
            provider: The provider name.
            pin_id: The provider's internal PIN ID.
            ttl: Time-to-live in seconds.

        Returns:
            A high-entropy opaque handle string.
        """
        handle = secrets.token_urlsafe(32)
        model = OAuthSessionModel(
            handle=handle,
            provider=provider,
            pin_id=pin_id,
            ttl=ttl,
        )
        session.add(model)
        await session.flush()
        logger.debug(
            "oauth_session_created",
            provider=provider,
            handle_prefix=handle[:8],
        )
        return handle

    async def get(
        self,
        session: AsyncSession,
        handle: str,
    ) -> OAuthSessionData | None:
        """Look up a session by handle.

        Returns None if the handle is unknown or the session has expired.

        Args:
            session: SQLAlchemy async session.
            handle: The opaque session handle.

        Returns:
            The session data, or None if not found/expired.
        """
        stmt = select(OAuthSessionModel).where(OAuthSessionModel.handle == handle)
        model = await session.scalar(stmt)
        if model is None:
            return None
        if self._is_expired(model):
            await session.delete(model)
            await session.flush()
            return None
        return self._to_data(model)

    async def set_authenticated(
        self,
        session: AsyncSession,
        handle: str,
        *,
        auth_token: str,
        email: str | None,
    ) -> str | None:
        """Mark a session as authenticated and generate a redemption token.

        Args:
            session: SQLAlchemy async session.
            handle: The opaque session handle.
            auth_token: The raw provider auth token.
            email: The user's email address.

        Returns:
            A one-time redemption token, or None if session not found.
        """
        stmt = select(OAuthSessionModel).where(OAuthSessionModel.handle == handle)
        model = await session.scalar(stmt)
        if model is None or self._is_expired(model):
            return None
        model.auth_token = auth_token
        model.email = email
        model.redemption_token = secrets.token_urlsafe(32)
        await session.flush()
        logger.debug(
            "oauth_session_authenticated",
            handle_prefix=handle[:8],
            has_email=email is not None,
        )
        return model.redemption_token

    async def redeem(
        self,
        session: AsyncSession,
        redemption_token: str,
    ) -> tuple[str, str] | None:
        """Consume a redemption token and return (provider, auth_token).

        One-time use: after redemption the token is invalidated.
        Uses a conditional UPDATE to atomically mark the token as redeemed,
        preventing double-redemption under concurrent requests.

        Args:
            session: SQLAlchemy async session.
            redemption_token: The one-time redemption token.

        Returns:
            A (provider, auth_token) tuple, or None if invalid/already used.
        """
        # Atomically claim the token: only one concurrent request can
        # match redeemed=False and flip it to True.
        stmt = (
            update(OAuthSessionModel)
            .where(
                OAuthSessionModel.redemption_token == redemption_token,
                OAuthSessionModel.redeemed.is_(False),
                OAuthSessionModel.auth_token.isnot(None),
            )
            .values(redeemed=True)
            .returning(
                OAuthSessionModel.handle,
                OAuthSessionModel.provider,
                OAuthSessionModel.auth_token,
                OAuthSessionModel.created_at,
                OAuthSessionModel.ttl,
            )
        )
        row = (await session.execute(stmt)).first()
        if row is None:
            return None
        handle: str = row.handle  # pyright: ignore[reportAny]
        provider: str = row.provider  # pyright: ignore[reportAny]
        auth_token: str = row.auth_token  # pyright: ignore[reportAny]
        # Check TTL expiry (can't easily express in SQL portably)
        if self._is_expired_raw(row.created_at, row.ttl):  # pyright: ignore[reportAny]
            return None
        # Clear auth_token from storage after reading it
        clear_stmt = (
            update(OAuthSessionModel)
            .where(OAuthSessionModel.redemption_token == redemption_token)
            .values(auth_token=None)
        )
        _ = await session.execute(clear_stmt)
        await session.flush()
        logger.debug(
            "oauth_session_redeemed",
            handle_prefix=handle[:8],
            provider=provider,
        )
        return (provider, auth_token)

    async def remove(
        self,
        session: AsyncSession,
        handle: str,
    ) -> None:
        """Remove a session by handle.

        Args:
            session: SQLAlchemy async session.
            handle: The opaque session handle.
        """
        stmt = delete(OAuthSessionModel).where(OAuthSessionModel.handle == handle)
        _ = await session.execute(stmt)
        await session.flush()

    async def cleanup_expired(self, session: AsyncSession) -> None:
        """Remove all expired sessions from the database.

        Args:
            session: SQLAlchemy async session.
        """
        now = datetime.now(UTC)
        # We can't easily express created_at + ttl < now in a single portable
        # SQL expression, so fetch and filter in Python.
        stmt = select(OAuthSessionModel)
        result = await session.scalars(stmt)
        expired = [m for m in result if self._is_expired(m, now=now)]
        for m in expired:
            await session.delete(m)
        if expired:
            await session.flush()

    @staticmethod
    def _is_expired(model: OAuthSessionModel, *, now: datetime | None = None) -> bool:
        """Check if a session model has exceeded its TTL."""
        return OAuthSessionStore._is_expired_raw(model.created_at, model.ttl, now=now)

    @staticmethod
    def _is_expired_raw(
        created_at: datetime, ttl: int, *, now: datetime | None = None
    ) -> bool:
        """Check if a session has exceeded its TTL using raw values."""
        if now is None:
            now = datetime.now(UTC)
        expiry = created_at + timedelta(seconds=ttl)
        # Ensure both are comparable (both should be UTC)
        if expiry.tzinfo is None:
            return expiry < now.replace(tzinfo=None)
        return expiry < now

    @staticmethod
    def _to_data(model: OAuthSessionModel) -> OAuthSessionData:
        """Convert a model instance to an OAuthSessionData view."""
        return OAuthSessionData(
            provider=model.provider,
            pin_id=model.pin_id,
            auth_token=model.auth_token,
            email=model.email,
            redemption_token=model.redemption_token,
            redeemed=model.redeemed,
        )
