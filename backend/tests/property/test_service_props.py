"""Property-based tests for service layer.

Feature: zondarr-foundation
Properties: 10, 11
Validates: Requirements 6.3, 6.5, 6.6
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from zondarr.core.exceptions import NotFoundError, ValidationError
from zondarr.media.registry import ClientRegistry
from zondarr.models import Invitation, ServerType
from zondarr.models.base import Base
from zondarr.repositories.invitation import InvitationRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.services.invitation import (
    InvitationService,
    InvitationValidationFailure,
)
from zondarr.services.media_server import MediaServerService

# Custom strategies for model fields
name_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=1,
    max_size=50,
).filter(lambda x: x.strip())
url_strategy = st.from_regex(r"https?://[a-z0-9]+\.[a-z]{2,}", fullmatch=True)
server_type_strategy = st.sampled_from([ServerType.JELLYFIN, ServerType.PLEX])
code_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=6,
    max_size=20,
)
positive_int_strategy = st.integers(min_value=0, max_value=1000)


async def create_test_engine() -> AsyncEngine:
    """Create an async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(  # pyright: ignore[reportUnusedFunction]
        dbapi_connection: Any,  # pyright: ignore[reportExplicitAny,reportAny]
        connection_record: Any,  # pyright: ignore[reportExplicitAny,reportUnusedParameter,reportAny]
    ) -> None:
        cursor = dbapi_connection.cursor()  # pyright: ignore[reportAny]
        cursor.execute("PRAGMA foreign_keys=ON")  # pyright: ignore[reportAny]
        cursor.close()  # pyright: ignore[reportAny]

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return engine


