"""encrypt_existing_media_server_api_keys

Data-only migration: encrypts all existing plaintext API keys in the
media_servers table using Fernet encryption derived from SECRET_KEY.

Revision ID: f28e9381c2ea
Revises: 3a3f41a6c5ed
Create Date: 2026-03-08 23:23:22.058948
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from zondarr.services.api_key_encryption import decrypt_api_key, encrypt_api_key

# Revision identifiers, used by Alembic.
revision: str = "f28e9381c2ea"
down_revision: str | None = "3a3f41a6c5ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_secret_key() -> str:
    """Get SECRET_KEY from environment, required for encryption."""
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY environment variable is required "
            "to run the API key encryption migration"
        )
    return secret_key


def upgrade() -> None:
    """Encrypt all plaintext API keys in media_servers."""
    secret_key = _get_secret_key()
    conn = op.get_bind()

    rows = conn.execute(sa.text("SELECT id, api_key FROM media_servers")).fetchall()

    for row_id, api_key in rows:
        encrypted = encrypt_api_key(api_key, secret_key=secret_key)
        conn.execute(
            sa.text("UPDATE media_servers SET api_key = :key WHERE id = :id"),
            {"key": encrypted, "id": row_id},
        )


def downgrade() -> None:
    """Decrypt all API keys back to plaintext."""
    secret_key = _get_secret_key()
    conn = op.get_bind()

    rows = conn.execute(sa.text("SELECT id, api_key FROM media_servers")).fetchall()

    for row_id, api_key in rows:
        decrypted = decrypt_api_key(api_key, secret_key=secret_key)
        conn.execute(
            sa.text("UPDATE media_servers SET api_key = :key WHERE id = :id"),
            {"key": decrypted, "id": row_id},
        )
