"""add sync_runs table

Revision ID: b7f8a1d2e3c4
Revises: 5a3e7f1b9c2d
Create Date: 2026-02-28 18:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "b7f8a1d2e3c4"
down_revision: str | None = "5a3e7f1b9c2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration changes."""
    op.create_table(
        "sync_runs",
        sa.Column("media_server_id", sa.Uuid(), nullable=False),
        sa.Column("sync_type", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "sync_type IN ('libraries', 'users')", name="ck_sync_runs_sync_type"
        ),
        sa.CheckConstraint(
            "trigger IN ('automatic', 'manual', 'onboarding')",
            name="ck_sync_runs_trigger",
        ),
        sa.CheckConstraint(
            "status IN ('success', 'failed')", name="ck_sync_runs_status"
        ),
        sa.ForeignKeyConstraint(
            ["media_server_id"], ["media_servers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("sync_runs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_sync_runs_media_server_id"),
            ["media_server_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_sync_runs_server_type_started",
            ["media_server_id", "sync_type", "started_at"],
            unique=False,
        )


def downgrade() -> None:
    """Revert migration changes."""
    with op.batch_alter_table("sync_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_sync_runs_server_type_started")
        batch_op.drop_index(batch_op.f("ix_sync_runs_media_server_id"))

    op.drop_table("sync_runs")
