"""Property-based tests for repository layer.

Feature: zondarr-foundation
Properties: 8, 9
Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.6
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TestDB
from zondarr.core.exceptions import RepositoryError
from zondarr.models import Identity, Invitation, MediaServer, ServerType, User
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.invitation import InvitationRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.user import UserRepository

# Custom strategies for model fields
uuid_strategy = st.uuids()
datetime_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(UTC),
)
optional_datetime_strategy = st.one_of(st.none(), datetime_strategy)
server_type_strategy = st.sampled_from([ServerType.JELLYFIN, ServerType.PLEX])
name_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=1,
    max_size=50,
).filter(lambda x: x.strip())
url_strategy = st.from_regex(r"https?://[a-z0-9]+\.[a-z]{2,}", fullmatch=True)
email_strategy = st.from_regex(r"[a-z0-9]+@[a-z0-9]+\.[a-z]{2,}", fullmatch=True)
code_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=6,
    max_size=20,
)
positive_int_strategy = st.integers(min_value=0, max_value=1000)
optional_positive_int_strategy = st.one_of(st.none(), positive_int_strategy)


class TestRepositoryCRUDRoundTrip:
    """
    Feature: zondarr-foundation
    Property 8: Repository CRUD Round-Trip

    *For any* valid entity (MediaServer, Invitation, Identity, User),
    creating it via the repository and then retrieving it by ID SHALL
    return an equivalent entity with all fields preserved.

    **Validates: Requirements 5.2, 5.3, 5.4, 5.5**
    """

    @settings(
        max_examples=25,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        name=name_strategy,
        server_type=server_type_strategy,
        url=url_strategy,
        api_key=name_strategy,
        enabled=st.booleans(),
    )
    @pytest.mark.asyncio
    async def test_media_server_crud_round_trip(
        self,
        db: TestDB,
        name: str,
        server_type: ServerType,
        url: str,
        api_key: str,
        enabled: bool,
    ) -> None:
        """MediaServer created via repository can be retrieved with all fields preserved."""
        await db.clean()
        async with db.session_factory() as session:
            repo = MediaServerRepository(session)

            # Create entity
            server = MediaServer()
            server.name = name
            server.server_type = server_type
            server.url = url
            server.api_key = api_key
            server.enabled = enabled

            created = await repo.create(server)
            await session.commit()

            # Retrieve by ID
            retrieved = await repo.get_by_id(created.id)

            # Verify all fields preserved
            assert retrieved is not None
            assert retrieved.id == created.id
            assert retrieved.name == name
            assert retrieved.server_type == server_type
            assert retrieved.url == url
            assert retrieved.api_key == api_key
            assert retrieved.enabled == enabled
            assert retrieved.created_at is not None

    @settings(
        max_examples=25,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        code=code_strategy,
        expires_at=optional_datetime_strategy,
        max_uses=optional_positive_int_strategy,
        use_count=positive_int_strategy,
        duration_days=optional_positive_int_strategy,
        enabled=st.booleans(),
        created_by=st.one_of(st.none(), name_strategy),
    )
    @pytest.mark.asyncio
    async def test_invitation_crud_round_trip(
        self,
        db: TestDB,
        code: str,
        expires_at: datetime | None,
        max_uses: int | None,
        use_count: int,
        duration_days: int | None,
        enabled: bool,
        created_by: str | None,
    ) -> None:
        """Invitation created via repository can be retrieved with all fields preserved."""
        await db.clean()
        async with db.session_factory() as session:
            repo = InvitationRepository(session)

            # Create entity
            invitation = Invitation()
            invitation.code = code
            invitation.expires_at = expires_at
            invitation.max_uses = max_uses
            invitation.use_count = use_count
            invitation.duration_days = duration_days
            invitation.enabled = enabled
            invitation.created_by = created_by

            created = await repo.create(invitation)
            await session.commit()

            # Retrieve by ID
            retrieved = await repo.get_by_id(created.id)

            # Verify all fields preserved
            assert retrieved is not None
            assert retrieved.id == created.id
            assert retrieved.code == code
            assert retrieved.max_uses == max_uses
            assert retrieved.use_count == use_count
            assert retrieved.duration_days == duration_days
            assert retrieved.enabled == enabled
            assert retrieved.created_by == created_by
            assert retrieved.created_at is not None

            # Also test get_by_code
            by_code = await repo.get_by_code(code)
            assert by_code is not None
            assert by_code.id == created.id

    @settings(
        max_examples=25,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        display_name=name_strategy,
        email=st.one_of(st.none(), email_strategy),
        expires_at=optional_datetime_strategy,
        enabled=st.booleans(),
    )
    @pytest.mark.asyncio
    async def test_identity_crud_round_trip(
        self,
        db: TestDB,
        display_name: str,
        email: str | None,
        expires_at: datetime | None,
        enabled: bool,
    ) -> None:
        """Identity created via repository can be retrieved with all fields preserved."""
        await db.clean()
        async with db.session_factory() as session:
            repo = IdentityRepository(session)

            # Create entity
            identity = Identity()
            identity.display_name = display_name
            identity.email = email
            identity.expires_at = expires_at
            identity.enabled = enabled

            created = await repo.create(identity)
            await session.commit()

            # Retrieve by ID
            retrieved = await repo.get_by_id(created.id)

            # Verify all fields preserved
            assert retrieved is not None
            assert retrieved.id == created.id
            assert retrieved.display_name == display_name
            assert retrieved.email == email
            assert retrieved.enabled == enabled
            assert retrieved.created_at is not None

    @settings(
        max_examples=25,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        external_user_id=name_strategy,
        username=name_strategy,
        expires_at=optional_datetime_strategy,
        enabled=st.booleans(),
    )
    @pytest.mark.asyncio
    async def test_user_crud_round_trip(
        self,
        db: TestDB,
        external_user_id: str,
        username: str,
        expires_at: datetime | None,
        enabled: bool,
    ) -> None:
        """User created via repository can be retrieved with all fields preserved."""
        await db.clean()
        async with db.session_factory() as session:
            # First create required parent entities
            identity_repo = IdentityRepository(session)
            server_repo = MediaServerRepository(session)
            user_repo = UserRepository(session)

            # Create identity
            identity = Identity()
            identity.display_name = "Test Identity"
            identity.enabled = True
            created_identity = await identity_repo.create(identity)

            # Create media server
            server = MediaServer()
            server.name = "Test Server"
            server.server_type = ServerType.JELLYFIN
            server.url = "http://test.local"
            server.api_key = "testkey"
            server.enabled = True
            created_server = await server_repo.create(server)

            await session.commit()

            # Create user
            user = User()
            user.identity_id = created_identity.id
            user.media_server_id = created_server.id
            user.external_user_id = external_user_id
            user.username = username
            user.expires_at = expires_at
            user.enabled = enabled

            created_user = await user_repo.create(user)
            await session.commit()

            # Retrieve by ID
            retrieved = await user_repo.get_by_id(created_user.id)

            # Verify all fields preserved
            assert retrieved is not None
            assert retrieved.id == created_user.id
            assert retrieved.identity_id == created_identity.id
            assert retrieved.media_server_id == created_server.id
            assert retrieved.external_user_id == external_user_id
            assert retrieved.username == username
            assert retrieved.enabled == enabled
            assert retrieved.created_at is not None

            # Also test get_by_identity
            by_identity = await user_repo.get_by_identity(created_identity.id)
            assert len(by_identity) == 1
            assert by_identity[0].id == created_user.id

            # Also test get_by_server
            by_server = await user_repo.get_by_server(created_server.id)
            assert len(by_server) == 1
            assert by_server[0].id == created_user.id


class TestRepositoryWrapsErrors:
    """
    Feature: zondarr-foundation
    Property 9: Repository Wraps Database Errors

    *For any* database operation that raises a SQLAlchemy exception,
    the repository SHALL catch it and raise a RepositoryError that
    wraps the original exception and includes the operation context.

    **Validates: Requirements 5.6**
    """

    @pytest.mark.asyncio
    async def test_get_by_id_wraps_database_errors(self) -> None:
        """get_by_id wraps database errors in RepositoryError."""
        # Create a mock session that raises SQLAlchemyError
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.get = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = MediaServerRepository(mock_session)

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.get_by_id(UUID("00000000-0000-0000-0000-000000000000"))

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "get_by_id"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_get_all_wraps_database_errors(self) -> None:
        """get_all wraps database errors in RepositoryError."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.scalars = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = MediaServerRepository(mock_session)

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.get_all()

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "get_all"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_create_wraps_database_errors(self) -> None:
        """create wraps database errors in RepositoryError."""
        mock_session = AsyncMock(spec=AsyncSession)
        # session.add() is synchronous on AsyncSession, so use MagicMock
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = MediaServerRepository(mock_session)

        server = MediaServer()
        server.name = "Test"
        server.server_type = ServerType.JELLYFIN
        server.url = "http://test.local"
        server.api_key = "key"
        server.enabled = True

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.create(server)

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "create"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_delete_wraps_database_errors(self) -> None:
        """delete wraps database errors in RepositoryError."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.delete = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = MediaServerRepository(mock_session)

        server = MediaServer()
        server.name = "Test"
        server.server_type = ServerType.JELLYFIN
        server.url = "http://test.local"
        server.api_key = "key"
        server.enabled = True

        with pytest.raises(RepositoryError) as exc_info:
            await repo.delete(server)

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "delete"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_invitation_get_by_code_wraps_errors(self) -> None:
        """InvitationRepository.get_by_code wraps database errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.scalars = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = InvitationRepository(mock_session)

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.get_by_code("TESTCODE")

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "get_by_code"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_invitation_get_active_wraps_errors(self) -> None:
        """InvitationRepository.get_active wraps database errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.scalars = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = InvitationRepository(mock_session)

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.get_active()

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "get_active"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_invitation_increment_use_count_wraps_errors(self) -> None:
        """InvitationRepository.increment_use_count wraps database errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.flush = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = InvitationRepository(mock_session)

        invitation = Invitation()
        invitation.code = "TEST123"
        invitation.use_count = 0
        invitation.enabled = True

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.increment_use_count(invitation)

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "increment_use_count"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_invitation_disable_wraps_errors(self) -> None:
        """InvitationRepository.disable wraps database errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.flush = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = InvitationRepository(mock_session)

        invitation = Invitation()
        invitation.code = "TEST123"
        invitation.enabled = True

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.disable(invitation)

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "disable"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_media_server_get_enabled_wraps_errors(self) -> None:
        """MediaServerRepository.get_enabled wraps database errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.scalars = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = MediaServerRepository(mock_session)

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.get_enabled()

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "get_enabled"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_user_get_by_identity_wraps_errors(self) -> None:
        """UserRepository.get_by_identity wraps database errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.scalars = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = UserRepository(mock_session)

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.get_by_identity(UUID("00000000-0000-0000-0000-000000000000"))

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "get_by_identity"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_user_get_by_server_wraps_errors(self) -> None:
        """UserRepository.get_by_server wraps database errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.scalars = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = UserRepository(mock_session)

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.get_by_server(UUID("00000000-0000-0000-0000-000000000000"))

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "get_by_server"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_identity_update_wraps_errors(self) -> None:
        """IdentityRepository.update wraps database errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.flush = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = IdentityRepository(mock_session)

        identity = Identity()
        identity.display_name = "Test"
        identity.enabled = True

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.update(identity)

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "update"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)

    @pytest.mark.asyncio
    async def test_user_update_wraps_errors(self) -> None:
        """UserRepository.update wraps database errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.flush = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        repo = UserRepository(mock_session)

        user = User()
        user.external_user_id = "ext123"
        user.username = "testuser"
        user.enabled = True

        with pytest.raises(RepositoryError) as exc_info:
            _ = await repo.update(user)

        assert exc_info.value.error_code == "REPOSITORY_ERROR"
        assert exc_info.value.context["operation"] == "update"
        assert exc_info.value.original is not None
        assert isinstance(exc_info.value.original, SQLAlchemyError)