class TestServiceValidatesBeforePersisting:
    """
    Feature: zondarr-foundation
    Property 10: Service Validates Before Persisting

    *For any* media server configuration where `test_connection()` returns False,
    the MediaServerService SHALL NOT persist the server to the database and
    SHALL raise a validation error.

    **Validates: Requirements 6.3**
    """

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        name=name_strategy,
        server_type=server_type_strategy,
        url=url_strategy,
        api_key=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_add_server_fails_when_connection_test_fails(
        self,
        name: str,
        server_type: ServerType,
        url: str,
        api_key: str,
    ) -> None:
        """MediaServerService.add raises ValidationError when connection test fails."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = MediaServerRepository(session)

                # Create a mock registry that returns a client with failing connection
                mock_registry = MagicMock(spec=ClientRegistry)
                mock_client = AsyncMock()
                mock_client.test_connection = AsyncMock(return_value=False)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_registry.create_client = MagicMock(return_value=mock_client)

                service = MediaServerService(repo, registry=mock_registry)

                # Attempt to add server - should raise ValidationError
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.add(
                        name=name,
                        server_type=server_type,
                        url=url,
                        api_key=api_key,
                    )

                # Verify error details
                assert exc_info.value.error_code == "VALIDATION_ERROR"
                assert "url" in exc_info.value.field_errors
                assert "api_key" in exc_info.value.field_errors

                # Verify server was NOT persisted
                all_servers = await repo.get_all()
                assert len(all_servers) == 0
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        name=name_strategy,
        server_type=server_type_strategy,
        url=url_strategy,
        api_key=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_add_server_succeeds_when_connection_test_passes(
        self,
        name: str,
        server_type: ServerType,
        url: str,
        api_key: str,
    ) -> None:
        """MediaServerService.add persists server when connection test passes."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = MediaServerRepository(session)

                # Create a mock registry that returns a client with passing connection
                mock_registry = MagicMock(spec=ClientRegistry)
                mock_client = AsyncMock()
                mock_client.test_connection = AsyncMock(return_value=True)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_registry.create_client = MagicMock(return_value=mock_client)

                service = MediaServerService(repo, registry=mock_registry)

                # Add server - should succeed
                created = await service.add(
                    name=name,
                    server_type=server_type,
                    url=url,
                    api_key=api_key,
                )
                await session.commit()

                # Verify server was persisted
                assert created.id is not None
                assert created.name == name
                assert created.server_type == server_type
                assert created.url == url
                assert created.api_key == api_key

                # Verify server exists in database
                retrieved = await repo.get_by_id(created.id)
                assert retrieved is not None
                assert retrieved.name == name
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        name=name_strategy,
        server_type=server_type_strategy,
        url=url_strategy,
        api_key=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_add_server_fails_when_connection_raises_exception(
        self,
        name: str,
        server_type: ServerType,
        url: str,
        api_key: str,
    ) -> None:
        """MediaServerService.add returns False when connection test raises exception."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = MediaServerRepository(session)

                # Create a mock registry that returns a client that raises exception
                mock_registry = MagicMock(spec=ClientRegistry)
                mock_client = AsyncMock()
                mock_client.test_connection = AsyncMock(
                    side_effect=Exception("Connection failed")
                )
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_registry.create_client = MagicMock(return_value=mock_client)

                service = MediaServerService(repo, registry=mock_registry)

                # Attempt to add server - should raise ValidationError
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.add(
                        name=name,
                        server_type=server_type,
                        url=url,
                        api_key=api_key,
                    )

                # Verify error details
                assert exc_info.value.error_code == "VALIDATION_ERROR"

                # Verify server was NOT persisted
                all_servers = await repo.get_all()
                assert len(all_servers) == 0
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        new_url=url_strategy,
        new_api_key=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_update_server_validates_when_credentials_change(
        self,
        new_url: str,
        new_api_key: str,
    ) -> None:
        """MediaServerService.update validates connection when url or api_key changes."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = MediaServerRepository(session)

                # Create a mock registry
                mock_registry = MagicMock(spec=ClientRegistry)
                mock_client = AsyncMock()
                # First call succeeds (for initial add), second fails (for update)
                mock_client.test_connection = AsyncMock(side_effect=[True, False])
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_registry.create_client = MagicMock(return_value=mock_client)

                service = MediaServerService(repo, registry=mock_registry)

                # First add a server successfully
                created = await service.add(
                    name="Test Server",
                    server_type=ServerType.JELLYFIN,
                    url="http://original.local",
                    api_key="originalkey",
                )
                await session.commit()

                # Now try to update with new credentials - should fail validation
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.update(
                        created.id,
                        url=new_url,
                        api_key=new_api_key,
                    )

                assert exc_info.value.error_code == "VALIDATION_ERROR"

                # Verify original server data is unchanged
                retrieved = await repo.get_by_id(created.id)
                assert retrieved is not None
                assert retrieved.url == "http://original.local"
                assert retrieved.api_key == "originalkey"
        finally:
            await engine.dispose()


