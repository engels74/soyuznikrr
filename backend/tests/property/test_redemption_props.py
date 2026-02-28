"""Property-based tests for RedemptionService.

Feature: jellyfin-integration
Property 15: Redemption Creates Users on All Target Servers

Tests that for N target servers in an invitation, exactly N User records
are created, each linked to the correct MediaServer, and all linked to
the same Identity.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import TestDB
from zondarr.media.registry import ClientRegistry
from zondarr.media.types import ExternalUser
from zondarr.models import Invitation
from zondarr.models.media_server import MediaServer
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.invitation import InvitationRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.invitation import InvitationService
from zondarr.services.redemption import RedemptionService
from zondarr.services.user import UserService

# =============================================================================
# Custom Strategies
# =============================================================================

# Use UUIDs for codes to ensure uniqueness across Hypothesis examples
code_strategy = st.uuids().map(lambda u: str(u).replace("-", "")[:12].upper())

# Username strategy - valid usernames for media servers
username_strategy = st.text(
    alphabet=st.characters(categories=("Ll",)),  # Lowercase letters only
    min_size=3,
    max_size=20,
).filter(lambda x: x.isalpha() and len(x) >= 3)

# Password strategy - valid passwords
password_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=8,
    max_size=32,
).filter(lambda x: len(x) >= 8)

# Email strategy - optional valid emails
email_strategy = st.one_of(
    st.none(),
    st.emails().map(lambda e: e[:255] if len(e) > 255 else e),
)

# Server name strategy
server_name_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=1,
    max_size=50,
).filter(lambda x: x.strip())


# =============================================================================
# Helper Functions
# =============================================================================


def create_mock_client(
    external_user_id: str,
    username: str,
    email: str | None = None,
) -> AsyncMock:
    """Create a mock media client that returns predictable ExternalUser."""
    mock_client = AsyncMock()
    mock_client.create_user = AsyncMock(
        return_value=ExternalUser(
            external_user_id=external_user_id,
            username=username,
            email=email,
        )
    )
    mock_client.set_library_access = AsyncMock(return_value=True)
    mock_client.update_permissions = AsyncMock(return_value=True)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


async def create_media_servers(
    session: async_sessionmaker[AsyncSession],
    count: int,
) -> list[MediaServer]:
    """Create test media servers in the database."""
    servers: list[MediaServer] = []
    async with session() as sess:
        for i in range(count):
            server = MediaServer(
                name=f"TestServer{i}",
                server_type="jellyfin",
                url=f"http://server{i}.local:8096",
                api_key=f"test-api-key-{i}",
                enabled=True,
            )
            sess.add(server)
            servers.append(server)
        await sess.commit()
    return servers


async def create_invitation_with_servers(
    session: async_sessionmaker[AsyncSession],
    code: str,
    servers: list[MediaServer],
) -> Invitation:
    """Create a valid invitation targeting the given servers.

    Note: We set expires_at to None (never expires) to avoid timezone
    comparison issues between SQLite (naive) and Python (aware) datetimes.
    The property tests focus on user creation, not expiration validation.
    """
    async with session() as sess:
        invitation = Invitation(
            code=code,
            enabled=True,
            expires_at=None,  # Never expires - avoids timezone issues
            max_uses=100,  # High limit to avoid exhaustion
            use_count=0,
        )
        invitation.target_servers = servers
        sess.add(invitation)
        await sess.commit()
    return invitation


# =============================================================================
# Property 15: Redemption Creates Users on All Target Servers
# =============================================================================


class TestRedemptionCreatesUsersOnAllServers:
    """Property 15: Redemption Creates Users on All Target Servers.

    For any valid invitation with N target servers, successful redemption
    should create exactly N User records, one for each target server,
    all linked to the same Identity.
    """

    @given(
        num_servers=st.integers(min_value=1, max_value=5),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
        email=email_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_redemption_creates_n_users_for_n_servers(
        self,
        db: TestDB,
        num_servers: int,
        code: str,
        username: str,
        password: str,
        email: str | None,
    ) -> None:
        """For N target servers, exactly N User records are created.

        Property: For any invitation with N target servers (N >= 1),
        successful redemption creates exactly N User records.
        """
        await db.clean()
        session_factory = db.session_factory

        # Create test media servers
        servers = await create_media_servers(session_factory, num_servers)

        # Create invitation targeting all servers
        _invitation = await create_invitation_with_servers(
            session_factory, code, servers
        )

        # Create mock registry that returns mock clients for each server
        mock_registry = MagicMock(spec=ClientRegistry)
        server_to_external_id: dict[UUID, str] = {}

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            external_id = str(uuid4())
            server_to_external_id[server.id] = external_id
            return create_mock_client(external_id, username, email)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Create services with real repositories
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            # Patch the registry in the redemption module
            with patch("zondarr.services.redemption.registry", mock_registry):
                # Execute redemption
                identity, users = await redemption_service.redeem(
                    code,
                    username=username,
                    password=password,
                    email=email,
                )

            await session.commit()

            # PROPERTY ASSERTION 1: Exactly N users created for N servers
            assert len(users) == num_servers, (
                f"Expected {num_servers} users, got {len(users)}"
            )

            # PROPERTY ASSERTION 2: Each user is linked to a different server
            user_server_ids = {user.media_server_id for user in users}
            expected_server_ids = {server.id for server in servers}
            assert user_server_ids == expected_server_ids, (
                f"User server IDs {user_server_ids} don't match "
                f"expected {expected_server_ids}"
            )

            # PROPERTY ASSERTION 3: All users are linked to the same Identity
            user_identity_ids = {user.identity_id for user in users}
            assert len(user_identity_ids) == 1, (
                f"Users should all have same identity, got {user_identity_ids}"
            )
            assert identity.id in user_identity_ids, (
                f"Users should be linked to returned identity {identity.id}"
            )

    @given(
        num_servers=st.integers(min_value=1, max_value=5),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_each_user_has_correct_external_user_id(
        self,
        db: TestDB,
        num_servers: int,
        code: str,
        username: str,
        password: str,
    ) -> None:
        """Each User record has the external_user_id from its media server.

        Property: For each target server, the created User record contains
        the external_user_id returned by that server's create_user call.
        """
        await db.clean()
        session_factory = db.session_factory

        # Create test media servers
        servers = await create_media_servers(session_factory, num_servers)

        # Create invitation targeting all servers
        _invitation = await create_invitation_with_servers(
            session_factory, code, servers
        )

        # Track external IDs per server URL
        url_to_external_id: dict[str, str] = {}
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(
            server: MediaServer,
            /,
        ) -> AsyncMock:
            external_id = str(uuid4())
            url_to_external_id[server.url] = external_id
            return create_mock_client(external_id, username, None)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                _identity, users = await redemption_service.redeem(
                    code,
                    username=username,
                    password=password,
                )

            await session.commit()

            # PROPERTY ASSERTION: Each user's external_user_id matches
            # what was returned by the mock client for that server
            for user in users:
                # Find the server for this user
                server = next(s for s in servers if s.id == user.media_server_id)
                expected_external_id = url_to_external_id[server.url]
                assert user.external_user_id == expected_external_id, (
                    f"User external_user_id {user.external_user_id} doesn't match "
                    f"expected {expected_external_id} for server {server.name}"
                )

    @given(
        num_servers=st.integers(min_value=2, max_value=5),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_all_users_share_same_invitation_id(
        self,
        db: TestDB,
        num_servers: int,
        code: str,
        username: str,
        password: str,
    ) -> None:
        """All created User records reference the same invitation.

        Property: For any redemption, all created User records have
        the same invitation_id pointing to the redeemed invitation.
        """
        await db.clean()
        session_factory = db.session_factory

        # Create test media servers
        servers = await create_media_servers(session_factory, num_servers)

        # Create invitation targeting all servers
        invitation = await create_invitation_with_servers(
            session_factory, code, servers
        )
        invitation_id = invitation.id

        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server  # Unused but required by interface
            return create_mock_client(str(uuid4()), username, None)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                _identity, users = await redemption_service.redeem(
                    code,
                    username=username,
                    password=password,
                )

            await session.commit()

            # PROPERTY ASSERTION: All users have the same invitation_id
            user_invitation_ids = {user.invitation_id for user in users}
            assert len(user_invitation_ids) == 1, (
                f"All users should have same invitation_id, got {user_invitation_ids}"
            )
            assert invitation_id in user_invitation_ids, (
                f"Users should reference invitation {invitation_id}"
            )

    @given(
        num_servers=st.integers(min_value=1, max_value=5),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_identity_has_correct_display_name(
        self,
        db: TestDB,
        num_servers: int,
        code: str,
        username: str,
        password: str,
    ) -> None:
        """Created Identity has display_name matching the username.

        Property: The Identity created during redemption has display_name
        equal to the username provided in the redemption request.
        """
        await db.clean()
        session_factory = db.session_factory

        # Create test media servers
        servers = await create_media_servers(session_factory, num_servers)

        # Create invitation targeting all servers
        _ = await create_invitation_with_servers(session_factory, code, servers)

        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server  # Unused but required by interface
            return create_mock_client(str(uuid4()), username, None)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                identity, _users = await redemption_service.redeem(
                    code,
                    username=username,
                    password=password,
                )

            await session.commit()

            # PROPERTY ASSERTION: Identity display_name matches username
            assert identity.display_name == username, (
                f"Identity display_name '{identity.display_name}' "
                f"should match username '{username}'"
            )


# =============================================================================
# Property 16: Redemption Increments Use Count
# =============================================================================


class TestRedemptionIncrementsUseCount:
    """Property 16: Redemption Increments Use Count.

    For any successful redemption of an invitation with use_count U,
    the invitation's use_count should become U + 1.
    """

    @given(
        initial_use_count=st.integers(min_value=0, max_value=50),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
        email=email_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_use_count_increments_by_one(
        self,
        db: TestDB,
        initial_use_count: int,
        code: str,
        username: str,
        password: str,
        email: str | None,
    ) -> None:
        """After successful redemption, use_count increases by exactly 1.

        Property: For any invitation with use_count U, after successful
        redemption the use_count should be U + 1.
        """
        await db.clean()
        session_factory = db.session_factory

        # Create a single test media server
        servers = await create_media_servers(session_factory, 1)

        # Create invitation with specific initial use_count
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,  # Never expires
                max_uses=100,  # High limit to avoid exhaustion
                use_count=initial_use_count,
            )
            invitation.target_servers = servers
            sess.add(invitation)
            await sess.commit()
            await sess.refresh(invitation)
            invitation_id = invitation.id

        # Verify initial use_count
        async with session_factory() as sess:
            invitation_repo = InvitationRepository(sess)
            invitation_before = await invitation_repo.get_by_id(invitation_id)
            assert invitation_before is not None
            assert invitation_before.use_count == initial_use_count

        # Create mock registry
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server  # Unused but required by interface
            return create_mock_client(str(uuid4()), username, email)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                _identity, _users = await redemption_service.redeem(
                    code,
                    username=username,
                    password=password,
                    email=email,
                )

            await session.commit()

        # PROPERTY ASSERTION: use_count should be initial + 1
        async with session_factory() as sess:
            invitation_repo = InvitationRepository(sess)
            invitation_after = await invitation_repo.get_by_id(invitation_id)
            assert invitation_after is not None
            assert invitation_after.use_count == initial_use_count + 1, (
                f"Expected use_count to be {initial_use_count + 1}, "
                f"got {invitation_after.use_count}"
            )

    @given(
        num_redemptions=st.integers(min_value=1, max_value=5),
        code=code_strategy,
        base_username=username_strategy,
        password=password_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_multiple_redemptions_increment_correctly(
        self,
        db: TestDB,
        num_redemptions: int,
        code: str,
        base_username: str,
        password: str,
    ) -> None:
        """Multiple redemptions increment use_count by the number of redemptions.

        Property: For N successful redemptions, the use_count should
        increase by exactly N.
        """
        await db.clean()
        session_factory = db.session_factory

        # Create a single test media server
        servers = await create_media_servers(session_factory, 1)

        # Create invitation with use_count = 0
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,  # Never expires
                max_uses=100,  # High limit to allow multiple redemptions
                use_count=0,
            )
            invitation.target_servers = servers
            sess.add(invitation)
            await sess.commit()
            await sess.refresh(invitation)
            invitation_id = invitation.id

        # Create mock registry
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server  # Unused but required by interface
            return create_mock_client(str(uuid4()), base_username, None)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute N redemptions with unique usernames
        for i in range(num_redemptions):
            # Generate unique username for each redemption
            unique_username = f"{base_username}{i}"

            async with session_factory() as session:
                invitation_repo = InvitationRepository(session)
                user_repo = UserRepository(session)
                identity_repo = IdentityRepository(session)

                invitation_service = InvitationService(invitation_repo)
                user_service = UserService(user_repo, identity_repo)
                redemption_service = RedemptionService(invitation_service, user_service)

                with patch("zondarr.services.redemption.registry", mock_registry):
                    _identity, _users = await redemption_service.redeem(
                        code,
                        username=unique_username,
                        password=password,
                    )

                await session.commit()

        # PROPERTY ASSERTION: use_count should equal num_redemptions
        async with session_factory() as sess:
            invitation_repo = InvitationRepository(sess)
            invitation_after = await invitation_repo.get_by_id(invitation_id)
            assert invitation_after is not None
            assert invitation_after.use_count == num_redemptions, (
                f"Expected use_count to be {num_redemptions} after "
                f"{num_redemptions} redemptions, got {invitation_after.use_count}"
            )

    @given(
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_use_count_before_plus_one_equals_after(
        self,
        db: TestDB,
        code: str,
        username: str,
        password: str,
    ) -> None:
        """The use_count before redemption + 1 equals use_count after redemption.

        Property: For any successful redemption, the invariant
        use_count_before + 1 == use_count_after holds.
        """
        await db.clean()
        session_factory = db.session_factory

        # Create a single test media server
        servers = await create_media_servers(session_factory, 1)

        # Create invitation
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,  # Never expires
                max_uses=100,  # High limit
                use_count=0,
            )
            invitation.target_servers = servers
            sess.add(invitation)
            await sess.commit()
            await sess.refresh(invitation)
            invitation_id = invitation.id

        # Capture use_count before redemption
        async with session_factory() as sess:
            invitation_repo = InvitationRepository(sess)
            invitation_before = await invitation_repo.get_by_id(invitation_id)
            assert invitation_before is not None
            use_count_before = invitation_before.use_count

        # Create mock registry
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server  # Unused but required by interface
            return create_mock_client(str(uuid4()), username, None)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                _identity, _users = await redemption_service.redeem(
                    code,
                    username=username,
                    password=password,
                )

            await session.commit()

        # Capture use_count after redemption
        async with session_factory() as sess:
            invitation_repo = InvitationRepository(sess)
            invitation_after = await invitation_repo.get_by_id(invitation_id)
            assert invitation_after is not None
            use_count_after = invitation_after.use_count

        # PROPERTY ASSERTION: use_count_before + 1 == use_count_after
        assert use_count_before + 1 == use_count_after, (
            f"Invariant violated: {use_count_before} + 1 != {use_count_after}"
        )


# =============================================================================
# Property 17: Duration Days Sets Expiration
# =============================================================================


class TestDurationDaysSetsExpiration:
    """Property 17: Duration Days Sets Expiration.

    For any invitation with duration_days D, successful redemption should
    create an Identity and Users with expires_at equal to (now + D days).
    When duration_days is None, expires_at should be None.
    """

    @given(
        duration_days=st.integers(min_value=1, max_value=365),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
        email=email_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_duration_days_sets_expires_at_on_identity(
        self,
        db: TestDB,
        duration_days: int,
        code: str,
        username: str,
        password: str,
        email: str | None,
    ) -> None:
        """When duration_days is set, Identity has expires_at set correctly.

        Property: For any invitation with duration_days D, the created
        Identity should have expires_at approximately equal to now + D days.
        """
        from datetime import UTC, datetime, timedelta

        await db.clean()
        session_factory = db.session_factory

        # Create a single test media server
        servers = await create_media_servers(session_factory, 1)

        # Create invitation with duration_days set
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,  # Never expires
                max_uses=100,
                use_count=0,
                duration_days=duration_days,
            )
            invitation.target_servers = servers
            sess.add(invitation)
            await sess.commit()

        # Create mock registry
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server  # Unused but required by interface
            return create_mock_client(str(uuid4()), username, email)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Capture time before redemption
        time_before = datetime.now(UTC)

        # Execute redemption
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                identity, _users = await redemption_service.redeem(
                    code,
                    username=username,
                    password=password,
                    email=email,
                )

            await session.commit()

            # Capture time after redemption
            time_after = datetime.now(UTC)

            # PROPERTY ASSERTION: Identity has expires_at set
            assert identity.expires_at is not None, (
                f"Identity expires_at should be set when duration_days={duration_days}"
            )

            # Calculate expected expiration range
            expected_min = time_before + timedelta(days=duration_days)
            expected_max = time_after + timedelta(days=duration_days)

            # PROPERTY ASSERTION: expires_at is within expected range
            assert expected_min <= identity.expires_at <= expected_max, (
                f"Identity expires_at {identity.expires_at} should be between "
                f"{expected_min} and {expected_max} for duration_days={duration_days}"
            )

    @given(
        duration_days=st.integers(min_value=1, max_value=365),
        num_servers=st.integers(min_value=1, max_value=3),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_duration_days_sets_expires_at_on_all_users(
        self,
        db: TestDB,
        duration_days: int,
        num_servers: int,
        code: str,
        username: str,
        password: str,
    ) -> None:
        """When duration_days is set, all User records have expires_at set.

        Property: For any invitation with duration_days D and N target servers,
        all N created User records should have expires_at approximately equal
        to now + D days.
        """
        from datetime import UTC, datetime, timedelta

        await db.clean()
        session_factory = db.session_factory

        # Create test media servers
        servers = await create_media_servers(session_factory, num_servers)

        # Create invitation with duration_days set
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,
                max_uses=100,
                use_count=0,
                duration_days=duration_days,
            )
            invitation.target_servers = servers
            sess.add(invitation)
            await sess.commit()

        # Create mock registry
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server
            return create_mock_client(str(uuid4()), username, None)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Capture time before redemption
        time_before = datetime.now(UTC)

        # Execute redemption
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                _identity, users = await redemption_service.redeem(
                    code,
                    username=username,
                    password=password,
                )

            await session.commit()

            # Capture time after redemption
            time_after = datetime.now(UTC)

            # Calculate expected expiration range
            expected_min = time_before + timedelta(days=duration_days)
            expected_max = time_after + timedelta(days=duration_days)

            # PROPERTY ASSERTION: All users have expires_at set
            for user in users:
                assert user.expires_at is not None, (
                    f"User {user.id} expires_at should be set when "
                    f"duration_days={duration_days}"
                )

                # PROPERTY ASSERTION: expires_at is within expected range
                assert expected_min <= user.expires_at <= expected_max, (
                    f"User {user.id} expires_at {user.expires_at} should be "
                    f"between {expected_min} and {expected_max}"
                )

    @given(
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
        email=email_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_no_duration_days_means_no_expires_at_on_identity(
        self,
        db: TestDB,
        code: str,
        username: str,
        password: str,
        email: str | None,
    ) -> None:
        """When duration_days is None, Identity has expires_at as None.

        Property: For any invitation with duration_days=None, the created
        Identity should have expires_at=None.
        """
        await db.clean()
        session_factory = db.session_factory

        # Create a single test media server
        servers = await create_media_servers(session_factory, 1)

        # Create invitation WITHOUT duration_days
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,
                max_uses=100,
                use_count=0,
                duration_days=None,  # Explicitly None
            )
            invitation.target_servers = servers
            sess.add(invitation)
            await sess.commit()

        # Create mock registry
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server
            return create_mock_client(str(uuid4()), username, email)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                identity, _users = await redemption_service.redeem(
                    code,
                    username=username,
                    password=password,
                    email=email,
                )

            await session.commit()

            # PROPERTY ASSERTION: Identity has expires_at as None
            assert identity.expires_at is None, (
                f"Identity expires_at should be None when duration_days is None, "
                f"got {identity.expires_at}"
            )

    @given(
        num_servers=st.integers(min_value=1, max_value=3),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_no_duration_days_means_no_expires_at_on_users(
        self,
        db: TestDB,
        num_servers: int,
        code: str,
        username: str,
        password: str,
    ) -> None:
        """When duration_days is None, all User records have expires_at as None.

        Property: For any invitation with duration_days=None and N target servers,
        all N created User records should have expires_at=None.
        """
        await db.clean()
        session_factory = db.session_factory

        # Create test media servers
        servers = await create_media_servers(session_factory, num_servers)

        # Create invitation WITHOUT duration_days
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,
                max_uses=100,
                use_count=0,
                duration_days=None,  # Explicitly None
            )
            invitation.target_servers = servers
            sess.add(invitation)
            await sess.commit()

        # Create mock registry
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server
            return create_mock_client(str(uuid4()), username, None)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                _identity, users = await redemption_service.redeem(
                    code,
                    username=username,
                    password=password,
                )

            await session.commit()

            # PROPERTY ASSERTION: All users have expires_at as None
            for user in users:
                assert user.expires_at is None, (
                    f"User {user.id} expires_at should be None when "
                    f"duration_days is None, got {user.expires_at}"
                )

    @given(
        duration_days=st.integers(min_value=1, max_value=365),
        num_servers=st.integers(min_value=1, max_value=3),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_identity_and_users_have_same_expires_at(
        self,
        db: TestDB,
        duration_days: int,
        num_servers: int,
        code: str,
        username: str,
        password: str,
    ) -> None:
        """Identity and all Users have the same expires_at value.

        Property: For any invitation with duration_days D, the created
        Identity and all User records should have the same expires_at value.
        """
        await db.clean()
        session_factory = db.session_factory

        # Create test media servers
        servers = await create_media_servers(session_factory, num_servers)

        # Create invitation with duration_days set
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,
                max_uses=100,
                use_count=0,
                duration_days=duration_days,
            )
            invitation.target_servers = servers
            sess.add(invitation)
            await sess.commit()

        # Create mock registry
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server
            return create_mock_client(str(uuid4()), username, None)

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                identity, users = await redemption_service.redeem(
                    code,
                    username=username,
                    password=password,
                )

            await session.commit()

            # PROPERTY ASSERTION: Identity and all users have same expires_at
            identity_expires_at = identity.expires_at
            assert identity_expires_at is not None

            for user in users:
                assert user.expires_at == identity_expires_at, (
                    f"User {user.id} expires_at {user.expires_at} should match "
                    f"Identity expires_at {identity_expires_at}"
                )


# =============================================================================
# Property 18: Rollback on Failure
# =============================================================================


class TestRollbackOnFailure:
    """Property 18: Rollback on Failure.

    For any redemption that fails after creating users on some servers:
    - All created users should be deleted from their respective servers
    - No local Identity or User records should exist
    - The invitation use_count should remain unchanged
    """

    @given(
        num_servers=st.integers(min_value=2, max_value=5),
        fail_at_server=st.integers(min_value=1, max_value=4),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
        email=email_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_rollback_deletes_created_users_on_failure(
        self,
        db: TestDB,
        num_servers: int,
        fail_at_server: int,
        code: str,
        username: str,
        password: str,
        email: str | None,
    ) -> None:
        """When creation fails on server N, users on servers 1..N-1 are deleted.

        Property: For any redemption that fails on server N (N > 1),
        all users created on servers 1 through N-1 should be deleted
        via delete_user calls.
        """
        from zondarr.core.exceptions import ValidationError
        from zondarr.media.exceptions import MediaClientError

        # Ensure fail_at_server is within bounds
        fail_at_server = min(fail_at_server, num_servers - 1)
        if fail_at_server < 1:
            fail_at_server = 1

        await db.clean()
        session_factory = db.session_factory

        # Create test media servers
        servers = await create_media_servers(session_factory, num_servers)

        # Create invitation targeting all servers
        _invitation = await create_invitation_with_servers(
            session_factory, code, servers
        )

        # Track which users were created and deleted
        created_user_ids: list[str] = []
        deleted_user_ids: list[str] = []
        create_call_count = 0

        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server  # Unused but required by interface

            mock_client = AsyncMock()

            # Track the external_user_id for this server
            external_id = str(uuid4())

            async def mock_create_user(
                uname: str,
                _pwd: str,
                /,
                *,
                email: str | None = None,
                auth_token: str | None = None,
            ) -> ExternalUser:
                _ = auth_token
                nonlocal create_call_count
                create_call_count += 1

                # Fail on the Nth call (1-indexed fail_at_server)
                if create_call_count == fail_at_server + 1:
                    raise MediaClientError(
                        "Simulated failure",
                        operation="create_user",
                    )

                created_user_ids.append(external_id)
                return ExternalUser(
                    external_user_id=external_id,
                    username=uname,
                    email=email,
                )

            async def mock_delete_user(ext_user_id: str, /) -> bool:
                deleted_user_ids.append(ext_user_id)
                return True

            mock_client.create_user = mock_create_user
            mock_client.delete_user = mock_delete_user
            mock_client.set_library_access = AsyncMock(return_value=True)
            mock_client.update_permissions = AsyncMock(return_value=True)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            return mock_client

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption - should fail
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                with pytest.raises(ValidationError):
                    _ = await redemption_service.redeem(
                        code,
                        username=username,
                        password=password,
                        email=email,
                    )

        # PROPERTY ASSERTION: All created users should be deleted
        assert set(deleted_user_ids) == set(created_user_ids), (
            f"Created users {created_user_ids} should all be deleted, "
            f"but only {deleted_user_ids} were deleted"
        )

        # PROPERTY ASSERTION: Number of created users equals fail_at_server
        assert len(created_user_ids) == fail_at_server, (
            f"Expected {fail_at_server} users to be created before failure, "
            f"got {len(created_user_ids)}"
        )

    @given(
        num_servers=st.integers(min_value=2, max_value=5),
        fail_at_server=st.integers(min_value=1, max_value=4),
        initial_use_count=st.integers(min_value=0, max_value=50),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_use_count_not_incremented_on_failure(
        self,
        db: TestDB,
        num_servers: int,
        fail_at_server: int,
        initial_use_count: int,
        code: str,
        username: str,
        password: str,
    ) -> None:
        """When redemption fails, use_count remains unchanged.

        Property: For any redemption that fails, the invitation's use_count
        should remain at its original value.
        """
        from zondarr.core.exceptions import ValidationError
        from zondarr.media.exceptions import MediaClientError

        # Ensure fail_at_server is within bounds
        fail_at_server = min(fail_at_server, num_servers - 1)
        if fail_at_server < 1:
            fail_at_server = 1

        await db.clean()
        session_factory = db.session_factory

        # Create test media servers
        servers = await create_media_servers(session_factory, num_servers)

        # Create invitation with specific initial use_count
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,
                max_uses=100,
                use_count=initial_use_count,
            )
            invitation.target_servers = servers
            sess.add(invitation)
            await sess.commit()
            await sess.refresh(invitation)
            invitation_id = invitation.id

        create_call_count = 0
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server

            mock_client = AsyncMock()

            async def mock_create_user(
                uname: str,
                _pwd: str,
                /,
                *,
                email: str | None = None,
                auth_token: str | None = None,
            ) -> ExternalUser:
                _ = auth_token
                nonlocal create_call_count
                create_call_count += 1

                # Fail on the Nth call (1-indexed fail_at_server)
                if create_call_count == fail_at_server + 1:
                    raise MediaClientError(
                        "Simulated failure",
                        operation="create_user",
                    )

                return ExternalUser(
                    external_user_id=str(uuid4()),
                    username=uname,
                    email=email,
                )

            mock_client.create_user = mock_create_user
            mock_client.delete_user = AsyncMock(return_value=True)
            mock_client.set_library_access = AsyncMock(return_value=True)
            mock_client.update_permissions = AsyncMock(return_value=True)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            return mock_client

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption - should fail
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                with pytest.raises(ValidationError):
                    _ = await redemption_service.redeem(
                        code,
                        username=username,
                        password=password,
                    )

        # PROPERTY ASSERTION: use_count should remain unchanged
        async with session_factory() as sess:
            invitation_repo = InvitationRepository(sess)
            invitation_after = await invitation_repo.get_by_id(invitation_id)
            assert invitation_after is not None
            assert invitation_after.use_count == initial_use_count, (
                f"use_count should remain {initial_use_count} after failed "
                f"redemption, but got {invitation_after.use_count}"
            )

    @given(
        num_servers=st.integers(min_value=2, max_value=5),
        fail_at_server=st.integers(min_value=1, max_value=4),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
        email=email_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_no_local_records_created_on_failure(
        self,
        db: TestDB,
        num_servers: int,
        fail_at_server: int,
        code: str,
        username: str,
        password: str,
        email: str | None,
    ) -> None:
        """When redemption fails, no local Identity or User records are created.

        Property: For any redemption that fails, no Identity or User records
        should exist in the database for this redemption attempt.
        """
        from sqlalchemy import func, select

        from zondarr.core.exceptions import ValidationError
        from zondarr.media.exceptions import MediaClientError
        from zondarr.models.identity import Identity as IdentityModel
        from zondarr.models.identity import User as UserModel

        # Ensure fail_at_server is within bounds
        fail_at_server = min(fail_at_server, num_servers - 1)
        if fail_at_server < 1:
            fail_at_server = 1

        await db.clean()
        session_factory = db.session_factory

        # Create test media servers
        servers = await create_media_servers(session_factory, num_servers)

        # Create invitation targeting all servers
        _invitation = await create_invitation_with_servers(
            session_factory, code, servers
        )

        # Count existing records before redemption attempt
        async with session_factory() as sess:
            identity_count_before = await sess.scalar(
                select(func.count()).select_from(IdentityModel)
            )
            user_count_before = await sess.scalar(
                select(func.count()).select_from(UserModel)
            )

        create_call_count = 0
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server

            mock_client = AsyncMock()

            async def mock_create_user(
                uname: str,
                _pwd: str,
                /,
                *,
                email: str | None = None,
                auth_token: str | None = None,
            ) -> ExternalUser:
                _ = auth_token
                nonlocal create_call_count
                create_call_count += 1

                # Fail on the Nth call (1-indexed fail_at_server)
                if create_call_count == fail_at_server + 1:
                    raise MediaClientError(
                        "Simulated failure",
                        operation="create_user",
                    )

                return ExternalUser(
                    external_user_id=str(uuid4()),
                    username=uname,
                    email=email,
                )

            mock_client.create_user = mock_create_user
            mock_client.delete_user = AsyncMock(return_value=True)
            mock_client.set_library_access = AsyncMock(return_value=True)
            mock_client.update_permissions = AsyncMock(return_value=True)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            return mock_client

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption - should fail
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                with pytest.raises(ValidationError):
                    _ = await redemption_service.redeem(
                        code,
                        username=username,
                        password=password,
                        email=email,
                    )

        # PROPERTY ASSERTION: No new Identity records created
        async with session_factory() as sess:
            identity_count_after = await sess.scalar(
                select(func.count()).select_from(IdentityModel)
            )
            assert identity_count_after == identity_count_before, (
                f"No new Identity records should be created on failure. "
                f"Before: {identity_count_before}, After: {identity_count_after}"
            )

        # PROPERTY ASSERTION: No new User records created
        async with session_factory() as sess:
            user_count_after = await sess.scalar(
                select(func.count()).select_from(UserModel)
            )
            assert user_count_after == user_count_before, (
                f"No new User records should be created on failure. "
                f"Before: {user_count_before}, After: {user_count_after}"
            )

    @given(
        num_servers=st.integers(min_value=2, max_value=4),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_rollback_on_first_server_failure(
        self,
        db: TestDB,
        num_servers: int,
        code: str,
        username: str,
        password: str,
    ) -> None:
        """When creation fails on the first server, no users need rollback.

        Property: When the first server fails, no users have been created
        yet, so no rollback deletions should occur, and no local records
        should be created.
        """
        from sqlalchemy import func, select

        from zondarr.core.exceptions import ValidationError
        from zondarr.media.exceptions import MediaClientError
        from zondarr.models.identity import Identity as IdentityModel
        from zondarr.models.identity import User as UserModel

        await db.clean()
        session_factory = db.session_factory

        # Create test media servers
        servers = await create_media_servers(session_factory, num_servers)

        # Create invitation with initial use_count
        initial_use_count = 5
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,
                max_uses=100,
                use_count=initial_use_count,
            )
            invitation.target_servers = servers
            sess.add(invitation)
            await sess.commit()
            await sess.refresh(invitation)
            invitation_id = invitation.id

        # Count existing records before redemption attempt
        async with session_factory() as sess:
            identity_count_before = await sess.scalar(
                select(func.count()).select_from(IdentityModel)
            )
            user_count_before = await sess.scalar(
                select(func.count()).select_from(UserModel)
            )

        delete_calls: list[str] = []
        create_call_count = 0
        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            del server

            mock_client = AsyncMock()

            async def mock_create_user(
                uname: str,
                _pwd: str,
                /,
                *,
                email: str | None = None,
                auth_token: str | None = None,
            ) -> ExternalUser:
                _ = auth_token
                nonlocal create_call_count
                create_call_count += 1

                # Fail on the first call
                if create_call_count == 1:
                    raise MediaClientError(
                        "First server failure",
                        operation="create_user",
                    )

                return ExternalUser(
                    external_user_id=str(uuid4()),
                    username=uname,
                    email=email,
                )

            async def mock_delete_user(ext_user_id: str, /) -> bool:
                delete_calls.append(ext_user_id)
                return True

            mock_client.create_user = mock_create_user
            mock_client.delete_user = mock_delete_user
            mock_client.set_library_access = AsyncMock(return_value=True)
            mock_client.update_permissions = AsyncMock(return_value=True)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            return mock_client

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption - should fail on first server
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                with pytest.raises(ValidationError):
                    _ = await redemption_service.redeem(
                        code,
                        username=username,
                        password=password,
                    )

        # PROPERTY ASSERTION: No delete calls should have been made
        assert len(delete_calls) == 0, (
            f"No delete calls should be made when first server fails, "
            f"but got {len(delete_calls)} calls"
        )

        # PROPERTY ASSERTION: use_count unchanged
        async with session_factory() as sess:
            invitation_repo = InvitationRepository(sess)
            invitation_after = await invitation_repo.get_by_id(invitation_id)
            assert invitation_after is not None
            assert invitation_after.use_count == initial_use_count

        # PROPERTY ASSERTION: No new local records
        async with session_factory() as sess:
            identity_count_after = await sess.scalar(
                select(func.count()).select_from(IdentityModel)
            )
            user_count_after = await sess.scalar(
                select(func.count()).select_from(UserModel)
            )
            assert identity_count_after == identity_count_before
            assert user_count_after == user_count_before


# =============================================================================
# Property 13: Redemption Rollback on Failure (Plex)
# =============================================================================


class TestPlexRedemptionRollbackOnFailure:
    """Property 13: Redemption Rollback on Failure (Plex).

    For any invitation targeting multiple servers where user creation succeeds
    on some servers but fails on a Plex server, all previously created users
    should be deleted and no local Identity/User records should be created.
    """

    @given(
        num_jellyfin_servers=st.integers(min_value=1, max_value=3),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
        email=email_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_plex_failure_triggers_rollback_of_created_users(
        self,
        db: TestDB,
        num_jellyfin_servers: int,
        code: str,
        username: str,
        password: str,
        email: str | None,
    ) -> None:
        """When Plex creation fails, all previously created users are deleted.

        Property: For any redemption with N Jellyfin servers and 1 Plex server,
        if user creation fails on the Plex server, all users created before
        the failure should be deleted via delete_user calls.

        Note: The order of server processing is not guaranteed, so we verify
        that all created users are deleted, regardless of how many were created
        before the Plex failure.
        """
        from zondarr.core.exceptions import ValidationError
        from zondarr.media.exceptions import MediaClientError

        await db.clean()
        session_factory = db.session_factory

        # Create Jellyfin servers
        jellyfin_servers: list[MediaServer] = []
        async with session_factory() as sess:
            for i in range(num_jellyfin_servers):
                server = MediaServer(
                    name=f"JellyfinServer{i}",
                    server_type="jellyfin",
                    url=f"http://jellyfin{i}.local:8096",
                    api_key=f"jellyfin-api-key-{i}",
                    enabled=True,
                )
                sess.add(server)
                jellyfin_servers.append(server)
            await sess.commit()
            for server in jellyfin_servers:
                await sess.refresh(server)

        # Create Plex server (will fail)
        async with session_factory() as sess:
            plex_server = MediaServer(
                name="PlexServer",
                server_type="plex",
                url="http://plex.local:32400",
                api_key="plex-api-key",
                enabled=True,
            )
            sess.add(plex_server)
            await sess.commit()
            await sess.refresh(plex_server)

        # Create invitation targeting all servers
        all_servers = [*jellyfin_servers, plex_server]
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,
                max_uses=100,
                use_count=0,
            )
            invitation.target_servers = all_servers
            sess.add(invitation)
            await sess.commit()

        # Track created and deleted users
        created_user_ids: list[str] = []
        deleted_user_ids: list[str] = []

        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            mock_client = AsyncMock()
            external_id = str(uuid4())

            async def mock_create_user(
                uname: str,
                _pwd: str,
                /,
                *,
                email: str | None = None,
                auth_token: str | None = None,
            ) -> ExternalUser:
                _ = auth_token
                # Fail if this is the Plex server
                if server.server_type == "plex":
                    raise MediaClientError(
                        "Plex server failure",
                        operation="create_user",
                        server_url=server.url,
                    )

                # Success for Jellyfin servers
                created_user_ids.append(external_id)
                return ExternalUser(
                    external_user_id=external_id,
                    username=uname,
                    email=email,
                )

            async def mock_delete_user(ext_user_id: str, /) -> bool:
                deleted_user_ids.append(ext_user_id)
                return True

            mock_client.create_user = mock_create_user
            mock_client.delete_user = mock_delete_user
            mock_client.set_library_access = AsyncMock(return_value=True)
            mock_client.update_permissions = AsyncMock(return_value=True)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            return mock_client

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption - should fail on Plex server
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                with pytest.raises(ValidationError):
                    _ = await redemption_service.redeem(
                        code,
                        username=username,
                        password=password,
                        email=email,
                    )

        # PROPERTY ASSERTION: All created users should be deleted
        # (regardless of how many were created before Plex failure)
        assert set(deleted_user_ids) == set(created_user_ids), (
            f"All created users {created_user_ids} should be deleted, "
            f"but only {deleted_user_ids} were deleted"
        )

        # PROPERTY ASSERTION: Created users count should be between 0 and num_jellyfin_servers
        # (depends on server processing order)
        assert 0 <= len(created_user_ids) <= num_jellyfin_servers, (
            f"Expected 0 to {num_jellyfin_servers} users to be created, "
            f"got {len(created_user_ids)}"
        )

    @given(
        num_jellyfin_servers=st.integers(min_value=1, max_value=2),
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
        email=email_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_no_local_records_on_plex_failure(
        self,
        db: TestDB,
        num_jellyfin_servers: int,
        code: str,
        username: str,
        password: str,
        email: str | None,
    ) -> None:
        """When Plex creation fails, no local Identity or User records are created.

        Property: For any redemption that fails on a Plex server, no Identity
        or User records should exist in the database for this redemption attempt.
        """
        from sqlalchemy import func, select

        from zondarr.core.exceptions import ValidationError
        from zondarr.media.exceptions import MediaClientError
        from zondarr.models.identity import Identity as IdentityModel
        from zondarr.models.identity import User as UserModel

        await db.clean()
        session_factory = db.session_factory

        # Create Jellyfin servers
        jellyfin_servers: list[MediaServer] = []
        async with session_factory() as sess:
            for i in range(num_jellyfin_servers):
                server = MediaServer(
                    name=f"JellyfinServer{i}",
                    server_type="jellyfin",
                    url=f"http://jellyfin{i}.local:8096",
                    api_key=f"jellyfin-api-key-{i}",
                    enabled=True,
                )
                sess.add(server)
                jellyfin_servers.append(server)
            await sess.commit()
            for server in jellyfin_servers:
                await sess.refresh(server)

        # Create Plex server (will fail)
        async with session_factory() as sess:
            plex_server = MediaServer(
                name="PlexServer",
                server_type="plex",
                url="http://plex.local:32400",
                api_key="plex-api-key",
                enabled=True,
            )
            sess.add(plex_server)
            await sess.commit()
            await sess.refresh(plex_server)

        # Create invitation targeting all servers
        all_servers = [*jellyfin_servers, plex_server]
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,
                max_uses=100,
                use_count=0,
            )
            invitation.target_servers = all_servers
            sess.add(invitation)
            await sess.commit()

        # Count existing records before redemption attempt
        async with session_factory() as sess:
            identity_count_before = await sess.scalar(
                select(func.count()).select_from(IdentityModel)
            )
            user_count_before = await sess.scalar(
                select(func.count()).select_from(UserModel)
            )

        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            mock_client = AsyncMock()

            async def mock_create_user(
                uname: str,
                _pwd: str,
                /,
                *,
                email: str | None = None,
                auth_token: str | None = None,
            ) -> ExternalUser:
                _ = auth_token
                # Fail if this is the Plex server
                if server.server_type == "plex":
                    raise MediaClientError(
                        "Plex server failure",
                        operation="create_user",
                        server_url=server.url,
                    )

                return ExternalUser(
                    external_user_id=str(uuid4()),
                    username=uname,
                    email=email,
                )

            mock_client.create_user = mock_create_user
            mock_client.delete_user = AsyncMock(return_value=True)
            mock_client.set_library_access = AsyncMock(return_value=True)
            mock_client.update_permissions = AsyncMock(return_value=True)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            return mock_client

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption - should fail on Plex server
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                with pytest.raises(ValidationError):
                    _ = await redemption_service.redeem(
                        code,
                        username=username,
                        password=password,
                        email=email,
                    )

        # PROPERTY ASSERTION: No new Identity records created
        async with session_factory() as sess:
            identity_count_after = await sess.scalar(
                select(func.count()).select_from(IdentityModel)
            )
            assert identity_count_after == identity_count_before, (
                f"No new Identity records should be created on Plex failure. "
                f"Before: {identity_count_before}, After: {identity_count_after}"
            )

        # PROPERTY ASSERTION: No new User records created
        async with session_factory() as sess:
            user_count_after = await sess.scalar(
                select(func.count()).select_from(UserModel)
            )
            assert user_count_after == user_count_before, (
                f"No new User records should be created on Plex failure. "
                f"Before: {user_count_before}, After: {user_count_after}"
            )

    @given(
        code=code_strategy,
        username=username_strategy,
        password=password_strategy,
        email=email_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_multi_server_rollback_with_plex_and_jellyfin(
        self,
        db: TestDB,
        code: str,
        username: str,
        password: str,
        email: str | None,
    ) -> None:
        """Multi-server rollback works correctly with mixed Plex and Jellyfin servers.

        Property: For any redemption with Jellyfin, Plex, and another Jellyfin
        server where the last server fails, users on all previous servers
        (both Plex and Jellyfin) should be deleted.
        """
        from zondarr.core.exceptions import ValidationError
        from zondarr.media.exceptions import MediaClientError

        await db.clean()
        session_factory = db.session_factory

        # Create servers: Jellyfin -> Plex -> Jellyfin (fails)
        servers: list[MediaServer] = []
        async with session_factory() as sess:
            # First Jellyfin server
            jellyfin1 = MediaServer(
                name="Jellyfin1",
                server_type="jellyfin",
                url="http://jellyfin1.local:8096",
                api_key="jellyfin1-api-key",
                enabled=True,
            )
            sess.add(jellyfin1)
            servers.append(jellyfin1)

            # Plex server
            plex = MediaServer(
                name="Plex",
                server_type="plex",
                url="http://plex.local:32400",
                api_key="plex-api-key",
                enabled=True,
            )
            sess.add(plex)
            servers.append(plex)

            # Second Jellyfin server (will fail)
            jellyfin2 = MediaServer(
                name="Jellyfin2",
                server_type="jellyfin",
                url="http://jellyfin2.local:8096",
                api_key="jellyfin2-api-key",
                enabled=True,
            )
            sess.add(jellyfin2)
            servers.append(jellyfin2)

            await sess.commit()
            for server in servers:
                await sess.refresh(server)

        # Create invitation targeting all servers
        async with session_factory() as sess:
            invitation = Invitation(
                code=code,
                enabled=True,
                expires_at=None,
                max_uses=100,
                use_count=0,
            )
            invitation.target_servers = servers
            sess.add(invitation)
            await sess.commit()

        # Track created and deleted users
        created_user_ids: list[str] = []
        deleted_user_ids: list[str] = []
        create_call_count = 0

        mock_registry = MagicMock(spec=ClientRegistry)

        def create_client_side_effect(server: MediaServer, /) -> AsyncMock:
            mock_client = AsyncMock()
            external_id = str(uuid4())

            async def mock_create_user(
                uname: str,
                _pwd: str,
                /,
                *,
                email: str | None = None,
                auth_token: str | None = None,
            ) -> ExternalUser:
                _ = auth_token
                nonlocal create_call_count

                create_call_count += 1

                # Fail on the third server (Jellyfin2)
                if create_call_count == 3:
                    raise MediaClientError(
                        "Third server failure",
                        operation="create_user",
                        server_url=server.url,
                    )

                created_user_ids.append(external_id)
                return ExternalUser(
                    external_user_id=external_id,
                    username=uname,
                    email=email,
                )

            async def mock_delete_user(ext_user_id: str, /) -> bool:
                deleted_user_ids.append(ext_user_id)
                return True

            mock_client.create_user = mock_create_user
            mock_client.delete_user = mock_delete_user
            mock_client.set_library_access = AsyncMock(return_value=True)
            mock_client.update_permissions = AsyncMock(return_value=True)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            return mock_client

        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )

        # Execute redemption - should fail on third server
        async with session_factory() as session:
            invitation_repo = InvitationRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)

            invitation_service = InvitationService(invitation_repo)
            user_service = UserService(user_repo, identity_repo)
            redemption_service = RedemptionService(invitation_service, user_service)

            with patch("zondarr.services.redemption.registry", mock_registry):
                with pytest.raises(ValidationError):
                    _ = await redemption_service.redeem(
                        code,
                        username=username,
                        password=password,
                        email=email,
                    )

        # PROPERTY ASSERTION: Both Jellyfin1 and Plex users should be deleted
        assert set(deleted_user_ids) == set(created_user_ids), (
            f"All created users {created_user_ids} should be deleted, "
            f"but only {deleted_user_ids} were deleted"
        )

        # PROPERTY ASSERTION: 2 users created (Jellyfin1 + Plex)
        assert len(created_user_ids) == 2, (
            f"Expected 2 users to be created before failure, "
            f"got {len(created_user_ids)}"
        )


# =============================================================================
# Atomic Reservation (reserve_use)
# =============================================================================


class TestAtomicReservation:
    """Tests for InvitationRepository.reserve_use() atomic reservation.

    Verifies that the SQL-level atomic UPDATE correctly handles all
    invitation states: enabled/disabled, expired, max_uses, unlimited.
    """

    @pytest.mark.asyncio
    async def test_reserve_use_returns_true_and_increments(
        self, db: TestDB
    ) -> None:
        """reserve_use returns True and increments use_count when valid."""
        await db.clean()
        session_factory = db.session_factory

        async with session_factory() as sess:
            invitation = Invitation(
                code="RESERVE01TST",
                enabled=True,
                expires_at=None,
                max_uses=5,
                use_count=2,
            )
            sess.add(invitation)
            await sess.commit()
            await sess.refresh(invitation)
            invitation_id = invitation.id

        async with session_factory() as sess:
            repo = InvitationRepository(sess)
            result = await repo.reserve_use("RESERVE01TST")
            await sess.commit()

        assert result is True

        async with session_factory() as sess:
            repo = InvitationRepository(sess)
            inv = await repo.get_by_id(invitation_id)
            assert inv is not None
            assert inv.use_count == 3

    @pytest.mark.asyncio
    async def test_reserve_use_returns_false_at_max_uses(
        self, db: TestDB
    ) -> None:
        """reserve_use returns False when use_count == max_uses."""
        await db.clean()
        session_factory = db.session_factory

        async with session_factory() as sess:
            invitation = Invitation(
                code="RESERVE02TST",
                enabled=True,
                expires_at=None,
                max_uses=3,
                use_count=3,
            )
            sess.add(invitation)
            await sess.commit()
            await sess.refresh(invitation)
            invitation_id = invitation.id

        async with session_factory() as sess:
            repo = InvitationRepository(sess)
            result = await repo.reserve_use("RESERVE02TST")
            await sess.commit()

        assert result is False

        # use_count should remain unchanged
        async with session_factory() as sess:
            repo = InvitationRepository(sess)
            inv = await repo.get_by_id(invitation_id)
            assert inv is not None
            assert inv.use_count == 3

    @pytest.mark.asyncio
    async def test_reserve_use_returns_false_when_disabled(
        self, db: TestDB
    ) -> None:
        """reserve_use returns False when invitation is disabled."""
        await db.clean()
        session_factory = db.session_factory

        async with session_factory() as sess:
            invitation = Invitation(
                code="RESERVE03TST",
                enabled=False,
                expires_at=None,
                max_uses=10,
                use_count=0,
            )
            sess.add(invitation)
            await sess.commit()

        async with session_factory() as sess:
            repo = InvitationRepository(sess)
            result = await repo.reserve_use("RESERVE03TST")
            await sess.commit()

        assert result is False

    @pytest.mark.asyncio
    async def test_reserve_use_returns_false_when_expired(
        self, db: TestDB
    ) -> None:
        """reserve_use returns False when invitation is expired."""
        from datetime import UTC, datetime, timedelta

        await db.clean()
        session_factory = db.session_factory

        async with session_factory() as sess:
            invitation = Invitation(
                code="RESERVE04TST",
                enabled=True,
                expires_at=datetime.now(UTC) - timedelta(hours=1),
                max_uses=10,
                use_count=0,
            )
            sess.add(invitation)
            await sess.commit()

        async with session_factory() as sess:
            repo = InvitationRepository(sess)
            result = await repo.reserve_use("RESERVE04TST")
            await sess.commit()

        assert result is False

    @pytest.mark.asyncio
    async def test_reserve_use_returns_true_when_unlimited(
        self, db: TestDB
    ) -> None:
        """reserve_use returns True when max_uses is None (unlimited)."""
        await db.clean()
        session_factory = db.session_factory

        async with session_factory() as sess:
            invitation = Invitation(
                code="RESERVE05TST",
                enabled=True,
                expires_at=None,
                max_uses=None,
                use_count=999,
            )
            sess.add(invitation)
            await sess.commit()
            await sess.refresh(invitation)
            invitation_id = invitation.id

        async with session_factory() as sess:
            repo = InvitationRepository(sess)
            result = await repo.reserve_use("RESERVE05TST")
            await sess.commit()

        assert result is True

        async with session_factory() as sess:
            repo = InvitationRepository(sess)
            inv = await repo.get_by_id(invitation_id)
            assert inv is not None
            assert inv.use_count == 1000

    @pytest.mark.asyncio
    async def test_reserve_use_returns_false_for_nonexistent_code(
        self, db: TestDB
    ) -> None:
        """reserve_use returns False for a code that doesn't exist."""
        await db.clean()
        session_factory = db.session_factory

        async with session_factory() as sess:
            repo = InvitationRepository(sess)
            result = await repo.reserve_use("DOESNOTEXIST")
            await sess.commit()

        assert result is False
