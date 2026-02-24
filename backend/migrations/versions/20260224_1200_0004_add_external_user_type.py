"""add external_user_type to users

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-24 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration changes."""
    op.add_column(
        "users",
        sa.Column("external_user_type", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    """Reverse migration changes."""
    op.drop_column("users", "external_user_type")
