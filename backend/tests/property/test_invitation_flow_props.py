"""Property-based tests for invitation creation and redemption flow.

Feature: phase-6-polish
Tests invitation creation with various configurations and redemption validation.

**Validates: Requirements 6.1, 6.2**
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.core.exceptions import NotFoundError, ValidationError
from zondarr.models import Invitation
from zondarr.repositories.invitation import InvitationRepository
from zondarr.services.invitation import InvitationService, InvitationValidationFailure

# =============================================================================
# Custom Strategies
# =============================================================================

# Code strategy - valid invitation codes
code_strategy = st.uuids().map(lambda u: str(u).replace("-", "")[:12].upper())

# Max uses strategy - positive integers
max_uses_strategy = st.integers(min_value=1, max_value=1000)

# Duration days strategy - positive integers
duration_days_strategy = st.integers(min_value=1, max_value=365)

# Server name strategy
server_name_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=1,
    max_size=50,
).filter(lambda x: x.strip())

# URL strategy
url_strategy = st.from_regex(r"https?://[a-z0-9]+\.[a-z]{2,}", fullmatch=True)


# =============================================================================
# Property Tests: Invitation Creation with Various Configurations
# Validates: Requirements 6.1
# =============================================================================


class TestInvitationCreationConfigurations:
    """Property tests for invitation creation with various configurations.

    **Validates: Requirements 6.1**
    """

    @given(
        max_uses=max_uses_strategy,
        duration_days=duration_days_strategy,
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_create_with_max_uses_and_duration(
        self,
        max_uses: int,
        duration_days: int,
    ) -> None:
        """Invitation creation with max_uses and duration_days persists correctly.

        **Validates: Requirements 6.1**

        Property: For any valid max_uses and duration_days values, the created
        invitation SHALL have those exact values persisted.
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = await service.create(
                    max_uses=max_uses,
                    duration_days=duration_days,
                )
                await session.commit()

                # PROPERTY ASSERTION: Values are persisted correctly
                assert invitation.max_uses == max_uses
                assert invitation.duration_days == duration_days
                assert invitation.enabled is True
                assert invitation.use_count == 0

                # Verify persistence
                retrieved = await repo.get_by_code(invitation.code)
                assert retrieved is not None
                assert retrieved.max_uses == max_uses
                assert retrieved.duration_days == duration_days
        finally:
            await engine.dispose()

    @given(
        days_until_expiry=st.integers(min_value=1, max_value=365),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_create_with_future_expiration(
        self,
        days_until_expiry: int,
    ) -> None:
        """Invitation creation with future expiration date persists correctly.

        **Validates: Requirements 6.1**

        Property: For any future expiration date, the created invitation
        SHALL have that expiration date persisted and be considered active.
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                expires_at = datetime.now(UTC) + timedelta(days=days_until_expiry)
                invitation = await service.create(expires_at=expires_at)
                await session.commit()

                # PROPERTY ASSERTION: Expiration is persisted
                assert invitation.expires_at is not None
                # Allow small time difference due to test execution
                time_diff = abs((invitation.expires_at - expires_at).total_seconds())
                assert time_diff < 1.0

                # Invitation should be active
                assert service.is_active(invitation) is True
        finally:
            await engine.dispose()

    @given(code=code_strategy)
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_create_with_custom_code(self, code: str) -> None:
        """Invitation creation with custom code uses the provided code.

        **Validates: Requirements 6.1**

        Property: For any valid custom code, the created invitation
        SHALL use that exact code.
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = await service.create(code=code)
                await session.commit()

                # PROPERTY ASSERTION: Custom code is used
                assert invitation.code == code

                # Verify retrieval by code works
                retrieved = await repo.get_by_code(code)
                assert retrieved is not None
                assert retrieved.id == invitation.id
        finally:
            await engine.dispose()

    @given(st.integers(min_value=1, max_value=5))
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_create_without_limits_is_unlimited(self, _iteration: int) -> None:
        """Invitation creation without limits creates unlimited invitation.

        **Validates: Requirements 6.1**

        Property: An invitation created without max_uses or expires_at
        SHALL be considered unlimited and always active (when enabled).
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = await service.create()
                await session.commit()

                # PROPERTY ASSERTION: No limits set
                assert invitation.max_uses is None
                assert invitation.expires_at is None
                assert invitation.enabled is True

                # Should be active
                assert service.is_active(invitation) is True

                # Remaining uses should be None (unlimited)
                assert service.remaining_uses(invitation) is None
        finally:
            await engine.dispose()

    @given(
        max_uses=max_uses_strategy,
        use_count=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_remaining_uses_calculation(
        self,
        max_uses: int,
        use_count: int,
    ) -> None:
        """Remaining uses is correctly calculated as max_uses - use_count.

        **Validates: Requirements 6.1**

        Property: For any invitation with max_uses M and use_count U,
        remaining_uses SHALL equal max(0, M - U).
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = Invitation(
                    code=str(uuid4()).replace("-", "")[:12].upper(),
                    max_uses=max_uses,
                    use_count=use_count,
                    enabled=True,
                )
                _ = await repo.create(invitation)
                await session.commit()

                # PROPERTY ASSERTION: Remaining uses calculation
                expected_remaining = max(0, max_uses - use_count)
                assert service.remaining_uses(invitation) == expected_remaining
        finally:
            await engine.dispose()


# =============================================================================
# Property Tests: Invitation Redemption Validation
# Validates: Requirements 6.2
# =============================================================================


class TestInvitationRedemptionValidation:
    """Property tests for invitation redemption validation.

    **Validates: Requirements 6.2**
    """

    @given(
        code=code_strategy,
        max_uses=st.integers(min_value=2, max_value=100),
        redemption_count=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_multiple_redemptions_increment_use_count(
        self,
        code: str,
        max_uses: int,
        redemption_count: int,
    ) -> None:
        """Multiple redemptions correctly increment use_count.

        **Validates: Requirements 6.2**

        Property: For any invitation with max_uses M, redeeming N times
        (where N < M) SHALL result in use_count = N.
        """
        # Ensure we don't exceed max_uses
        actual_redemptions = min(redemption_count, max_uses - 1)
        if actual_redemptions < 1:
            return  # Skip if no valid redemptions possible

        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = Invitation(
                    code=code,
                    max_uses=max_uses,
                    use_count=0,
                    enabled=True,
                    expires_at=datetime.now(UTC) + timedelta(days=30),
                )
                _ = await repo.create(invitation)
                await session.commit()

                # Perform redemptions
                for i in range(actual_redemptions):
                    redeemed = await service.redeem(code)
                    await session.commit()

                    # PROPERTY ASSERTION: Use count increments correctly
                    assert redeemed.use_count == i + 1

                # Final verification
                final = await repo.get_by_code(code)
                assert final is not None
                assert final.use_count == actual_redemptions
        finally:
            await engine.dispose()

    @given(
        code=code_strategy,
        max_uses=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_redemption_fails_when_exhausted(
        self,
        code: str,
        max_uses: int,
    ) -> None:
        """Redemption fails when max_uses is reached.

        **Validates: Requirements 6.2**

        Property: For any invitation with max_uses M and use_count = M,
        redemption SHALL fail with MAX_USES_REACHED error.
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create exhausted invitation
                invitation = Invitation(
                    code=code,
                    max_uses=max_uses,
                    use_count=max_uses,  # Already at max
                    enabled=True,
                )
                _ = await repo.create(invitation)
                await session.commit()

                # Validate should return MAX_USES_REACHED
                is_valid, reason = await service.validate(code)
                assert is_valid is False
                assert reason == InvitationValidationFailure.MAX_USES_REACHED

                # Redeem should raise ValidationError
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.redeem(code)

                assert "max" in exc_info.value.message.lower()
        finally:
            await engine.dispose()

    @given(
        code=code_strategy,
        days_expired=st.integers(min_value=1, max_value=365),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_redemption_fails_when_expired(
        self,
        code: str,
        days_expired: int,
    ) -> None:
        """Redemption fails when invitation has expired.

        **Validates: Requirements 6.2**

        Property: For any invitation with expires_at in the past,
        redemption SHALL fail with EXPIRED error.
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create expired invitation
                invitation = Invitation(
                    code=code,
                    expires_at=datetime.now(UTC) - timedelta(days=days_expired),
                    enabled=True,
                    use_count=0,
                )
                _ = await repo.create(invitation)
                await session.commit()

                # Validate should return EXPIRED
                is_valid, reason = await service.validate(code)
                assert is_valid is False
                assert reason == InvitationValidationFailure.EXPIRED

                # Redeem should raise ValidationError
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.redeem(code)

                assert "expired" in exc_info.value.message.lower()
        finally:
            await engine.dispose()

    @given(code=code_strategy)
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_redemption_fails_when_disabled(self, code: str) -> None:
        """Redemption fails when invitation is disabled.

        **Validates: Requirements 6.2**

        Property: For any disabled invitation, redemption SHALL fail
        with DISABLED error.
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create disabled invitation
                invitation = Invitation(
                    code=code,
                    enabled=False,
                    use_count=0,
                )
                _ = await repo.create(invitation)
                await session.commit()

                # Validate should return DISABLED
                is_valid, reason = await service.validate(code)
                assert is_valid is False
                assert reason == InvitationValidationFailure.DISABLED

                # Redeem should raise ValidationError
                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.redeem(code)

                assert "disabled" in exc_info.value.message.lower()
        finally:
            await engine.dispose()

    @given(code=code_strategy)
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_redemption_fails_for_nonexistent_code(self, code: str) -> None:
        """Redemption fails for non-existent invitation code.

        **Validates: Requirements 6.2**

        Property: For any code that doesn't exist in the database,
        redemption SHALL fail with NOT_FOUND error.
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Validate should return NOT_FOUND
                is_valid, reason = await service.validate(code)
                assert is_valid is False
                assert reason == InvitationValidationFailure.NOT_FOUND

                # Redeem should raise NotFoundError
                with pytest.raises(NotFoundError) as exc_info:
                    _ = await service.redeem(code)

                assert exc_info.value.error_code == "NOT_FOUND"
        finally:
            await engine.dispose()

    @given(
        code=code_strategy,
        days_until_expiry=st.integers(min_value=1, max_value=365),
        max_uses=st.integers(min_value=2, max_value=100),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_valid_invitation_passes_all_checks(
        self,
        code: str,
        days_until_expiry: int,
        max_uses: int,
    ) -> None:
        """Valid invitation passes all validation checks.

        **Validates: Requirements 6.2**

        Property: For any invitation that is enabled, not expired,
        and not exhausted, validation SHALL succeed.
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create valid invitation
                invitation = Invitation(
                    code=code,
                    expires_at=datetime.now(UTC) + timedelta(days=days_until_expiry),
                    max_uses=max_uses,
                    use_count=0,
                    enabled=True,
                )
                _ = await repo.create(invitation)
                await session.commit()

                # Validate should succeed
                is_valid, reason = await service.validate(code)
                assert is_valid is True
                assert reason is None

                # is_active should return True
                assert service.is_active(invitation) is True

                # Redeem should succeed
                redeemed = await service.redeem(code)
                await session.commit()

                assert redeemed.use_count == 1
        finally:
            await engine.dispose()


# =============================================================================
# Property Tests: Invitation Update Operations
# Validates: Requirements 6.1, 6.2
# =============================================================================


class TestInvitationUpdateOperations:
    """Property tests for invitation update operations.

    **Validates: Requirements 6.1, 6.2**
    """

    @given(
        code=code_strategy,
        initial_max_uses=st.integers(min_value=1, max_value=50),
        new_max_uses=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_update_max_uses(
        self,
        code: str,
        initial_max_uses: int,
        new_max_uses: int,
    ) -> None:
        """Updating max_uses persists the new value.

        **Validates: Requirements 6.1**

        Property: For any invitation, updating max_uses SHALL persist
        the new value while preserving other fields.
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation
                invitation = Invitation(
                    code=code,
                    max_uses=initial_max_uses,
                    enabled=True,
                    use_count=0,
                )
                created = await repo.create(invitation)
                await session.commit()

                # Update max_uses
                updated = await service.update(
                    created.id,
                    max_uses=new_max_uses,
                )
                await session.commit()

                # PROPERTY ASSERTION: max_uses is updated
                assert updated.max_uses == new_max_uses
                # Code should be unchanged (immutable)
                assert updated.code == code
                # use_count should be unchanged
                assert updated.use_count == 0
        finally:
            await engine.dispose()

    @given(
        code=code_strategy,
        initial_enabled=st.booleans(),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_disable_invitation(
        self,
        code: str,
        initial_enabled: bool,
    ) -> None:
        """Disabling an invitation prevents redemption.

        **Validates: Requirements 6.2**

        Property: For any enabled invitation, disabling it SHALL
        prevent further redemptions.
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation
                invitation = Invitation(
                    code=code,
                    enabled=initial_enabled,
                    use_count=0,
                )
                created = await repo.create(invitation)
                await session.commit()

                # Disable the invitation
                disabled = await service.disable(created.id)
                await session.commit()

                # PROPERTY ASSERTION: Invitation is disabled
                assert disabled.enabled is False

                # Validation should fail
                is_valid, reason = await service.validate(code)
                assert is_valid is False
                assert reason == InvitationValidationFailure.DISABLED
        finally:
            await engine.dispose()

    @given(code=code_strategy)
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_delete_invitation(self, code: str) -> None:
        """Deleting an invitation removes it from the database.

        **Validates: Requirements 6.1**

        Property: For any invitation, deleting it SHALL remove it
        from the database and make it unretrievable.
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                # Create invitation
                invitation = Invitation(
                    code=code,
                    enabled=True,
                    use_count=0,
                )
                created = await repo.create(invitation)
                await session.commit()
                invitation_id = created.id

                # Delete the invitation
                await service.delete(invitation_id)
                await session.commit()

                # PROPERTY ASSERTION: Invitation is deleted
                retrieved = await repo.get_by_code(code)
                assert retrieved is None

                # get_by_id should raise NotFoundError
                with pytest.raises(NotFoundError):
                    _ = await service.get_by_id(invitation_id)
        finally:
            await engine.dispose()
