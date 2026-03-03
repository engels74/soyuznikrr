"""add wizard step translations

Revision ID: a1b2c3d4e5f6
Revises: 879656e4f2f5
Create Date: 2026-03-03 19:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "879656e4f2f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration changes."""
    # Add primary_language column to wizard_steps
    with op.batch_alter_table("wizard_steps", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "primary_language",
                sa.String(length=10),
                server_default="en",
                nullable=False,
            )
        )

    # Create wizard_step_translations table
    op.create_table(
        "wizard_step_translations",
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("language_code", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["step_id"], ["wizard_steps.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "step_id", "language_code", name="uq_step_translation_language"
        ),
    )

    # Data migration: create English translation rows for existing steps
    conn = op.get_bind()
    steps = conn.execute(
        sa.text("SELECT id, title, content_markdown FROM wizard_steps")
    ).fetchall()
    for step in steps:
        conn.execute(
            sa.text(
                "INSERT INTO wizard_step_translations "
                "(id, step_id, language_code, title, content_markdown, created_at) "
                "VALUES (lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || "
                "'-4' || substr(hex(randomblob(2)),2) || '-' || "
                "substr('89ab', abs(random()) % 4 + 1, 1) || "
                "substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6))), "
                ":step_id, 'en', :title, :content_markdown, CURRENT_TIMESTAMP)"
            ),
            {
                "step_id": step[0],
                "title": step[1],
                "content_markdown": step[2],
            },
        )


def downgrade() -> None:
    """Revert migration changes."""
    op.drop_table("wizard_step_translations")
    with op.batch_alter_table("wizard_steps", schema=None) as batch_op:
        batch_op.drop_column("primary_language")
