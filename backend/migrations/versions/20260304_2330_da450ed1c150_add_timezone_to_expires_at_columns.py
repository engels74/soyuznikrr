"""add timezone to expires_at columns

Revision ID: da450ed1c150
Revises: a1b2c3d4e5f6
Create Date: 2026-03-04 23:30:29.857537
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "da450ed1c150"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration changes."""
    # Change expires_at columns to DateTime(timezone=True) for PostgreSQL.
    # SQLite ignores the timezone flag, so this is a no-op there.
    with op.batch_alter_table("invitations", schema=None) as batch_op:
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
        )

    with op.batch_alter_table("identities", schema=None) as batch_op:
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
        )


def downgrade() -> None:
    """Revert migration changes."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    with op.batch_alter_table("identities", schema=None) as batch_op:
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    with op.batch_alter_table("invitations", schema=None) as batch_op:
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