class TestInvitationValidationChecksAllConditions:
    """
    Feature: zondarr-foundation
    Property 11: Invitation Validation Checks All Conditions

    *For any* invitation redemption attempt, the InvitationService SHALL check:
    (1) enabled status, (2) expiration time, (3) use count vs max_uses.
    If any check fails, it SHALL return a specific error indicating which
    condition failed.

    **Validates: Requirements 6.5, 6.6**
    """

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_redeem_fails_for_disabled_invitation(self, code: str) -> None:
        """InvitationService.redeem fails with DISABLED for disabled invitations."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create a disabled invitation
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = False  # Disabled
                invitation.expires_at = None
                invitation.max_uses = None
                invitation.use_count = 0
                _ = await repo.create(invitation)
                await session.commit()

                # Attempt to redeem - should fail with DISABLED
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.redeem(code)

                assert "disabled" in exc_info.value.message.lower()
                assert "code" in exc_info.value.field_errors
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_redeem_fails_for_expired_invitation(self, code: str) -> None:
        """InvitationService.redeem fails with EXPIRED for expired invitations."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create an expired invitation
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = datetime.now(UTC) - timedelta(days=1)  # Expired
                invitation.max_uses = None
                invitation.use_count = 0
                _ = await repo.create(invitation)
                await session.commit()

                # Attempt to redeem - should fail with EXPIRED
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.redeem(code)

                assert "expired" in exc_info.value.message.lower()
                assert "code" in exc_info.value.field_errors
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        code=code_strategy,
        max_uses=st.integers(min_value=1, max_value=100),
    )
    @pytest.mark.asyncio
    async def test_redeem_fails_for_exhausted_invitation(
        self, code: str, max_uses: int
    ) -> None:
        """InvitationService.redeem fails with MAX_USES_REACHED for exhausted invitations."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create an exhausted invitation (use_count >= max_uses)
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = None
                invitation.max_uses = max_uses
                invitation.use_count = max_uses  # Already at max
                _ = await repo.create(invitation)
                await session.commit()

                # Attempt to redeem - should fail with MAX_USES_REACHED
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.redeem(code)

                assert "max" in exc_info.value.message.lower()
                assert "code" in exc_info.value.field_errors
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_redeem_fails_for_nonexistent_invitation(self, code: str) -> None:
        """InvitationService.redeem fails with NOT_FOUND for nonexistent invitations."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Attempt to redeem nonexistent code - should fail with NotFoundError
                with pytest.raises(NotFoundError) as exc_info:
                    _ = await service.redeem(code)

                assert exc_info.value.error_code == "NOT_FOUND"
                assert exc_info.value.context["resource_type"] == "Invitation"
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_redeem_succeeds_for_valid_invitation(self, code: str) -> None:
        """InvitationService.redeem succeeds and increments use_count for valid invitations."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create a valid invitation
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = datetime.now(UTC) + timedelta(days=7)  # Future
                invitation.max_uses = 10
                invitation.use_count = 0
                _ = await repo.create(invitation)
                await session.commit()

                # Redeem - should succeed
                redeemed = await service.redeem(code)
                await session.commit()

                # Verify use_count was incremented
                assert redeemed.use_count == 1
                assert redeemed.code == code

                # Verify in database
                retrieved = await repo.get_by_code(code)
                assert retrieved is not None
                assert retrieved.use_count == 1
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_validate_returns_correct_failure_reason(self, code: str) -> None:
        """InvitationService.validate returns specific failure reasons."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Test NOT_FOUND
                is_valid, reason = await service.validate(code)
                assert is_valid is False
                assert reason == InvitationValidationFailure.NOT_FOUND

                # Create disabled invitation
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = False
                invitation.expires_at = None
                invitation.max_uses = None
                invitation.use_count = 0
                _ = await repo.create(invitation)
                await session.commit()

                # Test DISABLED
                is_valid, reason = await service.validate(code)
                assert is_valid is False
                assert reason == InvitationValidationFailure.DISABLED
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_validation_checks_in_order(self, code: str) -> None:
        """InvitationService checks enabled, then expiration, then max_uses."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation that fails all checks
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = False  # Fails first check
                invitation.expires_at = datetime.now(UTC) - timedelta(days=1)  # Expired
                invitation.max_uses = 1
                invitation.use_count = 1  # Exhausted
                _ = await repo.create(invitation)
                await session.commit()

                # Should fail with DISABLED (first check)
                is_valid, reason = await service.validate(code)
                assert is_valid is False
                assert reason == InvitationValidationFailure.DISABLED

                # Enable it - should now fail with EXPIRED
                invitation.enabled = True
                await session.commit()

                is_valid, reason = await service.validate(code)
                assert is_valid is False
                assert reason == InvitationValidationFailure.EXPIRED

                # Fix expiration - should now fail with MAX_USES_REACHED
                invitation.expires_at = datetime.now(UTC) + timedelta(days=1)
                await session.commit()

                is_valid, reason = await service.validate(code)
                assert is_valid is False
                assert reason == InvitationValidationFailure.MAX_USES_REACHED

                # Fix max_uses - should now be valid
                invitation.use_count = 0
                await session.commit()

                is_valid, reason = await service.validate(code)
                assert is_valid is True
                assert reason is None
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_invitation_with_no_limits_is_always_valid(self, code: str) -> None:
        """Invitation with no expiration and no max_uses is always valid when enabled."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation with no limits
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = None  # No expiration
                invitation.max_uses = None  # No max uses
                invitation.use_count = 1000  # High use count doesn't matter
                _ = await repo.create(invitation)
                await session.commit()

                # Should be valid
                is_valid, reason = await service.validate(code)
                assert is_valid is True
                assert reason is None

                # Should be redeemable
                redeemed = await service.redeem(code)
                assert redeemed.use_count == 1001
        finally:
            await engine.dispose()


