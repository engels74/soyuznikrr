"""Property-based tests for SyncService.

Feature: jellyfin-integration
Properties: 22, 23, 24
Validates: Requirements 20.3, 20.4, 20.6, 20.7
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.media.registry import ClientRegistry
from zondarr.media.types import ExternalUser
from zondarr.models import MediaServer, ServerType
from zondarr.models.identity import Identity, User
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.sync import SyncService

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for generating valid external user IDs (UUIDs as strings)
external_id_strategy = st.uuids().map(str)

# Strategy for generating usernames
username_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=3,
    max_size=20,
).filter(lambda x: x.strip() and x[0].isalpha())


@st.composite
def user_sets_strategy(
    draw: st.DrawFn,
) -> tuple[list[ExternalUser], list[ExternalUser], list[ExternalUser]]:
    """Generate three disjoint sets of users: orphaned, stale, and matched.

    Returns:
        Tuple of (orphaned_users, stale_users, matched_users) where:
        - orphaned_users: exist on server only
        - stale_users: exist locally only
        - matched_users: exist in both places
    """
    # Generate unique external IDs for each category
    num_orphaned = draw(st.integers(min_value=0, max_value=5))
    num_stale = draw(st.integers(min_value=0, max_value=5))
    num_matched = draw(st.integers(min_value=0, max_value=5))

    # Generate unique IDs for all users
    all_ids = draw(
        st.lists(
            external_id_strategy,
            min_size=num_orphaned + num_stale + num_matched,
            max_size=num_orphaned + num_stale + num_matched,
            unique=True,
        )
    )

    orphaned_ids = all_ids[:num_orphaned]
    stale_ids = all_ids[num_orphaned : num_orphaned + num_stale]
    matched_ids = all_ids[num_orphaned + num_stale :]

    # Generate usernames for each user
    orphaned_users = [
        ExternalUser(
            external_user_id=uid,
            username=draw(username_strategy),
            email=None,
        )
        for uid in orphaned_ids
    ]

    stale_users = [
        ExternalUser(
            external_user_id=uid,
            username=draw(username_strategy),
            email=None,
        )
        for uid in stale_ids
    ]

    matched_users = [
        ExternalUser(
            external_user_id=uid,
            username=draw(username_strategy),
            email=None,
        )
        for uid in matched_ids
    ]

    return orphaned_users, stale_users, matched_users


# =============================================================================
# Property 22: Sync Identifies Discrepancies Correctly
# =============================================================================


class TestSyncIdentifiesDiscrepanciesCorrectly:
    """Property 22: Sync Identifies Discrepancies Correctly.

    **Validates: Requirements 20.3, 20.4**

    For any media server with Jellyfin users J and local users L:
    - orphaned_users = {u.username for u in J if u.external_user_id not in {l.external_user_id for l in L}}
    - stale_users = {l.username for l in L if l.external_user_id not in {j.external_user_id for j in J}}
    """

    @given(user_sets=user_sets_strategy())
    @pytest.mark.asyncio
    async def test_sync_identifies_orphaned_users(
        self,
        user_sets: tuple[list[ExternalUser], list[ExternalUser], list[ExternalUser]],
    ) -> None:
        """Sync correctly identifies users on server but not in local DB (orphaned).

        **Validates: Requirement 20.3**
        """
        orphaned_users, stale_users, matched_users = user_sets

        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                # Create a media server
                server_repo = MediaServerRepository(session)
                server = MediaServer()
                server.name = "Test Server"
                server.server_type = ServerType.JELLYFIN
                server.url = "http://localhost:8096"
                server.api_key = "test-api-key"
                server.enabled = True
                server = await server_repo.create(server)
                await session.commit()

                # Create an identity for local users
                identity = Identity()
                identity.display_name = "Test Identity"
                identity.enabled = True
                session.add(identity)
                await session.flush()

                # Create local users for stale and matched categories
                for ext_user in stale_users + matched_users:
                    local_user = User()
                    local_user.identity_id = identity.id
                    local_user.media_server_id = server.id
                    local_user.external_user_id = ext_user.external_user_id
                    local_user.username = ext_user.username
                    local_user.enabled = True
                    session.add(local_user)
                await session.commit()

                # Mock the client to return orphaned + matched users (server users)
                server_users = orphaned_users + matched_users
                mock_client = AsyncMock()
                mock_client.list_users = AsyncMock(return_value=server_users)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_registry = MagicMock(spec=ClientRegistry)
                mock_registry.create_client = MagicMock(return_value=mock_client)

                user_repo = UserRepository(session)
                sync_service = SyncService(server_repo, user_repo)

                with patch("zondarr.services.sync.registry", mock_registry):
                    result = await sync_service.sync_server(server.id)

                # Verify orphaned users are correctly identified
                expected_orphaned = {u.username for u in orphaned_users}
                actual_orphaned = set(result.orphaned_users)
                assert actual_orphaned == expected_orphaned, (
                    f"Expected orphaned: {expected_orphaned}, got: {actual_orphaned}"
                )
        finally:
            await engine.dispose()

    @given(user_sets=user_sets_strategy())
    @pytest.mark.asyncio
    async def test_sync_identifies_stale_users(
        self,
        user_sets: tuple[list[ExternalUser], list[ExternalUser], list[ExternalUser]],
    ) -> None:
        """Sync correctly identifies users in local DB but not on server (stale).

        **Validates: Requirement 20.4**
        """
        orphaned_users, stale_users, matched_users = user_sets

        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                # Create a media server
                server_repo = MediaServerRepository(session)
                server = MediaServer()
                server.name = "Test Server"
                server.server_type = ServerType.JELLYFIN
                server.url = "http://localhost:8096"
                server.api_key = "test-api-key"
                server.enabled = True
                server = await server_repo.create(server)
                await session.commit()

                # Create an identity for local users
                identity = Identity()
                identity.display_name = "Test Identity"
                identity.enabled = True
                session.add(identity)
                await session.flush()

                # Create local users for stale and matched categories
                for ext_user in stale_users + matched_users:
                    local_user = User()
                    local_user.identity_id = identity.id
                    local_user.media_server_id = server.id
                    local_user.external_user_id = ext_user.external_user_id
                    local_user.username = ext_user.username
                    local_user.enabled = True
                    session.add(local_user)
                await session.commit()

                # Mock the client to return orphaned + matched users (server users)
                server_users = orphaned_users + matched_users
                mock_client = AsyncMock()
                mock_client.list_users = AsyncMock(return_value=server_users)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_registry = MagicMock(spec=ClientRegistry)
                mock_registry.create_client = MagicMock(return_value=mock_client)

                user_repo = UserRepository(session)
                sync_service = SyncService(server_repo, user_repo)

                with patch("zondarr.services.sync.registry", mock_registry):
                    result = await sync_service.sync_server(server.id)

                # Verify stale users are correctly identified
                expected_stale = {u.username for u in stale_users}
                actual_stale = set(result.stale_users)
                assert actual_stale == expected_stale, (
                    f"Expected stale: {expected_stale}, got: {actual_stale}"
                )
        finally:
            await engine.dispose()

    @given(user_sets=user_sets_strategy())
    @pytest.mark.asyncio
    async def test_sync_counts_matched_users(
        self,
        user_sets: tuple[list[ExternalUser], list[ExternalUser], list[ExternalUser]],
    ) -> None:
        """Sync correctly counts users that exist in both places (matched).

        **Validates: Requirements 20.3, 20.4**
        """
        orphaned_users, stale_users, matched_users = user_sets

        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                # Create a media server
                server_repo = MediaServerRepository(session)
                server = MediaServer()
                server.name = "Test Server"
                server.server_type = ServerType.JELLYFIN
                server.url = "http://localhost:8096"
                server.api_key = "test-api-key"
                server.enabled = True
                server = await server_repo.create(server)
                await session.commit()

                # Create an identity for local users
                identity = Identity()
                identity.display_name = "Test Identity"
                identity.enabled = True
                session.add(identity)
                await session.flush()

                # Create local users for stale and matched categories
                for ext_user in stale_users + matched_users:
                    local_user = User()
                    local_user.identity_id = identity.id
                    local_user.media_server_id = server.id
                    local_user.external_user_id = ext_user.external_user_id
                    local_user.username = ext_user.username
                    local_user.enabled = True
                    session.add(local_user)
                await session.commit()

                # Mock the client to return orphaned + matched users (server users)
                server_users = orphaned_users + matched_users
                mock_client = AsyncMock()
                mock_client.list_users = AsyncMock(return_value=server_users)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_registry = MagicMock(spec=ClientRegistry)
                mock_registry.create_client = MagicMock(return_value=mock_client)

                user_repo = UserRepository(session)
                sync_service = SyncService(server_repo, user_repo)

                with patch("zondarr.services.sync.registry", mock_registry):
                    result = await sync_service.sync_server(server.id)

                # Verify matched count is correct
                assert result.matched_users == len(matched_users), (
                    f"Expected {len(matched_users)} matched users, got {result.matched_users}"
                )
        finally:
            await engine.dispose()


# =============================================================================
# Property 23: Sync Is Idempotent
# =============================================================================


class TestSyncIsIdempotent:
    """Property 23: Sync Is Idempotent.

    **Validates: Requirement 20.6**

    For any media server, running sync N times (N > 1) should produce
    the same orphaned_users, stale_users, and matched_users counts each time.
    """

    @given(
        user_sets=user_sets_strategy(),
        num_runs=st.integers(min_value=2, max_value=5),
    )
    @pytest.mark.asyncio
    async def test_sync_produces_same_results_on_multiple_runs(
        self,
        user_sets: tuple[list[ExternalUser], list[ExternalUser], list[ExternalUser]],
        num_runs: int,
    ) -> None:
        """Running sync multiple times produces identical results.

        **Validates: Requirement 20.6**
        """
        orphaned_users, stale_users, matched_users = user_sets

        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                # Create a media server
                server_repo = MediaServerRepository(session)
                server = MediaServer()
                server.name = "Test Server"
                server.server_type = ServerType.JELLYFIN
                server.url = "http://localhost:8096"
                server.api_key = "test-api-key"
                server.enabled = True
                server = await server_repo.create(server)
                await session.commit()

                # Create an identity for local users
                identity = Identity()
                identity.display_name = "Test Identity"
                identity.enabled = True
                session.add(identity)
                await session.flush()

                # Create local users for stale and matched categories
                for ext_user in stale_users + matched_users:
                    local_user = User()
                    local_user.identity_id = identity.id
                    local_user.media_server_id = server.id
                    local_user.external_user_id = ext_user.external_user_id
                    local_user.username = ext_user.username
                    local_user.enabled = True
                    session.add(local_user)
                await session.commit()

                # Mock the client to return orphaned + matched users (server users)
                server_users = orphaned_users + matched_users
                mock_client = AsyncMock()
                mock_client.list_users = AsyncMock(return_value=server_users)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_registry = MagicMock(spec=ClientRegistry)
                mock_registry.create_client = MagicMock(return_value=mock_client)

                user_repo = UserRepository(session)
                sync_service = SyncService(server_repo, user_repo)

                # Run sync multiple times and collect results
                from zondarr.api.schemas import SyncResult

                results: list[SyncResult] = []
                with patch("zondarr.services.sync.registry", mock_registry):
                    for _ in range(num_runs):
                        result = await sync_service.sync_server(server.id)
                        results.append(result)

                # Verify all results are identical (except synced_at timestamp)
                first_result: SyncResult = results[0]
                for i, result in enumerate(results[1:], start=2):
                    assert set(result.orphaned_users) == set(
                        first_result.orphaned_users
                    ), f"Run {i} orphaned_users differs from run 1"
                    assert set(result.stale_users) == set(first_result.stale_users), (
                        f"Run {i} stale_users differs from run 1"
                    )
                    assert result.matched_users == first_result.matched_users, (
                        f"Run {i} matched_users ({result.matched_users}) differs from run 1 ({first_result.matched_users})"
                    )
                    assert result.server_id == first_result.server_id
                    assert result.server_name == first_result.server_name
        finally:
            await engine.dispose()


# =============================================================================
# Property 24: Sync Does Not Modify Users
# =============================================================================


class TestSyncDoesNotModifyUsers:
    """Property 24: Sync Does Not Modify Users.

    **Validates: Requirement 20.7**

    For any sync operation, the count of local User records and Jellyfin users
    should remain unchanged before and after the sync.
    """

    @given(user_sets=user_sets_strategy())
    @pytest.mark.asyncio
    async def test_sync_does_not_modify_local_users(
        self,
        user_sets: tuple[list[ExternalUser], list[ExternalUser], list[ExternalUser]],
    ) -> None:
        """Sync does not create, delete, or modify local User records.

        **Validates: Requirement 20.7**
        """
        orphaned_users, stale_users, matched_users = user_sets

        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                # Create a media server
                server_repo = MediaServerRepository(session)
                server = MediaServer()
                server.name = "Test Server"
                server.server_type = ServerType.JELLYFIN
                server.url = "http://localhost:8096"
                server.api_key = "test-api-key"
                server.enabled = True
                server = await server_repo.create(server)
                await session.commit()

                # Create an identity for local users
                identity = Identity()
                identity.display_name = "Test Identity"
                identity.enabled = True
                session.add(identity)
                await session.flush()

                # Create local users for stale and matched categories
                local_users_before: list[tuple[str, str]] = []
                for ext_user in stale_users + matched_users:
                    local_user = User()
                    local_user.identity_id = identity.id
                    local_user.media_server_id = server.id
                    local_user.external_user_id = ext_user.external_user_id
                    local_user.username = ext_user.username
                    local_user.enabled = True
                    session.add(local_user)
                    local_users_before.append(
                        (ext_user.external_user_id, ext_user.username)
                    )
                await session.commit()

                # Record the count of local users before sync
                user_repo = UserRepository(session)
                users_before = await user_repo.get_by_server(server.id)
                count_before = len(users_before)

                # Mock the client to return orphaned + matched users (server users)
                server_users = orphaned_users + matched_users
                mock_client = AsyncMock()
                mock_client.list_users = AsyncMock(return_value=server_users)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_registry = MagicMock(spec=ClientRegistry)
                mock_registry.create_client = MagicMock(return_value=mock_client)

                sync_service = SyncService(server_repo, user_repo)

                with patch("zondarr.services.sync.registry", mock_registry):
                    _ = await sync_service.sync_server(server.id)

                # Verify local users are unchanged after sync
                users_after = await user_repo.get_by_server(server.id)
                count_after = len(users_after)

                assert count_after == count_before, (
                    f"Local user count changed from {count_before} to {count_after}"
                )

                # Verify the same users exist with same data
                local_users_after = {
                    (u.external_user_id, u.username) for u in users_after
                }
                assert local_users_after == set(local_users_before), (
                    "Local user data was modified during sync"
                )
        finally:
            await engine.dispose()

    @given(user_sets=user_sets_strategy())
    @pytest.mark.asyncio
    async def test_sync_does_not_call_modify_methods_on_client(
        self,
        user_sets: tuple[list[ExternalUser], list[ExternalUser], list[ExternalUser]],
    ) -> None:
        """Sync only calls list_users, not create/delete/update methods.

        **Validates: Requirement 20.7**
        """
        orphaned_users, stale_users, matched_users = user_sets

        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                # Create a media server
                server_repo = MediaServerRepository(session)
                server = MediaServer()
                server.name = "Test Server"
                server.server_type = ServerType.JELLYFIN
                server.url = "http://localhost:8096"
                server.api_key = "test-api-key"
                server.enabled = True
                server = await server_repo.create(server)
                await session.commit()

                # Create an identity for local users
                identity = Identity()
                identity.display_name = "Test Identity"
                identity.enabled = True
                session.add(identity)
                await session.flush()

                # Create local users for stale and matched categories
                for ext_user in stale_users + matched_users:
                    local_user = User()
                    local_user.identity_id = identity.id
                    local_user.media_server_id = server.id
                    local_user.external_user_id = ext_user.external_user_id
                    local_user.username = ext_user.username
                    local_user.enabled = True
                    session.add(local_user)
                await session.commit()

                # Mock the client with all methods tracked
                server_users = orphaned_users + matched_users
                mock_client = AsyncMock()
                mock_client.list_users = AsyncMock(return_value=server_users)
                mock_client.create_user = AsyncMock()
                mock_client.delete_user = AsyncMock()
                mock_client.set_user_enabled = AsyncMock()
                mock_client.update_permissions = AsyncMock()
                mock_client.set_library_access = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_registry = MagicMock(spec=ClientRegistry)
                mock_registry.create_client = MagicMock(return_value=mock_client)

                user_repo = UserRepository(session)
                sync_service = SyncService(server_repo, user_repo)

                with patch("zondarr.services.sync.registry", mock_registry):
                    _ = await sync_service.sync_server(server.id)

                # Verify only list_users was called, not any modification methods
                mock_client.list_users.assert_called_once()  # pyright: ignore[reportAny]
                mock_client.create_user.assert_not_called()  # pyright: ignore[reportAny]
                mock_client.delete_user.assert_not_called()  # pyright: ignore[reportAny]
                mock_client.set_user_enabled.assert_not_called()  # pyright: ignore[reportAny]
                mock_client.update_permissions.assert_not_called()  # pyright: ignore[reportAny]
                mock_client.set_library_access.assert_not_called()  # pyright: ignore[reportAny]
        finally:
            await engine.dispose()


# =============================================================================
# Property 4: Sync Task Error Resilience (Background Task)
# =============================================================================


class TestSyncTaskErrorResilience:
    """Property 4: Sync Task Error Resilience.

    For any set of media servers being synced, if syncing one server fails,
    the remaining servers SHALL still be synced.

    **Validates: Requirements 2.5**
    """

    @given(
        num_servers=st.integers(min_value=2, max_value=4),
        failing_server_index=st.integers(min_value=0, max_value=3),
    )
    @pytest.mark.asyncio
    async def test_sync_continues_after_server_failure(
        self,
        num_servers: int,
        failing_server_index: int,
    ) -> None:
        """Sync task continues processing servers even when one fails.

        **Validates: Requirement 2.5**
        """
        # Ensure failing index is within bounds
        failing_server_index = failing_server_index % num_servers

        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            # Create multiple media servers
            server_ids: list[str] = []
            async with session_factory() as session:
                server_repo = MediaServerRepository(session)

                for i in range(num_servers):
                    server = MediaServer()
                    server.name = f"Test Server {i}"
                    server.server_type = ServerType.JELLYFIN
                    server.url = f"http://server{i}:8096"
                    server.api_key = f"api-key-{i}"
                    server.enabled = True
                    server = await server_repo.create(server)
                    server_ids.append(str(server.id))
                await session.commit()

            # Create mock client that fails for one server
            call_count = 0
            successful_syncs: list[str] = []

            def create_mock_client(
                _server_type: ServerType,
                *,
                url: str,
                api_key: str,  # pyright: ignore[reportUnusedParameter]
            ) -> AsyncMock:
                nonlocal call_count
                current_call = call_count
                call_count += 1

                mock_client = AsyncMock()

                if current_call == failing_server_index:
                    # This server will fail
                    mock_client.list_users = AsyncMock(
                        side_effect=Exception("Connection failed")
                    )
                else:
                    # This server will succeed
                    mock_client.list_users = AsyncMock(return_value=[])
                    successful_syncs.append(url)

                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                return mock_client

            mock_registry = MagicMock(spec=ClientRegistry)
            mock_registry.create_client = MagicMock(side_effect=create_mock_client)

            # Run the background task sync
            from zondarr.config import Settings
            from zondarr.core.tasks import BackgroundTaskManager

            settings = Settings(
                secret_key="test-secret-key-at-least-32-characters-long",
                expiration_check_interval_seconds=60,
                sync_interval_seconds=60,
            )
            manager = BackgroundTaskManager(settings)

            state = MagicMock()
            state.session_factory = session_factory

            with patch("zondarr.services.sync.registry", mock_registry):
                await manager.sync_all_servers(state)

            # Verify that all servers were attempted (num_servers calls)
            assert call_count == num_servers, (
                f"Expected {num_servers} sync attempts, got {call_count}"
            )

            # Verify that successful servers were synced (num_servers - 1)
            assert len(successful_syncs) == num_servers - 1, (
                f"Expected {num_servers - 1} successful syncs, got {len(successful_syncs)}"
            )
        finally:
            await engine.dispose()

    @given(num_servers=st.integers(min_value=1, max_value=3))
    @pytest.mark.asyncio
    async def test_sync_task_handles_empty_server_list(
        self,
        num_servers: int,
    ) -> None:
        """Sync task handles case when no servers are enabled.

        **Validates: Requirement 2.5**
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            # Create disabled servers
            async with session_factory() as session:
                server_repo = MediaServerRepository(session)

                for i in range(num_servers):
                    server = MediaServer()
                    server.name = f"Disabled Server {i}"
                    server.server_type = ServerType.JELLYFIN
                    server.url = f"http://disabled{i}:8096"
                    server.api_key = f"api-key-{i}"
                    server.enabled = False  # All disabled
                    _ = await server_repo.create(server)
                await session.commit()

            # Run the background task sync
            from zondarr.config import Settings
            from zondarr.core.tasks import BackgroundTaskManager

            settings = Settings(
                secret_key="test-secret-key-at-least-32-characters-long",
                expiration_check_interval_seconds=60,
                sync_interval_seconds=60,
            )
            manager = BackgroundTaskManager(settings)

            state = MagicMock()
            state.session_factory = session_factory

            # Should complete without error even with no enabled servers
            await manager.sync_all_servers(state)
        finally:
            await engine.dispose()
