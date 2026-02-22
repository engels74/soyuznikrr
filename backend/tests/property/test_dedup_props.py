"""Property-based tests for user deduplication.

Tests that:
- Redemption cleans up stale sync-imported users before creating new records
- Cleanup cascades to orphaned Identity (Property 21 consistency)
- Cleanup preserves Identity when other Users remain
- Unique constraint prevents duplicate (external_user_id, media_server_id) rows
- Same external_user_id on different servers is allowed
- Sync skips already-imported users gracefully
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.conftest import TestDB
from zondarr.media.registry import ClientRegistry
from zondarr.media.types import ExternalUser
from zondarr.models.identity import Identity, User
from zondarr.models.media_server import MediaServer
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.user import UserService

# =============================================================================
# Custom Strategies
# =============================================================================

external_id_strategy = st.uuids().map(str)

username_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=3,
    max_size=20,
).filter(lambda x: x.strip() and x[0].isalpha())


# =============================================================================
# Dedup: Redemption cleans up stale sync-imported users
# =============================================================================


class TestRedemptionCleansUpStaleUsers:
    """Redemption cleanup removes stale local users before creating new ones."""

    @given(
        ext_id=external_id_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_cleanup_removes_existing_user(
        self,
        db: TestDB,
        ext_id: str,
        username: str,
    ) -> None:
        """cleanup_stale_local_users deletes a User with matching compound key."""
        await db.clean()
        async with db.session_factory() as session:
            # Create server
            server = MediaServer()
            server.name = "Test Server"
            server.server_type = "plex"
            server.url = "http://localhost:32400"
            server.api_key = "test-key"
            server.enabled = True
            session.add(server)
            await session.flush()

            # Create identity + user (simulating sync import)
            identity = Identity()
            identity.display_name = username
            identity.enabled = True
            session.add(identity)
            await session.flush()

            user = User()
            user.identity_id = identity.id
            user.media_server_id = server.id
            user.external_user_id = ext_id
            user.username = username
            user.enabled = True
            session.add(user)
            await session.commit()

            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            external_user = ExternalUser(
                external_user_id=ext_id,
                username=username,
                email=None,
            )

            cleaned = await user_service.cleanup_stale_local_users(
                [(server, external_user)]
            )
            await session.commit()

            assert cleaned == 1

            # Verify user is gone
            remaining = await user_repo.get_by_external_and_server(ext_id, server.id)
            assert remaining is None

    @given(
        ext_id=external_id_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_cleanup_noop_when_no_existing_user(
        self,
        db: TestDB,
        ext_id: str,
        username: str,
    ) -> None:
        """cleanup_stale_local_users returns 0 when no matching user exists."""
        await db.clean()
        async with db.session_factory() as session:
            server = MediaServer()
            server.name = "Test Server"
            server.server_type = "plex"
            server.url = "http://localhost:32400"
            server.api_key = "test-key"
            server.enabled = True
            session.add(server)
            await session.commit()

            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            external_user = ExternalUser(
                external_user_id=ext_id,
                username=username,
                email=None,
            )

            cleaned = await user_service.cleanup_stale_local_users(
                [(server, external_user)]
            )

            assert cleaned == 0


# =============================================================================
# Dedup: Cleanup cascades to orphaned Identity (Property 21)
# =============================================================================


class TestCleanupCascadesToOrphanedIdentity:
    """When cleanup removes the last User, the Identity is also deleted."""

    @given(
        ext_id=external_id_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_cleanup_deletes_orphaned_identity(
        self,
        db: TestDB,
        ext_id: str,
        username: str,
    ) -> None:
        """Identity is deleted when its last User is cleaned up."""
        await db.clean()
        async with db.session_factory() as session:
            server = MediaServer()
            server.name = "Test Server"
            server.server_type = "plex"
            server.url = "http://localhost:32400"
            server.api_key = "test-key"
            server.enabled = True
            session.add(server)
            await session.flush()

            identity = Identity()
            identity.display_name = username
            identity.enabled = True
            session.add(identity)
            await session.flush()
            identity_id = identity.id

            user = User()
            user.identity_id = identity.id
            user.media_server_id = server.id
            user.external_user_id = ext_id
            user.username = username
            user.enabled = True
            session.add(user)
            await session.commit()

            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            external_user = ExternalUser(
                external_user_id=ext_id,
                username=username,
                email=None,
            )

            _ = await user_service.cleanup_stale_local_users([(server, external_user)])
            await session.commit()

            # Identity should be deleted
            remaining_identity = await identity_repo.get_by_id(identity_id)
            assert remaining_identity is None


# =============================================================================
# Dedup: Cleanup preserves Identity when other Users remain
# =============================================================================


class TestCleanupPreservesIdentityWithOtherUsers:
    """When cleanup removes a User but others remain, the Identity is kept."""

    @given(
        ext_id1=external_id_strategy,
        ext_id2=external_id_strategy,
        username1=username_strategy,
        username2=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_cleanup_preserves_identity_with_remaining_users(
        self,
        db: TestDB,
        ext_id1: str,
        ext_id2: str,
        username1: str,
        username2: str,
    ) -> None:
        """Identity is preserved when other Users still reference it."""
        if ext_id1 == ext_id2:
            return  # Skip degenerate case

        await db.clean()
        async with db.session_factory() as session:
            # Create two servers
            server1 = MediaServer()
            server1.name = "Server 1"
            server1.server_type = "plex"
            server1.url = "http://server1:32400"
            server1.api_key = "key1"
            server1.enabled = True
            session.add(server1)

            server2 = MediaServer()
            server2.name = "Server 2"
            server2.server_type = "jellyfin"
            server2.url = "http://server2:8096"
            server2.api_key = "key2"
            server2.enabled = True
            session.add(server2)
            await session.flush()

            # One identity with two users on different servers
            identity = Identity()
            identity.display_name = username1
            identity.enabled = True
            session.add(identity)
            await session.flush()
            identity_id = identity.id

            user1 = User()
            user1.identity_id = identity.id
            user1.media_server_id = server1.id
            user1.external_user_id = ext_id1
            user1.username = username1
            user1.enabled = True
            session.add(user1)

            user2 = User()
            user2.identity_id = identity.id
            user2.media_server_id = server2.id
            user2.external_user_id = ext_id2
            user2.username = username2
            user2.enabled = True
            session.add(user2)
            await session.commit()

            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            # Only clean up user1
            external_user = ExternalUser(
                external_user_id=ext_id1,
                username=username1,
                email=None,
            )

            _ = await user_service.cleanup_stale_local_users([(server1, external_user)])
            await session.commit()

            # Identity should still exist (user2 remains)
            remaining_identity = await identity_repo.get_by_id(identity_id)
            assert remaining_identity is not None


# =============================================================================
# Dedup: Unique constraint prevents duplicates
# =============================================================================


class TestUniqueConstraintPreventsduplicates:
    """The DB unique constraint prevents duplicate (external_user_id, media_server_id)."""

    @given(
        ext_id=external_id_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_duplicate_insert_raises(
        self,
        db: TestDB,
        ext_id: str,
        username: str,
    ) -> None:
        """Inserting two Users with same (external_user_id, media_server_id) fails."""
        await db.clean()
        async with db.session_factory() as session:
            server = MediaServer()
            server.name = "Test Server"
            server.server_type = "plex"
            server.url = "http://localhost:32400"
            server.api_key = "test-key"
            server.enabled = True
            session.add(server)
            await session.flush()

            identity1 = Identity()
            identity1.display_name = "Identity 1"
            identity1.enabled = True
            session.add(identity1)

            identity2 = Identity()
            identity2.display_name = "Identity 2"
            identity2.enabled = True
            session.add(identity2)
            await session.flush()

            user1 = User()
            user1.identity_id = identity1.id
            user1.media_server_id = server.id
            user1.external_user_id = ext_id
            user1.username = username
            user1.enabled = True
            session.add(user1)
            await session.flush()

            user2 = User()
            user2.identity_id = identity2.id
            user2.media_server_id = server.id
            user2.external_user_id = ext_id  # Same external_user_id + server
            user2.username = username
            user2.enabled = True
            session.add(user2)

            with pytest.raises(Exception):  # noqa: B017
                await session.flush()


# =============================================================================
# Dedup: Same external_user_id on different servers is allowed
# =============================================================================


class TestSameExternalIdDifferentServers:
    """Same external_user_id on different servers does not conflict."""

    @given(
        ext_id=external_id_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_same_external_id_different_servers_allowed(
        self,
        db: TestDB,
        ext_id: str,
        username: str,
    ) -> None:
        """Two Users with same external_user_id but different servers is fine."""
        await db.clean()
        async with db.session_factory() as session:
            server1 = MediaServer()
            server1.name = "Server 1"
            server1.server_type = "plex"
            server1.url = "http://server1:32400"
            server1.api_key = "key1"
            server1.enabled = True
            session.add(server1)

            server2 = MediaServer()
            server2.name = "Server 2"
            server2.server_type = "jellyfin"
            server2.url = "http://server2:8096"
            server2.api_key = "key2"
            server2.enabled = True
            session.add(server2)
            await session.flush()

            identity = Identity()
            identity.display_name = username
            identity.enabled = True
            session.add(identity)
            await session.flush()

            user1 = User()
            user1.identity_id = identity.id
            user1.media_server_id = server1.id
            user1.external_user_id = ext_id
            user1.username = username
            user1.enabled = True
            session.add(user1)

            user2 = User()
            user2.identity_id = identity.id
            user2.media_server_id = server2.id
            user2.external_user_id = ext_id  # Same ext ID, different server
            user2.username = username
            user2.enabled = True
            session.add(user2)

            # Should not raise
            await session.flush()

            # Both should exist
            user_repo = UserRepository(session)
            u1 = await user_repo.get_by_external_and_server(ext_id, server1.id)
            u2 = await user_repo.get_by_external_and_server(ext_id, server2.id)
            assert u1 is not None
            assert u2 is not None
            assert u1.id != u2.id


# =============================================================================
# Dedup: Sync skips already-imported users
# =============================================================================


class TestSyncSkipsAlreadyImportedUsers:
    """Sync import skips users that already exist locally."""

    @given(
        ext_id=external_id_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_sync_import_skips_existing_user(
        self,
        db: TestDB,
        ext_id: str,
        username: str,
    ) -> None:
        """When a user already exists locally, sync import skips it."""
        from zondarr.services.sync import SyncService

        await db.clean()
        async with db.session_factory() as session:
            server_repo = MediaServerRepository(session)
            server = MediaServer()
            server.name = "Test Server"
            server.server_type = "plex"
            server.url = "http://localhost:32400"
            server.api_key = "test-key"
            server.enabled = True
            server = await server_repo.create(server)
            await session.commit()

            # Pre-create identity + user (simulating prior sync/redemption)
            identity = Identity()
            identity.display_name = username
            identity.enabled = True
            session.add(identity)
            await session.flush()

            user = User()
            user.identity_id = identity.id
            user.media_server_id = server.id
            user.external_user_id = ext_id
            user.username = username
            user.enabled = True
            session.add(user)
            await session.commit()

            # Mock client returns this user as "on server" but not in local_ids
            # We'll manually construct the scenario by making list_users return
            # users that include one already in the DB
            ext_user = ExternalUser(
                external_user_id=ext_id,
                username=username,
                email=None,
            )
            mock_client = AsyncMock()
            mock_client.list_users = AsyncMock(return_value=[ext_user])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_registry = MagicMock(spec=ClientRegistry)
            mock_registry.create_client_for_server = MagicMock(return_value=mock_client)

            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            sync_service = SyncService(server_repo, user_repo, identity_repo)

            with patch("zondarr.services.sync.registry", mock_registry):
                result = await sync_service.sync_server(server.id, dry_run=False)
            await session.commit()

            # User was already matched, so no imports needed
            assert result.imported_users == 0
            assert result.matched_users == 1

            # Verify only one user exists (no duplicate)
            all_users = await user_repo.get_by_server(server.id)
            ext_ids = [u.external_user_id for u in all_users]
            assert ext_ids.count(ext_id) == 1
