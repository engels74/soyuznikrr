"""admin_auth

Creates admin_accounts and refresh_tokens tables for admin authentication.

Revision ID: 18295ce7ef76
Revises: 003
Create Date: 2026-02-08 22:44:21.989542
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "18295ce7ef76"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create admin_accounts and refresh_tokens tables."""
    _ = op.create_table(
        "admin_accounts",
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column(
            "auth_method",
            sa.String(length=20),
            nullable=False,
            server_default="local",
        ),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("admin_accounts", schema=None) as batch_op:
        batch_op.create_index(
            "ix_admin_accounts_external_id", ["external_id"], unique=False
        )
        batch_op.create_index("ix_admin_accounts_username", ["username"], unique=True)

    _ = op.create_table(
        "refresh_tokens",
        sa.Column("admin_account_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["admin_account_id"], ["admin_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.create_index(
            "ix_refresh_tokens_token_hash", ["token_hash"], unique=False
        )


def downgrade() -> None:
    """Drop admin_accounts and refresh_tokens tables."""
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.drop_index("ix_refresh_tokens_token_hash")

    op.drop_table("refresh_tokens")

    with op.batch_alter_table("admin_accounts", schema=None) as batch_op:
        batch_op.drop_index("ix_admin_accounts_username")
        batch_op.drop_index("ix_admin_accounts_external_id")

    op.drop_table("admin_accounts")
