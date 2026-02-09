"""Admin authentication models.

Provides:
- AuthMethod: StrEnum for authentication methods (local, plex, jellyfin)
- AdminAccount: Admin user account for Zondarr dashboard access
- RefreshToken: JWT refresh tokens stored in DB for revocation support
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuthMethod(StrEnum):
    """Supported authentication methods."""

    LOCAL = "local"
    PLEX = "plex"
    JELLYFIN = "jellyfin"


class AdminAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Admin user account for Zondarr dashboard access.

    Separate from Identity/User which represent media server accounts.
    Supports local password auth and external auth via Plex/Jellyfin.

    Attributes:
        id: UUID primary key.
        username: Unique admin username.
        password_hash: Argon2id hash (nullable for external auth).
        email: Optional email address.
        auth_method: How this admin authenticates.
        external_id: External service identifier (Plex email or Jellyfin user ID).
        enabled: Whether this admin can log in.
        last_login_at: Timestamp of last successful login.
    """

    __tablename__: str = "admin_accounts"

    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), default=None)
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    auth_method: Mapped[AuthMethod] = mapped_column(default=AuthMethod.LOCAL)
    external_id: Mapped[str | None] = mapped_column(String(255), default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(default=None)

    # Relationships
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="admin_account",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__: tuple[Index, ...] = (
        Index("ix_admin_accounts_external_id", "external_id"),
    )


class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """JWT refresh token for session management.

    Stored in DB to support revocation. The token itself is hashed
    with SHA-256 for storage; only the hash is persisted.

    Attributes:
        id: UUID primary key.
        admin_account_id: FK to the owning admin account.
        token_hash: SHA-256 hash of the refresh token value.
        expires_at: When this token expires.
        revoked: Whether this token has been explicitly revoked.
        user_agent: Client user-agent string for audit.
        ip_address: Client IP address for audit.
    """

    __tablename__: str = "refresh_tokens"

    admin_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_accounts.id", ondelete="CASCADE"),
    )
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column()
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), default=None)
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)

    # Relationships
    admin_account: Mapped[AdminAccount] = relationship(
        back_populates="refresh_tokens",
        lazy="joined",
    )
