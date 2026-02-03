"""Wizard system tables migration.

Creates wizard tables for configurable onboarding flows:
- wizards: Wizard flow definitions
- wizard_steps: Individual steps within wizards

Also adds wizard foreign keys to invitations table:
- pre_wizard_id: Wizard to run before account creation
- post_wizard_id: Wizard to run after account creation

Revision ID: 002
Revises: 001
Create Date: 2026-02-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create wizard tables and add wizard FKs to invitations."""
    # Create wizards table
    _ = op.create_table(
        "wizards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create wizard_steps table
    _ = op.create_table(
        "wizard_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wizard_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("interaction_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["wizard_id"],
            ["wizards.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wizard_id", "step_order", name="uq_wizard_step_order"),
    )

    # Add wizard foreign keys to invitations table using batch mode for SQLite
    with op.batch_alter_table("invitations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pre_wizard_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("post_wizard_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_invitations_pre_wizard_id",
            "wizards",
            ["pre_wizard_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_invitations_post_wizard_id",
            "wizards",
            ["post_wizard_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Drop wizard tables and remove wizard FKs from invitations."""
    # Drop wizard columns from invitations using batch mode for SQLite
    with op.batch_alter_table("invitations", schema=None) as batch_op:
        batch_op.drop_constraint("fk_invitations_post_wizard_id", type_="foreignkey")
        batch_op.drop_constraint("fk_invitations_pre_wizard_id", type_="foreignkey")
        batch_op.drop_column("post_wizard_id")
        batch_op.drop_column("pre_wizard_id")

    # Drop wizard tables
    op.drop_table("wizard_steps")
    op.drop_table("wizards")
