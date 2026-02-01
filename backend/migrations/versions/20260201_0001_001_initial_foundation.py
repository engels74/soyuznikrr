"""Initial foundation tables migration.

Creates all foundation tables for Zondarr:
- media_servers: Media server instances (Plex, Jellyfin)
- libraries: Content libraries within media servers
- invitations: Secure invitation codes for access
- identities: User accounts within Zondarr
- users: Media server accounts linked to identities
- invitation_servers: Association table for invitation-to-server relationships
- invitation_libraries: Association table for invitation-to-library relationships

Revision ID: 001
Revises:
Create Date: 2026-02-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all foundation tables."""
    # Create media_servers table
    _ = op.create_table(
        "media_servers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("server_type", sa.String(length=50), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("api_key", sa.String(length=512), nullable=False),
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

    # Create libraries table
    _ = op.create_table(
        "libraries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_server_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("library_type", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["media_server_id"],
            ["media_servers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create identities table
    _ = op.create_table(
        "identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
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

    # Create invitations table
    _ = op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column(
            "use_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invitations_code", "invitations", ["code"], unique=True)

    # Create users table
    _ = op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("media_server_id", sa.Uuid(), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["media_server_id"],
            ["media_servers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create invitation_servers association table
    _ = op.create_table(
        "invitation_servers",
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("media_server_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["invitation_id"],
            ["invitations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["media_server_id"],
            ["media_servers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("invitation_id", "media_server_id"),
    )

    # Create invitation_libraries association table
    _ = op.create_table(
        "invitation_libraries",
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("library_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["invitation_id"],
            ["invitations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["library_id"],
            ["libraries.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("invitation_id", "library_id"),
    )


def downgrade() -> None:
    """Drop all foundation tables in reverse order."""
    # Drop association tables first (they have foreign keys)
    op.drop_table("invitation_libraries")
    op.drop_table("invitation_servers")

    # Drop tables with foreign keys
    op.drop_table("users")
    op.drop_index("ix_invitations_code", table_name="invitations")
    op.drop_table("invitations")
    op.drop_table("libraries")

    # Drop tables without foreign keys
    op.drop_table("identities")
    op.drop_table("media_servers")
