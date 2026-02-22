"""add unique constraint external_user_server

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-22 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add unique constraint on (external_user_id, media_server_id) to users table.

    Phase 1: Clean up duplicate rows (keep the one with an invitation_id, or the newest).
    Phase 2: Add the unique constraint.
    """
    # Phase 1: Data cleanup — remove duplicates before adding constraint
    conn = op.get_bind()

    # Find duplicate groups: same (external_user_id, media_server_id) with multiple rows
    duplicates = conn.execute(
        sa.text(
            "SELECT external_user_id, media_server_id, COUNT(*) as cnt "
            "FROM users "
            "GROUP BY external_user_id, media_server_id "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()

    for row in duplicates:
        ext_id = row[0]
        server_id = row[1]

        # Get all rows for this duplicate group, prefer ones with invitation_id
        dupe_rows = conn.execute(
            sa.text(
                "SELECT id, identity_id, invitation_id "
                "FROM users "
                "WHERE external_user_id = :ext_id AND media_server_id = :server_id "
                "ORDER BY "
                "  CASE WHEN invitation_id IS NOT NULL THEN 0 ELSE 1 END, "
                "  created_at DESC"
            ),
            {"ext_id": ext_id, "server_id": server_id},
        ).fetchall()

        # Keep the first row (has invitation_id or is newest), delete the rest
        for dupe_row in dupe_rows[1:]:
            delete_id = dupe_row[0]
            identity_id = dupe_row[1]

            # Delete the duplicate user
            conn.execute(
                sa.text("DELETE FROM users WHERE id = :id"),
                {"id": delete_id},
            )

            # Clean up orphaned identity (if no other users reference it)
            remaining = conn.execute(
                sa.text("SELECT COUNT(*) FROM users WHERE identity_id = :identity_id"),
                {"identity_id": identity_id},
            ).scalar()

            if remaining == 0:
                conn.execute(
                    sa.text("DELETE FROM identities WHERE id = :id"),
                    {"id": identity_id},
                )

    # Phase 2: Add the unique constraint
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_users_external_user_server",
            ["external_user_id", "media_server_id"],
        )


def downgrade() -> None:
    """Remove the unique constraint."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("uq_users_external_user_server", type_="unique")
