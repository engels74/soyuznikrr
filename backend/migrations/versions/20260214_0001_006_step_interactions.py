"""Extract step interactions into separate table.

Creates step_interactions table and migrates existing interaction_type
and config data from wizard_steps into the new table. Then drops the
interaction_type and config columns from wizard_steps.

Revision ID: 006
Revises: 47df78392c60
Create Date: 2026-02-14
"""

import json
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "47df78392c60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create step_interactions table and migrate data from wizard_steps."""
    # 1. Create step_interactions table
    _ = op.create_table(
        "step_interactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_type", sa.String(length=20), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["step_id"],
            ["wizard_steps.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "step_id", "interaction_type", name="uq_step_interaction_type"
        ),
    )

    # 2. Migrate existing data from wizard_steps to step_interactions
    connection = op.get_bind()
    steps = connection.execute(
        sa.text("SELECT id, interaction_type, config, created_at FROM wizard_steps")
    ).fetchall()

    for step_id, interaction_type, config, created_at in steps:  # pyright: ignore[reportAny]
        # Only migrate if there's an interaction type
        if interaction_type:
            new_id = str(uuid4())
            _ = connection.execute(
                sa.text(
                    "INSERT INTO step_interactions (id, step_id, interaction_type, config, display_order, created_at)"
                    + " VALUES (:id, :step_id, :interaction_type, :config, 0, :created_at)"
                ),
                {
                    "id": new_id,
                    "step_id": step_id,
                    "interaction_type": interaction_type,
                    "config": config
                    if isinstance(config, str)
                    else json.dumps(config)
                    if isinstance(config, (dict, list))
                    else "{}",
                    "created_at": created_at,
                },
            )

    # 3. Drop interaction_type and config columns from wizard_steps (batch mode for SQLite)
    with op.batch_alter_table("wizard_steps", schema=None) as batch_op:
        batch_op.drop_column("interaction_type")
        batch_op.drop_column("config")


def downgrade() -> None:
    """Restore interaction_type and config columns to wizard_steps."""
    # 1. Add columns back to wizard_steps
    with op.batch_alter_table("wizard_steps", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("interaction_type", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "config", sa.JSON(), nullable=True, server_default=sa.text("'{}'")
            )
        )

    # 2. Migrate data back from step_interactions to wizard_steps
    connection = op.get_bind()
    interactions = connection.execute(
        sa.text(
            "SELECT step_id, interaction_type, config FROM step_interactions"
            + " ORDER BY display_order ASC"
        )
    ).fetchall()

    for step_id, interaction_type, config in interactions:  # pyright: ignore[reportAny]
        _ = connection.execute(
            sa.text(
                "UPDATE wizard_steps SET interaction_type = :interaction_type, config = :config"
                + " WHERE id = :step_id AND interaction_type IS NULL"
            ),
            {
                "step_id": step_id,
                "interaction_type": interaction_type,
                "config": config,
            },
        )

    # Set default for any steps that didn't get migrated back
    _ = connection.execute(
        sa.text(
            "UPDATE wizard_steps SET interaction_type = 'click', config = '{}'"
            + " WHERE interaction_type IS NULL"
        )
    )

    # Make interaction_type NOT NULL again
    with op.batch_alter_table("wizard_steps", schema=None) as batch_op:
        batch_op.alter_column("interaction_type", nullable=False)
        batch_op.alter_column("config", nullable=False)

    # 3. Drop step_interactions table
    op.drop_table("step_interactions")
