"""Property-based tests for InvitationController validation endpoint.

Feature: jellyfin-integration
Properties: 13, 14
Validates: Requirements 13.2, 13.4, 13.6
"""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.models import Invitation
from zondarr.repositories.invitation import InvitationRepository
from zondarr.services.invitation import InvitationService, InvitationValidationFailure

# Custom strategies for model fields
# Use UUIDs for codes to ensure uniqueness across Hypothesis examples
code_strategy = st.uuids().map(lambda u: str(u).replace("-", "")[:12].upper())


class TestValidationChecksAllConditions:
    """Property 13: Validation Checks All Conditions.

    **Validates: Requirements 13.2, 13.4**

    For any invitation validation attempt, the service SHALL check:
    (1) code exists, (2) enabled status, (3) expiration time, (4) use count vs max_uses.
    If any check fails, it SHALL return a specific failure reason.
    """

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_validate_returns_not_found_for_nonexistent_code(
        self, code: str
    ) -> None:
        """Validation returns NOT_FOUND for nonexistent invitation codes."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                is_valid, reason = await service.validate(code)

                assert is_valid is False
                assert reason == InvitationValidationFailure.NOT_FOUND
        finally:
            await engine.dispose()

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_validate_returns_disabled_for_disabled_invitation(
        self, code: str
    ) -> None:
        """Validation returns DISABLED for disabled invitations."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = Invitation()
                invitation.code = code
                invitation.enabled = False
                invitation.expires_at = None
                invitation.max_uses = None
                invitation.use_count = 0
                _ = await repo.create(invitation)
                await session.commit()

                is_valid, reason = await service.validate(code)

                assert is_valid is False
                assert reason == InvitationValidationFailure.DISABLED
        finally:
            await engine.dispose()

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_validate_returns_expired_for_expired_invitation(
        self, code: str
    ) -> None:
        """Validation returns EXPIRED for expired invitations."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = datetime.now(UTC) - timedelta(days=1)
                invitation.max_uses = None
                invitation.use_count = 0
                _ = await repo.create(invitation)
                await session.commit()

                is_valid, reason = await service.validate(code)

                assert is_valid is False
                assert reason == InvitationValidationFailure.EXPIRED
        finally:
            await engine.dispose()

    @given(
        code=code_strategy,
        max_uses=st.integers(min_value=1, max_value=100),
    )
    @pytest.mark.asyncio
    async def test_validate_returns_max_uses_reached_for_exhausted_invitation(
        self, code: str, max_uses: int
    ) -> None:
        """Validation returns MAX_USES_REACHED for exhausted invitations."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = None
                invitation.max_uses = max_uses
                invitation.use_count = max_uses
                _ = await repo.create(invitation)
                await session.commit()

                is_valid, reason = await service.validate(code)

                assert is_valid is False
                assert reason == InvitationValidationFailure.MAX_USES_REACHED
        finally:
            await engine.dispose()

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_validate_returns_valid_for_valid_invitation(self, code: str) -> None:
        """Validation returns valid=True for valid invitations."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = datetime.now(UTC) + timedelta(days=7)
                invitation.max_uses = 10
                invitation.use_count = 0
                _ = await repo.create(invitation)
                await session.commit()

                is_valid, reason = await service.validate(code)

                assert is_valid is True
                assert reason is None
        finally:
            await engine.dispose()


class TestValidationDoesNotIncrementUseCount:
    """Property 14: Validation Does Not Increment Use Count.

    **Validates: Requirements 13.6**

    For any invitation validation attempt, the use_count SHALL NOT be incremented.
    Only redemption should increment the use count.
    """

    @given(
        code=code_strategy,
        initial_use_count=st.integers(min_value=0, max_value=50),
    )
    @pytest.mark.asyncio
    async def test_validate_does_not_increment_use_count_for_valid_invitation(
        self, code: str, initial_use_count: int
    ) -> None:
        """Validation does not increment use_count for valid invitations."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = datetime.now(UTC) + timedelta(days=7)
                invitation.max_uses = 100
                invitation.use_count = initial_use_count
                _ = await repo.create(invitation)
                await session.commit()

                # Validate multiple times
                for _ in range(3):
                    is_valid, _ = await service.validate(code)
                    assert is_valid is True

                # Verify use_count unchanged
                retrieved = await repo.get_by_code(code)
                assert retrieved is not None
                assert retrieved.use_count == initial_use_count
        finally:
            await engine.dispose()

    @given(
        code=code_strategy,
        initial_use_count=st.integers(min_value=0, max_value=50),
    )
    @pytest.mark.asyncio
    async def test_validate_does_not_increment_use_count_for_invalid_invitation(
        self, code: str, initial_use_count: int
    ) -> None:
        """Validation does not increment use_count for invalid invitations."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create a disabled invitation
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = False
                invitation.expires_at = None
                invitation.max_uses = None
                invitation.use_count = initial_use_count
                _ = await repo.create(invitation)
                await session.commit()

                # Validate multiple times
                for _ in range(3):
                    is_valid, _ = await service.validate(code)
                    assert is_valid is False

                # Verify use_count unchanged
                retrieved = await repo.get_by_code(code)
                assert retrieved is not None
                assert retrieved.use_count == initial_use_count
        finally:
            await engine.dispose()

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_redeem_increments_use_count_but_validate_does_not(
        self, code: str
    ) -> None:
        """Redeem increments use_count while validate does not."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = datetime.now(UTC) + timedelta(days=7)
                invitation.max_uses = 10
                invitation.use_count = 0
                _ = await repo.create(invitation)
                await session.commit()

                # Validate should not increment
                is_valid, _ = await service.validate(code)
                assert is_valid is True

                retrieved = await repo.get_by_code(code)
                assert retrieved is not None
                assert retrieved.use_count == 0

                # Redeem should increment
                redeemed = await service.redeem(code)
                await session.commit()
                assert redeemed.use_count == 1

                # Validate again should still not increment
                is_valid, _ = await service.validate(code)
                assert is_valid is True

                retrieved = await repo.get_by_code(code)
                assert retrieved is not None
                assert retrieved.use_count == 1
        finally:
            await engine.dispose()
