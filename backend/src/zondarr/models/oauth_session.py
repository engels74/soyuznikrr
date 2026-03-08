"""OAuth session model for database-backed PIN session storage.

Provides:
- OAuthSessionModel: Persists OAuth PIN sessions across workers/processes
"""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OAuthSessionModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database-backed OAuth PIN session.

    Replaces the in-memory singleton to survive across Granian workers.
    Sessions have TTL-based expiry checked at query time via created_at + ttl.

    Attributes:
        id: UUID primary key.
        handle: High-entropy opaque handle (secrets.token_urlsafe).
        provider: Media server provider name (e.g. "plex").
        pin_id: Provider's internal PIN ID.
        ttl: Time-to-live in seconds from created_at.
        auth_token: Raw provider auth token, set on successful PIN auth.
        email: User's email, set on successful PIN auth.
        redemption_token: One-time token for redeeming the auth_token.
        redeemed: Whether the redemption token has been consumed.
        created_at: Timestamp when the session was created (from TimestampMixin).
    """

    __tablename__: str = "oauth_sessions"

    handle: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(50))
    pin_id: Mapped[int] = mapped_column(Integer)
    ttl: Mapped[int] = mapped_column(Integer)
    auth_token: Mapped[str | None] = mapped_column(String(512), default=None)
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    redemption_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, default=None, index=True
    )
    redeemed: Mapped[bool] = mapped_column(Boolean, default=False)
