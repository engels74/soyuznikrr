"""Property-based tests for UserService.

Feature: jellyfin-integration

Property 19: Enable/Disable Atomicity
**Validates: Requirements 18.3, 18.4**

Tests that for any user enable/disable operation:
- If the Jellyfin API call succeeds, the local User.enabled field is updated
- If the Jellyfin API call fails, the local User.enabled field remains unchanged

Property 20: User Deletion Atomicity
**Validates: Requirements 19.3, 19.4**

Tests that for any user deletion operation:
- If the Jellyfin API call succeeds, the local User record is deleted
- If the Jellyfin API call fails, the local User record still exists
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import TestDB
from zondarr.core.exceptions import ValidationError
from zondarr.media.exceptions import MediaClientError
from zondarr.media.registry import ClientRegistry
from zondarr.models import ServerType
from zondarr.models.identity import Identity, User
from zondarr.models.media_server import MediaServer
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.user import UserService

# =============================================================================
# Custom Strategies
# =============================================================================

# Username strategy - valid usernames for media servers
username_strategy = st.text(
    alphabet=st.characters(categories=("Ll",)),  # Lowercase letters only
    min_size=3,
    max_size=20,
).filter(lambda x: x.isalpha() and len(x) >= 3)

# External user ID strategy - simulates Jellyfin GUIDs
external_user_id_strategy = st.uuids().map(str)

# Server name strategy
server_name_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=1,
    max_size=50,
).filter(lambda x: x.strip())


# =============================================================================
# Helper Functions
# =============================================================================


def create_mock_client_success(*, enabled: bool) -> AsyncMock:
    """Create a mock media client that succeeds on set_user_enabled.

    Args:
        enabled: The enabled value being set (unused but documents intent).

    Returns:
        A mock client that returns True for set_user_enabled.
    """
    del enabled  # Unused but documents the operation being mocked
    mock_client = AsyncMock()
    mock_client.set_user_enabled = AsyncMock(return_value=True)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def create_mock_client_failure(
    *, error_message: str = "Connection failed"
) -> AsyncMock:
    """Create a mock media client that fails on set_user_enabled.

    Args:
        error_message: The error message for the MediaClientError.

    Returns:
        A mock client that raises MediaClientError for set_user_enabled.
    """
    mock_client = AsyncMock()
    mock_client.set_user_enabled = AsyncMock(
        side_effect=MediaClientError(
            error_message,
            operation="set_user_enabled",
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def create_mock_client_user_not_found() -> AsyncMock:
    """Create a mock media client that returns False (user not found).

    Returns:
        A mock client that returns False for set_user_enabled.
    """
    mock_client = AsyncMock()
    mock_client.set_user_enabled = AsyncMock(return_value=False)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def create_mock_client_delete_success() -> AsyncMock:
    """Create a mock media client that succeeds on delete_user.

    Returns:
        A mock client that returns True for delete_user.
    """
    mock_client = AsyncMock()
    mock_client.delete_user = AsyncMock(return_value=True)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def create_mock_client_delete_failure(
    *, error_message: str = "Connection failed"
) -> AsyncMock:
    """Create a mock media client that fails on delete_user.

    Args:
        error_message: The error message for the MediaClientError.

    Returns:
        A mock client that raises MediaClientError for delete_user.
    """
    mock_client = AsyncMock()
    mock_client.delete_user = AsyncMock(
        side_effect=MediaClientError(
            error_message,
            operation="delete_user",
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def create_mock_client_delete_user_not_found() -> AsyncMock:
    """Create a mock media client that returns False (user not found on delete).

    Returns:
        A mock client that returns False for delete_user.
    """
    mock_client = AsyncMock()
    mock_client.delete_user = AsyncMock(return_value=False)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


async def create_test_user_with_server(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    username: str,
    external_user_id: str,
    initial_enabled: bool,
) -> tuple[User, MediaServer, Identity]:
    """Create a test user with associated media server and identity.

    Args:
        session_factory: The async session factory.
        username: The username for the user.
        external_user_id: The external user ID on the media server.
        initial_enabled: The initial enabled state of the user.

    Returns:
        A tuple of (User, MediaServer, Identity) created in the database.
    """
    async with session_factory() as session:
        # Create media server
        server = MediaServer(
            name="TestServer",
            server_type=ServerType.JELLYFIN,
            url="http://jellyfin.local:8096",
            api_key="test-api-key",
            enabled=True,
        )
        session.add(server)
        await session.flush()

        # Create identity
        identity = Identity(
            display_name=username,
            email=None,
            expires_at=None,
            enabled=True,
        )
        session.add(identity)
        await session.flush()

        # Create user
        user = User(
            identity_id=identity.id,
            media_server_id=server.id,
            invitation_id=None,
            external_user_id=external_user_id,
            username=username,
            expires_at=None,
            enabled=initial_enabled,
        )
        session.add(user)
        await session.commit()

        # Refresh to get all relationships loaded
        await session.refresh(user)
        await session.refresh(server)
        await session.refresh(identity)

        return user, server, identity


# =============================================================================
# Property 19: Enable/Disable Atomicity
# =============================================================================


class TestEnableDisableAtomicity:
    """Property 19: Enable/Disable Atomicity.

    **Validates: Requirements 18.3, 18.4**

    For any user enable/disable operation:
    - If the Jellyfin API call succeeds, the local User.enabled field is updated
    - If the Jellyfin API call fails, the local User.enabled field remains unchanged
    """

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
        initial_enabled=st.booleans(),
        target_enabled=st.booleans(),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_successful_update_changes_local_record(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
        initial_enabled: bool,
        target_enabled: bool,
    ) -> None:
        """When Jellyfin update succeeds, local User.enabled is updated.

        **Validates: Requirements 18.3**

        Property: For any user with initial enabled state I and target state T,
        if the Jellyfin API call succeeds, the local User.enabled becomes T.
        """
        await db.clean()

        # Create test user with initial enabled state
        user, _server, _identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=initial_enabled,
        )
        user_id = user.id

        # Create mock registry that returns successful client
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_success(enabled=target_enabled)
        )

        # Execute set_enabled operation
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                updated_user = await user_service.set_enabled(
                    user_id,
                    enabled=target_enabled,
                )

            await session.commit()

            # PROPERTY ASSERTION: Local record is updated to target state
            assert updated_user.enabled == target_enabled, (
                f"Expected enabled={target_enabled}, got {updated_user.enabled}"
            )

        # Verify persistence by reading from fresh session
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            persisted_user = await user_repo.get_by_id(user_id)
            assert persisted_user is not None
            assert persisted_user.enabled == target_enabled, (
                f"Persisted enabled={persisted_user.enabled}, expected {target_enabled}"
            )

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
        initial_enabled=st.booleans(),
        target_enabled=st.booleans(),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_failed_update_preserves_local_record(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
        initial_enabled: bool,
        target_enabled: bool,
    ) -> None:
        """When Jellyfin update fails, local User.enabled remains unchanged.

        **Validates: Requirements 18.4**

        Property: For any user with initial enabled state I and target state T,
        if the Jellyfin API call fails, the local User.enabled remains I.
        """
        await db.clean()

        # Create test user with initial enabled state
        user, _server, _identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=initial_enabled,
        )
        user_id = user.id

        # Create mock registry that returns failing client
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_failure(
                error_message="Jellyfin server unavailable"
            )
        )

        # Execute set_enabled operation - should raise ValidationError
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                with pytest.raises(ValidationError) as exc_info:
                    _ = await user_service.set_enabled(
                        user_id,
                        enabled=target_enabled,
                    )

            # Verify exception contains relevant error info
            assert "media server" in exc_info.value.message.lower()

        # PROPERTY ASSERTION: Local record is unchanged
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            persisted_user = await user_repo.get_by_id(user_id)
            assert persisted_user is not None
            assert persisted_user.enabled == initial_enabled, (
                f"Expected enabled to remain {initial_enabled}, "
                f"but got {persisted_user.enabled}"
            )

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
        initial_enabled=st.booleans(),
        target_enabled=st.booleans(),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_user_not_found_on_server_preserves_local_record(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
        initial_enabled: bool,
        target_enabled: bool,
    ) -> None:
        """When user not found on Jellyfin, local User.enabled remains unchanged.

        **Validates: Requirements 18.4**

        Property: For any user that exists locally but not on the media server,
        the set_enabled operation should fail and preserve the local state.
        """
        await db.clean()

        # Create test user with initial enabled state
        user, _server, _identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=initial_enabled,
        )
        user_id = user.id

        # Create mock registry that returns "user not found" response
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_user_not_found()
        )

        # Execute set_enabled operation - should raise ValidationError
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                with pytest.raises(ValidationError) as exc_info:
                    _ = await user_service.set_enabled(
                        user_id,
                        enabled=target_enabled,
                    )

            # Verify exception indicates user not found
            assert "not found" in exc_info.value.message.lower()

        # PROPERTY ASSERTION: Local record is unchanged
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            persisted_user = await user_repo.get_by_id(user_id)
            assert persisted_user is not None
            assert persisted_user.enabled == initial_enabled, (
                f"Expected enabled to remain {initial_enabled}, "
                f"but got {persisted_user.enabled}"
            )

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
        initial_enabled=st.booleans(),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_idempotent_enable_disable(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
        initial_enabled: bool,
    ) -> None:
        """Setting enabled to current value is idempotent.

        **Validates: Requirements 18.3**

        Property: For any user with enabled state E, setting enabled to E
        should succeed and leave the state as E.
        """
        await db.clean()

        # Create test user with initial enabled state
        user, _server, _identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=initial_enabled,
        )
        user_id = user.id

        # Create mock registry that returns successful client
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_success(enabled=initial_enabled)
        )

        # Execute set_enabled with same value
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                updated_user = await user_service.set_enabled(
                    user_id,
                    enabled=initial_enabled,  # Same as current
                )

            await session.commit()

            # PROPERTY ASSERTION: State remains the same
            assert updated_user.enabled == initial_enabled, (
                f"Expected enabled={initial_enabled}, got {updated_user.enabled}"
            )

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
        initial_enabled=st.booleans(),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_toggle_enabled_state(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
        initial_enabled: bool,
    ) -> None:
        """Toggling enabled state works correctly.

        **Validates: Requirements 18.3**

        Property: For any user with enabled state E, setting enabled to !E
        should result in the user having enabled state !E.
        """
        await db.clean()

        # Create test user with initial enabled state
        user, _server, _identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=initial_enabled,
        )
        user_id = user.id
        target_enabled = not initial_enabled

        # Create mock registry that returns successful client
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_success(enabled=target_enabled)
        )

        # Execute set_enabled with toggled value
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                updated_user = await user_service.set_enabled(
                    user_id,
                    enabled=target_enabled,
                )

            await session.commit()

            # PROPERTY ASSERTION: State is toggled
            assert updated_user.enabled == target_enabled, (
                f"Expected enabled={target_enabled}, got {updated_user.enabled}"
            )
            assert updated_user.enabled != initial_enabled, (
                f"Expected enabled to change from {initial_enabled}"
            )


# =============================================================================
# Property 20: User Deletion Atomicity
# =============================================================================


class TestUserDeletionAtomicity:
    """Property 20: User Deletion Atomicity.

    **Validates: Requirements 19.3, 19.4**

    For any user deletion operation:
    - If the Jellyfin API call succeeds, the local User record is deleted (19.3)
    - If the Jellyfin API call fails, the local User record still exists (19.4)
    """

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
        initial_enabled=st.booleans(),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_successful_delete_removes_local_record(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
        initial_enabled: bool,
    ) -> None:
        """When Jellyfin deletion succeeds, local User record is deleted.

        **Validates: Requirements 19.3**

        Property: For any user, if the Jellyfin API delete_user call succeeds,
        the local User record is deleted from the database.
        """
        await db.clean()

        # Create test user
        user, _server, _identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=initial_enabled,
        )
        user_id = user.id

        # Create mock registry that returns successful delete client
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_delete_success()
        )

        # Execute delete operation
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                await user_service.delete(user_id)

            await session.commit()

        # PROPERTY ASSERTION: Local record is deleted
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            deleted_user = await user_repo.get_by_id(user_id)
            assert deleted_user is None, (
                f"Expected user {user_id} to be deleted, but it still exists"
            )

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
        initial_enabled=st.booleans(),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_failed_delete_preserves_local_record(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
        initial_enabled: bool,
    ) -> None:
        """When Jellyfin deletion fails, local User record remains unchanged.

        **Validates: Requirements 19.4**

        Property: For any user, if the Jellyfin API delete_user call fails
        with MediaClientError, the local User record still exists in the database.
        """
        await db.clean()

        # Create test user
        user, _server, _identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=initial_enabled,
        )
        user_id = user.id

        # Create mock registry that returns failing delete client
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_delete_failure(
                error_message="Jellyfin server unavailable"
            )
        )

        # Execute delete operation - should raise ValidationError
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                with pytest.raises(ValidationError) as exc_info:
                    await user_service.delete(user_id)

            # Verify exception contains relevant error info
            assert "media server" in exc_info.value.message.lower()

        # PROPERTY ASSERTION: Local record still exists
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            persisted_user = await user_repo.get_by_id(user_id)
            assert persisted_user is not None, (
                f"Expected user {user_id} to still exist after failed delete"
            )
            assert persisted_user.username == username, (
                f"Expected username {username}, got {persisted_user.username}"
            )
            assert persisted_user.enabled == initial_enabled, (
                f"Expected enabled={initial_enabled}, got {persisted_user.enabled}"
            )

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
        initial_enabled=st.booleans(),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_user_not_found_on_server_still_deletes_local(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
        initial_enabled: bool,
    ) -> None:
        """When user not found on Jellyfin, local User record is still deleted.

        **Validates: Requirements 19.3**

        Property: For any user that exists locally but not on the media server
        (delete_user returns False), the local User record should still be deleted.
        This handles the case where the user was already deleted externally.
        """
        await db.clean()

        # Create test user
        user, _server, _identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=initial_enabled,
        )
        user_id = user.id

        # Create mock registry that returns "user not found" response
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_delete_user_not_found()
        )

        # Execute delete operation - should succeed even if user not on server
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                await user_service.delete(user_id)

            await session.commit()

        # PROPERTY ASSERTION: Local record is deleted
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            deleted_user = await user_repo.get_by_id(user_id)
            assert deleted_user is None, (
                f"Expected user {user_id} to be deleted even when not found on server"
            )

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_delete_atomicity_external_first(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
    ) -> None:
        """Deletion is atomic - external deletion happens before local deletion.

        **Validates: Requirements 19.3, 19.4**

        Property: The delete operation must attempt external deletion first.
        If external deletion fails, local deletion must not occur.
        This ensures atomicity - either both succeed or neither happens.
        """
        await db.clean()

        # Create test user
        user, _server, _identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=True,
        )
        user_id = user.id

        # Track call order
        call_order: list[str] = []

        # Create mock client that tracks calls and fails
        mock_client = AsyncMock()

        async def track_delete_user(_ext_id: str, /) -> bool:
            call_order.append("external_delete")
            raise MediaClientError(
                "Server error",
                operation="delete_user",
            )

        mock_client.delete_user = track_delete_user
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(return_value=mock_client)

        # Execute delete operation - should fail
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                with pytest.raises(ValidationError):
                    await user_service.delete(user_id)

        # PROPERTY ASSERTION: External delete was attempted
        assert "external_delete" in call_order, (
            "External delete should be attempted before local delete"
        )

        # PROPERTY ASSERTION: Local record still exists (atomicity)
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            persisted_user = await user_repo.get_by_id(user_id)
            assert persisted_user is not None, (
                "Local record should exist when external delete fails (atomicity)"
            )

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_delete_calls_correct_external_user_id(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
    ) -> None:
        """Delete operation uses the correct external_user_id.

        **Validates: Requirements 19.2**

        Property: The delete operation must call the media client's delete_user
        method with the correct external_user_id from the User record.
        """
        await db.clean()

        # Create test user
        user, _server, _identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=True,
        )
        user_id = user.id

        # Track the external_user_id passed to delete_user
        captured_external_id: list[str] = []

        mock_client = AsyncMock()

        async def capture_delete_user(ext_id: str, /) -> bool:
            captured_external_id.append(ext_id)
            return True

        mock_client.delete_user = capture_delete_user
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(return_value=mock_client)

        # Execute delete operation
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                await user_service.delete(user_id)

            await session.commit()

        # PROPERTY ASSERTION: Correct external_user_id was used
        assert len(captured_external_id) == 1, (
            f"Expected exactly one delete_user call, got {len(captured_external_id)}"
        )
        assert captured_external_id[0] == external_user_id, (
            f"Expected external_user_id {external_user_id}, "
            f"got {captured_external_id[0]}"
        )


# =============================================================================
# Property 21: Last User Deletion Cascades to Identity
# =============================================================================


async def create_multiple_users_for_identity(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    identity_display_name: str,
    users_data: list[tuple[str, str]],
) -> tuple[Identity, list[User], MediaServer]:
    """Create an identity with multiple users on the same server.

    Args:
        session_factory: The async session factory.
        identity_display_name: Display name for the identity.
        users_data: List of (username, external_user_id) tuples.

    Returns:
        A tuple of (Identity, list of Users, MediaServer).
    """
    async with session_factory() as session:
        # Create media server
        server = MediaServer(
            name="TestServer",
            server_type=ServerType.JELLYFIN,
            url="http://jellyfin.local:8096",
            api_key="test-api-key",
            enabled=True,
        )
        session.add(server)
        await session.flush()

        # Create identity
        identity = Identity(
            display_name=identity_display_name,
            email=None,
            expires_at=None,
            enabled=True,
        )
        session.add(identity)
        await session.flush()

        # Create users
        users: list[User] = []
        for username, external_user_id in users_data:
            user = User(
                identity_id=identity.id,
                media_server_id=server.id,
                invitation_id=None,
                external_user_id=external_user_id,
                username=username,
                expires_at=None,
                enabled=True,
            )
            session.add(user)
            users.append(user)

        await session.commit()

        # Refresh to get all relationships loaded
        for user in users:
            await session.refresh(user)
        await session.refresh(server)
        await session.refresh(identity)

        return identity, users, server


class TestIdentityCascade:
    """Property 21: Last User Deletion Cascades to Identity.

    **Validates: Requirements 19.5**

    For any Identity with exactly one User, deleting that User should also
    delete the Identity. When other Users remain, the Identity is preserved.
    """

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_last_user_deletion_cascades_to_identity(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
    ) -> None:
        """Deleting the last User for an Identity also deletes the Identity.

        **Validates: Requirements 19.5**

        Property: For any Identity with exactly one User, when that User is
        deleted successfully, the Identity should also be deleted.
        """
        await db.clean()

        # Create test user (single user for identity)
        user, _server, identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=True,
        )
        user_id = user.id
        identity_id = identity.id

        # Create mock registry that returns successful delete client
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_delete_success()
        )

        # Execute delete operation
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                await user_service.delete(user_id)

            await session.commit()

        # PROPERTY ASSERTION: User is deleted
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            deleted_user = await user_repo.get_by_id(user_id)
            assert deleted_user is None, f"Expected user {user_id} to be deleted"

        # PROPERTY ASSERTION: Identity is also deleted (cascade)
        async with db.session_factory() as session:
            identity_repo = IdentityRepository(session)
            deleted_identity = await identity_repo.get_by_id(identity_id)
            assert deleted_identity is None, (
                f"Expected identity {identity_id} to be deleted when last user deleted"
            )

    @given(
        username1=username_strategy,
        username2=username_strategy,
        external_user_id1=external_user_id_strategy,
        external_user_id2=external_user_id_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_non_last_user_deletion_preserves_identity(
        self,
        db: TestDB,
        username1: str,
        username2: str,
        external_user_id1: str,
        external_user_id2: str,
    ) -> None:
        """Deleting a User when others remain does NOT delete the Identity.

        **Validates: Requirements 19.5**

        Property: For any Identity with multiple Users, when one User is
        deleted, the Identity should remain because other Users still exist.
        """
        # Ensure usernames and external IDs are different
        if username1 == username2:
            username2 = username2 + "x"
        if external_user_id1 == external_user_id2:
            external_user_id2 = external_user_id2 + "x"

        await db.clean()

        # Create identity with two users
        identity, users, _server = await create_multiple_users_for_identity(
            db.session_factory,
            identity_display_name="TestIdentity",
            users_data=[
                (username1, external_user_id1),
                (username2, external_user_id2),
            ],
        )
        user_to_delete_id = users[0].id
        remaining_user_id = users[1].id
        identity_id = identity.id

        # Create mock registry that returns successful delete client
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_delete_success()
        )

        # Execute delete operation on first user
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                await user_service.delete(user_to_delete_id)

            await session.commit()

        # PROPERTY ASSERTION: Deleted user is gone
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            deleted_user = await user_repo.get_by_id(user_to_delete_id)
            assert deleted_user is None, (
                f"Expected user {user_to_delete_id} to be deleted"
            )

        # PROPERTY ASSERTION: Remaining user still exists
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            remaining_user = await user_repo.get_by_id(remaining_user_id)
            assert remaining_user is not None, (
                f"Expected user {remaining_user_id} to still exist"
            )

        # PROPERTY ASSERTION: Identity is NOT deleted (other users remain)
        async with db.session_factory() as session:
            identity_repo = IdentityRepository(session)
            preserved_identity = await identity_repo.get_by_id(identity_id)
            assert preserved_identity is not None, (
                f"Expected identity {identity_id} to be preserved when other users remain"
            )

    @given(
        username=username_strategy,
        external_user_id=external_user_id_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_cascade_only_after_successful_external_deletion(
        self,
        db: TestDB,
        username: str,
        external_user_id: str,
    ) -> None:
        """Identity cascade only happens after successful external deletion.

        **Validates: Requirements 19.5**

        Property: For any Identity with exactly one User, if the external
        deletion fails, neither the User nor the Identity should be deleted.
        This ensures atomicity of the cascade operation.
        """
        await db.clean()

        # Create test user (single user for identity)
        user, _server, identity = await create_test_user_with_server(
            db.session_factory,
            username=username,
            external_user_id=external_user_id,
            initial_enabled=True,
        )
        user_id = user.id
        identity_id = identity.id

        # Create mock registry that returns failing delete client
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_delete_failure(
                error_message="Jellyfin server unavailable"
            )
        )

        # Execute delete operation - should raise ValidationError
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                with pytest.raises(ValidationError) as exc_info:
                    await user_service.delete(user_id)

            # Verify exception contains relevant error info
            assert "media server" in exc_info.value.message.lower()

        # PROPERTY ASSERTION: User still exists (atomicity)
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            persisted_user = await user_repo.get_by_id(user_id)
            assert persisted_user is not None, (
                f"Expected user {user_id} to still exist after failed external delete"
            )

        # PROPERTY ASSERTION: Identity still exists (cascade didn't happen)
        async with db.session_factory() as session:
            identity_repo = IdentityRepository(session)
            persisted_identity = await identity_repo.get_by_id(identity_id)
            assert persisted_identity is not None, (
                f"Expected identity {identity_id} to still exist after failed delete"
            )

    @given(
        username1=username_strategy,
        username2=username_strategy,
        external_user_id1=external_user_id_strategy,
        external_user_id2=external_user_id_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_sequential_deletion_eventually_cascades(
        self,
        db: TestDB,
        username1: str,
        username2: str,
        external_user_id1: str,
        external_user_id2: str,
    ) -> None:
        """Deleting all users sequentially eventually cascades to Identity.

        **Validates: Requirements 19.5**

        Property: For any Identity with N Users, deleting N-1 Users preserves
        the Identity, but deleting the Nth (last) User cascades to delete
        the Identity.
        """
        # Ensure usernames and external IDs are different
        if username1 == username2:
            username2 = username2 + "x"
        if external_user_id1 == external_user_id2:
            external_user_id2 = external_user_id2 + "x"

        await db.clean()

        # Create identity with two users
        identity, users, _server = await create_multiple_users_for_identity(
            db.session_factory,
            identity_display_name="TestIdentity",
            users_data=[
                (username1, external_user_id1),
                (username2, external_user_id2),
            ],
        )
        first_user_id = users[0].id
        second_user_id = users[1].id
        identity_id = identity.id

        # Create mock registry that returns successful delete client
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_delete_success()
        )

        # Delete first user - Identity should remain
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                await user_service.delete(first_user_id)

            await session.commit()

        # Verify Identity still exists after first deletion
        async with db.session_factory() as session:
            identity_repo = IdentityRepository(session)
            identity_after_first = await identity_repo.get_by_id(identity_id)
            assert identity_after_first is not None, (
                "Identity should exist after deleting first of two users"
            )

        # Reset mock for second deletion
        mock_registry.create_client = MagicMock(
            return_value=create_mock_client_delete_success()
        )

        # Delete second (last) user - Identity should be deleted
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            with patch("zondarr.services.user.registry", mock_registry):
                await user_service.delete(second_user_id)

            await session.commit()

        # PROPERTY ASSERTION: Both users are deleted
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            first_user = await user_repo.get_by_id(first_user_id)
            second_user = await user_repo.get_by_id(second_user_id)
            assert first_user is None, "First user should be deleted"
            assert second_user is None, "Second user should be deleted"

        # PROPERTY ASSERTION: Identity is now deleted (cascade after last user)
        async with db.session_factory() as session:
            identity_repo = IdentityRepository(session)
            final_identity = await identity_repo.get_by_id(identity_id)
            assert final_identity is None, (
                f"Expected identity {identity_id} to be deleted after last user deleted"
            )
