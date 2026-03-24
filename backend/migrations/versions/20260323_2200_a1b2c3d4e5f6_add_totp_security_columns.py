"""add totp security columns

Revision ID: a1b2c3d4e5f6
Revises: bf231ee80bbd
Create Date: 2026-03-23 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "bf231ee80bbd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add totp_challenge_nonce, totp_last_used_code, and totp_last_used_at columns."""
    with op.batch_alter_table("admin_accounts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("totp_challenge_nonce", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("totp_last_used_code", sa.String(length=6), nullable=True)
        )
        batch_op.add_column(
            sa.Column("totp_last_used_at", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    """Remove totp security columns."""
    with op.batch_alter_table("admin_accounts", schema=None) as batch_op:
        batch_op.drop_column("totp_last_used_at")
        batch_op.drop_column("totp_last_used_code")
        batch_op.drop_column("totp_challenge_nonce")
