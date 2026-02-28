"""Admin authentication models.

Provides:
- AdminAccount: Admin user account for Zondarr dashboard access
- RefreshToken: JWT refresh tokens stored in DB for revocation support
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AdminAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Admin user account for Zondarr dashboard access.

    Separate from Identity/User which represent media server accounts.
    Supports local password auth and external auth via registered providers.

    Attributes:
        id: UUID primary key.
        username: Unique admin username.
        password_hash: Argon2id hash (nullable for external auth).
        email: Optional email address.
        auth_method: How this admin authenticates.
        external_id: External service identifier for the auth provider.
        enabled: Whether this admin can log in.
        last_login_at: Timestamp of last successful login.
        totp_enabled: Whether TOTP two-factor authentication is active.
        totp_secret_encrypted: Fernet-encrypted TOTP secret (base32).
        totp_backup_codes: JSON array of argon2-hashed backup codes.
    """

    __tablename__: str = "admin_accounts"

    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), default=None)
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    auth_method: Mapped[str] = mapped_column(String(50), default="local")
    external_id: Mapped[str | None] = mapped_column(String(255), default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(default=None)

    # TOTP two-factor authentication
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    totp_backup_codes: Mapped[str | None] = mapped_column(Text, default=None)

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