class TestGeneratedCodesAreValid:
    """
    Feature: jellyfin-integration
    Property 8: Generated Codes Are Valid

    *For any* generated invitation code, the code SHALL:
    (1) be exactly 12 characters long,
    (2) contain only uppercase letters and digits,
    (3) exclude ambiguous characters (0, O, I, L).

    **Validates: Requirements 9.2, 9.3**
    """

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(st.integers(min_value=1, max_value=100))
    @pytest.mark.asyncio
    async def test_generated_code_has_correct_length(
        self,
        iteration: int,  # pyright: ignore[reportUnusedParameter]
    ) -> None:
        """Generated invitation codes are exactly 12 characters long."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation without providing code - should generate one
                invitation = await service.create()
                await session.commit()

                # Verify code length
                assert len(invitation.code) == 12
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(st.integers(min_value=1, max_value=100))
    @pytest.mark.asyncio
    async def test_generated_code_contains_only_valid_characters(
        self,
        iteration: int,  # pyright: ignore[reportUnusedParameter]
    ) -> None:
        """Generated codes contain only uppercase letters and digits."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation without providing code
                invitation = await service.create()
                await session.commit()

                # Verify all characters are uppercase letters or digits
                for char in invitation.code:
                    assert char.isupper() or char.isdigit(), (
                        f"Invalid character '{char}' in code '{invitation.code}'"
                    )
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(st.integers(min_value=1, max_value=100))
    @pytest.mark.asyncio
    async def test_generated_code_excludes_ambiguous_characters(
        self,
        iteration: int,  # pyright: ignore[reportUnusedParameter]
    ) -> None:
        """Generated codes exclude ambiguous characters (0, O, I, L)."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation without providing code
                invitation = await service.create()
                await session.commit()

                # Verify no ambiguous characters
                ambiguous_chars = {"0", "O", "I", "L"}
                for char in invitation.code:
                    assert char not in ambiguous_chars, (
                        f"Ambiguous character '{char}' found in code '{invitation.code}'"
                    )
        finally:
            await engine.dispose()

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(st.integers(min_value=1, max_value=50))
    @pytest.mark.asyncio
    async def test_generated_codes_are_unique(
        self,
        iteration: int,  # pyright: ignore[reportUnusedParameter]
    ) -> None:
        """Multiple generated codes are unique."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create multiple invitations
                codes: set[str] = set()
                num_invitations = 10

                for _ in range(num_invitations):
                    invitation = await service.create()
                    codes.add(invitation.code)
                    await session.commit()

                # All codes should be unique
                assert len(codes) == num_invitations
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        custom_code=st.text(
            alphabet=st.characters(categories=("L", "N")),
            min_size=1,
            max_size=20,
        )
    )
    @pytest.mark.asyncio
    async def test_custom_code_is_preserved(self, custom_code: str) -> None:
        """When a custom code is provided, it is used instead of generating one."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation with custom code
                invitation = await service.create(code=custom_code)
                await session.commit()

                # Verify custom code is preserved
                assert invitation.code == custom_code
        finally:
            await engine.dispose()


class TestServerAndLibraryValidationOnCreate:
    """
    Feature: jellyfin-integration
    Property 9: Server and Library Validation on Create

    *For any* invitation creation with server_ids or library_ids:
    (1) All server_ids SHALL reference existing enabled MediaServer records,
    (2) All library_ids SHALL belong to the specified target servers.

    **Validates: Requirements 9.5, 9.6**
    """

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(st.uuids())
    @pytest.mark.asyncio
    async def test_create_fails_with_nonexistent_server_ids(
        self, fake_server_id: UUID
    ) -> None:
        """Creating invitation with nonexistent server_ids raises ValidationError."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                invitation_repo = InvitationRepository(session)
                server_repo = MediaServerRepository(session)
                service = InvitationService(
                    invitation_repo, server_repository=server_repo
                )

                # Attempt to create invitation with nonexistent server ID
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.create(server_ids=[fake_server_id])

                assert "server_ids" in exc_info.value.field_errors
                assert any(
                    "does not exist" in msg or "disabled" in msg
                    for msg in exc_info.value.field_errors["server_ids"]
                )
        finally:
            await engine.dispose()

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        name=name_strategy,
        url=url_strategy,
        api_key=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_fails_with_disabled_server_ids(
        self, name: str, url: str, api_key: str
    ) -> None:
        """Creating invitation with disabled server_ids raises ValidationError."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                invitation_repo = InvitationRepository(session)
                server_repo = MediaServerRepository(session)
                service = InvitationService(
                    invitation_repo, server_repository=server_repo
                )

                # Create a disabled server
                from zondarr.models.media_server import MediaServer

                server = MediaServer(
                    name=name,
                    server_type=ServerType.JELLYFIN,
                    url=url,
                    api_key=api_key,
                    enabled=False,  # Disabled
                )
                session.add(server)
                await session.flush()
                await session.commit()

                # Attempt to create invitation with disabled server ID
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.create(server_ids=[server.id])

                assert "server_ids" in exc_info.value.field_errors
        finally:
            await engine.dispose()

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        name=name_strategy,
        url=url_strategy,
        api_key=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_succeeds_with_valid_enabled_server_ids(
        self, name: str, url: str, api_key: str
    ) -> None:
        """Creating invitation with valid enabled server_ids succeeds."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                invitation_repo = InvitationRepository(session)
                server_repo = MediaServerRepository(session)
                service = InvitationService(
                    invitation_repo, server_repository=server_repo
                )

                # Create an enabled server
                from zondarr.models.media_server import MediaServer

                server = MediaServer(
                    name=name,
                    server_type=ServerType.JELLYFIN,
                    url=url,
                    api_key=api_key,
                    enabled=True,
                )
                session.add(server)
                await session.flush()
                await session.commit()

                # Create invitation with valid server ID
                invitation = await service.create(server_ids=[server.id])
                await session.commit()

                assert invitation.id is not None
                assert len(invitation.target_servers) == 1
                assert invitation.target_servers[0].id == server.id
        finally:
            await engine.dispose()

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(st.uuids())
    @pytest.mark.asyncio
    async def test_create_fails_with_nonexistent_library_ids(
        self, fake_library_id: UUID
    ) -> None:
        """Creating invitation with nonexistent library_ids raises ValidationError."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                invitation_repo = InvitationRepository(session)
                server_repo = MediaServerRepository(session)
                service = InvitationService(
                    invitation_repo, server_repository=server_repo
                )

                # Create an enabled server first
                from zondarr.models.media_server import MediaServer

                server = MediaServer(
                    name="Test Server",
                    server_type=ServerType.JELLYFIN,
                    url="http://test.local",
                    api_key="testkey",
                    enabled=True,
                )
                session.add(server)
                await session.flush()
                await session.commit()

                # Attempt to create invitation with nonexistent library ID
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.create(
                        server_ids=[server.id], library_ids=[fake_library_id]
                    )

                assert "library_ids" in exc_info.value.field_errors
                assert any(
                    "does not exist" in msg
                    for msg in exc_info.value.field_errors["library_ids"]
                )
        finally:
            await engine.dispose()

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        name=name_strategy,
        url=url_strategy,
        api_key=name_strategy,
        library_name=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_fails_with_library_not_belonging_to_target_server(
        self, name: str, url: str, api_key: str, library_name: str
    ) -> None:
        """Creating invitation with library not belonging to target server raises ValidationError."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                invitation_repo = InvitationRepository(session)
                server_repo = MediaServerRepository(session)
                service = InvitationService(
                    invitation_repo, server_repository=server_repo
                )

                from zondarr.models.media_server import Library, MediaServer

                # Create two servers
                server1 = MediaServer(
                    name=name,
                    server_type=ServerType.JELLYFIN,
                    url=url,
                    api_key=api_key,
                    enabled=True,
                )
                server2 = MediaServer(
                    name=f"{name}_2",
                    server_type=ServerType.JELLYFIN,
                    url=f"{url}/2",
                    api_key=f"{api_key}_2",
                    enabled=True,
                )
                session.add(server1)
                session.add(server2)
                await session.flush()

                # Create library belonging to server2
                library = Library(
                    media_server_id=server2.id,
                    external_id="lib123",
                    name=library_name,
                    library_type="movies",
                )
                session.add(library)
                await session.flush()
                await session.commit()

                # Attempt to create invitation with server1 but library from server2
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.create(
                        server_ids=[server1.id], library_ids=[library.id]
                    )

                assert "library_ids" in exc_info.value.field_errors
                assert any(
                    "does not belong" in msg
                    for msg in exc_info.value.field_errors["library_ids"]
                )
        finally:
            await engine.dispose()

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        name=name_strategy,
        url=url_strategy,
        api_key=name_strategy,
        library_name=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_succeeds_with_valid_library_ids(
        self, name: str, url: str, api_key: str, library_name: str
    ) -> None:
        """Creating invitation with valid library_ids belonging to target server succeeds."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                invitation_repo = InvitationRepository(session)
                server_repo = MediaServerRepository(session)
                service = InvitationService(
                    invitation_repo, server_repository=server_repo
                )

                from zondarr.models.media_server import Library, MediaServer

                # Create an enabled server
                server = MediaServer(
                    name=name,
                    server_type=ServerType.JELLYFIN,
                    url=url,
                    api_key=api_key,
                    enabled=True,
                )
                session.add(server)
                await session.flush()

                # Create library belonging to the server
                library = Library(
                    media_server_id=server.id,
                    external_id="lib123",
                    name=library_name,
                    library_type="movies",
                )
                session.add(library)
                await session.flush()
                await session.commit()

                # Create invitation with valid server and library IDs
                invitation = await service.create(
                    server_ids=[server.id], library_ids=[library.id]
                )
                await session.commit()

                assert invitation.id is not None
                assert len(invitation.target_servers) == 1
                assert len(invitation.allowed_libraries) == 1
                assert invitation.allowed_libraries[0].id == library.id
        finally:
            await engine.dispose()


class TestInvitationComputedFields:
    """
    Feature: jellyfin-integration
    Property 10: Invitation Computed Fields

    *For any* invitation:
    (1) is_active SHALL be True iff enabled AND not expired AND use_count < max_uses,
    (2) remaining_uses SHALL be max_uses - use_count if max_uses is set, else None.

    **Validates: Requirements 10.5**
    """

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        enabled=st.booleans(),
        use_count=st.integers(min_value=0, max_value=100),
        max_uses=st.one_of(st.none(), st.integers(min_value=1, max_value=100)),
        is_expired=st.booleans(),
    )
    @pytest.mark.asyncio
    async def test_is_active_computed_correctly(
        self,
        enabled: bool,
        use_count: int,
        max_uses: int | None,
        is_expired: bool,
    ) -> None:
        """is_active is True iff enabled AND not expired AND use_count < max_uses."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation with specified properties
                invitation = Invitation()
                invitation.code = f"TEST{use_count:04d}{max_uses or 0:04d}"
                invitation.enabled = enabled
                invitation.use_count = use_count
                invitation.max_uses = max_uses

                # Set expiration based on is_expired flag
                if is_expired:
                    invitation.expires_at = datetime.now(UTC) - timedelta(days=1)
                else:
                    invitation.expires_at = datetime.now(UTC) + timedelta(days=7)

                _ = await repo.create(invitation)
                await session.commit()

                # Calculate expected is_active
                expected_is_active = enabled and not is_expired
                if max_uses is not None:
                    expected_is_active = expected_is_active and (use_count < max_uses)

                # Verify computed field
                actual_is_active = service.is_active(invitation)
                assert actual_is_active == expected_is_active, (
                    f"is_active mismatch: expected {expected_is_active}, got {actual_is_active} "
                    f"(enabled={enabled}, is_expired={is_expired}, use_count={use_count}, max_uses={max_uses})"
                )
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        use_count=st.integers(min_value=0, max_value=100),
        max_uses=st.one_of(st.none(), st.integers(min_value=1, max_value=100)),
    )
    @pytest.mark.asyncio
    async def test_remaining_uses_computed_correctly(
        self,
        use_count: int,
        max_uses: int | None,
    ) -> None:
        """remaining_uses is max_uses - use_count if max_uses set, else None."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation with specified properties
                invitation = Invitation()
                invitation.code = f"TEST{use_count:04d}{max_uses or 0:04d}"
                invitation.enabled = True
                invitation.use_count = use_count
                invitation.max_uses = max_uses
                invitation.expires_at = None

                _ = await repo.create(invitation)
                await session.commit()

                # Calculate expected remaining_uses
                if max_uses is None:
                    expected_remaining = None
                else:
                    expected_remaining = max(0, max_uses - use_count)

                # Verify computed field
                actual_remaining = service.remaining_uses(invitation)
                assert actual_remaining == expected_remaining, (
                    f"remaining_uses mismatch: expected {expected_remaining}, got {actual_remaining} "
                    f"(use_count={use_count}, max_uses={max_uses})"
                )
        finally:
            await engine.dispose()

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_is_active_false_when_disabled(self, code: str) -> None:
        """is_active is False when invitation is disabled."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create disabled invitation
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = False
                invitation.use_count = 0
                invitation.max_uses = 10
                invitation.expires_at = datetime.now(UTC) + timedelta(days=7)

                _ = await repo.create(invitation)
                await session.commit()

                assert service.is_active(invitation) is False
        finally:
            await engine.dispose()

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_is_active_false_when_expired(self, code: str) -> None:
        """is_active is False when invitation is expired."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create expired invitation
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.use_count = 0
                invitation.max_uses = 10
                invitation.expires_at = datetime.now(UTC) - timedelta(days=1)

                _ = await repo.create(invitation)
                await session.commit()

                assert service.is_active(invitation) is False
        finally:
            await engine.dispose()

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        code=code_strategy,
        max_uses=st.integers(min_value=1, max_value=100),
    )
    @pytest.mark.asyncio
    async def test_is_active_false_when_exhausted(
        self, code: str, max_uses: int
    ) -> None:
        """is_active is False when invitation has reached max uses."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create exhausted invitation
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.use_count = max_uses  # At max
                invitation.max_uses = max_uses
                invitation.expires_at = datetime.now(UTC) + timedelta(days=7)

                _ = await repo.create(invitation)
                await session.commit()

                assert service.is_active(invitation) is False
        finally:
            await engine.dispose()

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_remaining_uses_none_when_unlimited(self, code: str) -> None:
        """remaining_uses is None when max_uses is not set."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create unlimited invitation
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.use_count = 100
                invitation.max_uses = None  # Unlimited
                invitation.expires_at = None

                _ = await repo.create(invitation)
                await session.commit()

                assert service.remaining_uses(invitation) is None
        finally:
            await engine.dispose()

    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        code=code_strategy,
        max_uses=st.integers(min_value=1, max_value=100),
        use_count=st.integers(min_value=0, max_value=200),
    )
    @pytest.mark.asyncio
    async def test_remaining_uses_never_negative(
        self, code: str, max_uses: int, use_count: int
    ) -> None:
        """remaining_uses is never negative, even if use_count > max_uses."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation (use_count may exceed max_uses)
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.use_count = use_count
                invitation.max_uses = max_uses
                invitation.expires_at = None

                _ = await repo.create(invitation)
                await session.commit()

                remaining = service.remaining_uses(invitation)
                assert remaining is not None
                assert remaining >= 0, (
                    f"remaining_uses should never be negative, got {remaining}"
                )
        finally:
            await engine.dispose()
