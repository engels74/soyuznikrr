"""Tests for sync-time identity email backfill."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.media.types import ExternalUser
from zondarr.models.identity import Identity, User
from zondarr.models.media_server import MediaServer
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.sync import SyncService


@pytest.mark.asyncio
async def test_sync_backfills_missing_identity_email_for_matched_user(
    session: AsyncSession,
) -> None:
    """Non-dry-run sync stores provider email when the local identity lacks one."""
    server = MediaServer(
        name="Plex",
        server_type="plex",
        url="http://plex.local",
        api_key="token",
        enabled=True,
    )
    identity = Identity(display_name="Plex User", email=None, enabled=True)
    session.add_all([server, identity])
    await session.flush()

    user = User(
        identity_id=identity.id,
        media_server_id=server.id,
        external_user_id="plex-123",
        username="plexuser",
        enabled=True,
    )
    session.add(user)
    await session.flush()

    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.list_users = AsyncMock(
        return_value=[
            ExternalUser(
                external_user_id="plex-123",
                username="plexuser",
                email="plexuser@example.com",
            )
        ]
    )
    mock_registry = MagicMock()
    mock_registry.create_client_for_server = MagicMock(return_value=client)

    service = SyncService(
        MediaServerRepository(session),
        UserRepository(session),
        IdentityRepository(session),
    )

    with patch("zondarr.services.sync.registry", mock_registry):
        result = await service.sync_server(server.id, dry_run=False)

    assert result.matched_users == 1
    await session.refresh(identity)
    assert identity.email == "plexuser@example.com"


@pytest.mark.asyncio
async def test_sync_preserves_existing_identity_email_for_matched_user(
    session: AsyncSession,
) -> None:
    """Provider email does not overwrite an existing local identity email."""
    server = MediaServer(
        name="Plex",
        server_type="plex",
        url="http://plex.local",
        api_key="token",
        enabled=True,
    )
    identity = Identity(
        display_name="Plex User",
        email="local@example.com",
        enabled=True,
    )
    session.add_all([server, identity])
    await session.flush()

    user = User(
        identity_id=identity.id,
        media_server_id=server.id,
        external_user_id="plex-123",
        username="plexuser",
        enabled=True,
    )
    session.add(user)
    await session.flush()

    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.list_users = AsyncMock(
        return_value=[
            ExternalUser(
                external_user_id="plex-123",
                username="plexuser",
                email="provider@example.com",
            )
        ]
    )
    mock_registry = MagicMock()
    mock_registry.create_client_for_server = MagicMock(return_value=client)

    service = SyncService(
        MediaServerRepository(session),
        UserRepository(session),
        IdentityRepository(session),
    )

    with patch("zondarr.services.sync.registry", mock_registry):
        _ = await service.sync_server(server.id, dry_run=False)

    await session.refresh(identity)
    assert identity.email == "local@example.com"
