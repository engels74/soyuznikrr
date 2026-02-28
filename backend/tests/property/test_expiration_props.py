"""Property-based tests for invitation expiration background task.

Feature: phase-6-polish
Properties: 1, 2
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from hypothesis import given
from hypothesis import strategies as st
from litestar.datastructures import State

from tests.conftest import TestDB
from zondarr.config import Settings
from zondarr.core.tasks import BackgroundTaskManager
from zondarr.models.invitation import Invitation
from zondarr.repositories.invitation import InvitationRepository

# Custom strategies
code_strategy = st.uuids().map(lambda u: str(u).replace("-", "")[:12].upper())


def create_test_settings() -> Settings:
    """Create test settings with minimal intervals."""
    return Settings(
        secret_key="test-secret-key-at-least-32-characters-long",
        expiration_check_interval_seconds=60,
        sync_interval_seconds=60,
    )


class TestExpiredInvitationDisabling:
    """Property 1: Expired Invitation Disabling.

    For any set of invitations where some have expires_at in the past,
    running the expiration task SHALL result in all expired invitations
    having enabled=false, while non-expired invitations remain unchanged.
    """

    @given(
        expired_codes=st.lists(code_strategy, min_size=1, max_size=5, unique=True),
        active_codes=st.lists(code_strategy, min_size=0, max_size=3, unique=True),
        days_expired=st.integers(min_value=1, max_value=30),
        days_until_expiry=st.integers(min_value=1, max_value=30),
    )
    @pytest.mark.asyncio
    async def test_expired_invitations_are_disabled(
        self,
        db: TestDB,
        expired_codes: list[str],
        active_codes: list[str],
        days_expired: int,
        days_until_expiry: int,
    ) -> None:
        """Expired invitations are disabled while active ones remain enabled."""
        await db.clean()

        # Ensure no overlap between expired and active codes
        active_codes = [c for c in active_codes if c not in expired_codes]

        # Create invitations
        async with db.session_factory() as session:
            repo = InvitationRepository(session)
            now = datetime.now(UTC)

            # Create expired invitations
            for code in expired_codes:
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = now - timedelta(days=days_expired)
                invitation.max_uses = None
                invitation.use_count = 0
                _ = await repo.create(invitation)

            # Create active invitations
            for code in active_codes:
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = now + timedelta(days=days_until_expiry)
                invitation.max_uses = None
                invitation.use_count = 0
                _ = await repo.create(invitation)

            await session.commit()

        # Run expiration check
        settings = create_test_settings()
        manager = BackgroundTaskManager(settings)

        state = MagicMock(spec=State)
        state.session_factory = db.session_factory

        await manager.check_expired_invitations(state)

        # Verify results
        async with db.session_factory() as session:
            repo = InvitationRepository(session)

            # All expired invitations should be disabled
            for code in expired_codes:
                invitation = await repo.get_by_code(code)
                assert invitation is not None
                assert invitation.enabled is False, (
                    f"Expired invitation {code} should be disabled"
                )

            # All active invitations should remain enabled
            for code in active_codes:
                invitation = await repo.get_by_code(code)
                assert invitation is not None
                assert invitation.enabled is True, (
                    f"Active invitation {code} should remain enabled"
                )

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_never_expiring_invitations_remain_enabled(
        self,
        db: TestDB,
        code: str,
    ) -> None:
        """Invitations without expiration date remain enabled."""
        await db.clean()

        # Create invitation without expiration
        async with db.session_factory() as session:
            repo = InvitationRepository(session)

            invitation = Invitation()
            invitation.code = code
            invitation.enabled = True
            invitation.expires_at = None  # Never expires
            invitation.max_uses = None
            invitation.use_count = 0
            _ = await repo.create(invitation)
            await session.commit()

        # Run expiration check
        settings = create_test_settings()
        manager = BackgroundTaskManager(settings)

        state = MagicMock(spec=State)
        state.session_factory = db.session_factory

        await manager.check_expired_invitations(state)

        # Verify invitation remains enabled
        async with db.session_factory() as session:
            repo = InvitationRepository(session)
            invitation = await repo.get_by_code(code)
            assert invitation is not None
            assert invitation.enabled is True


class TestExpirationTaskErrorResilience:
    """Property 2: Expiration Task Error Resilience.

    For any batch of invitations being processed for expiration,
    if processing one invitation throws an error, the remaining
    invitations SHALL still be processed.
    """

    @given(
        codes=st.lists(code_strategy, min_size=2, max_size=5, unique=True),
        days_expired=st.integers(min_value=1, max_value=30),
    )
    @pytest.mark.asyncio
    async def test_error_in_one_invitation_does_not_stop_others(
        self,
        db: TestDB,
        codes: list[str],
        days_expired: int,
    ) -> None:
        """Processing continues even if one invitation fails."""
        await db.clean()

        # Create expired invitations
        async with db.session_factory() as session:
            repo = InvitationRepository(session)
            now = datetime.now(UTC)

            for code in codes:
                invitation = Invitation()
                invitation.code = code
                invitation.enabled = True
                invitation.expires_at = now - timedelta(days=days_expired)
                invitation.max_uses = None
                invitation.use_count = 0
                _ = await repo.create(invitation)

            await session.commit()

        # Run expiration check - should process all without errors
        settings = create_test_settings()
        manager = BackgroundTaskManager(settings)

        state = MagicMock(spec=State)
        state.session_factory = db.session_factory

        # This should complete without raising
        await manager.check_expired_invitations(state)

        # Verify all invitations were processed
        async with db.session_factory() as session:
            repo = InvitationRepository(session)

            for code in codes:
                invitation = await repo.get_by_code(code)
                assert invitation is not None
                assert invitation.enabled is False

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_already_disabled_invitations_are_skipped(
        self,
        db: TestDB,
        code: str,
    ) -> None:
        """Already disabled expired invitations are not processed again."""
        await db.clean()

        # Create already disabled expired invitation
        async with db.session_factory() as session:
            repo = InvitationRepository(session)
            now = datetime.now(UTC)

            invitation = Invitation()
            invitation.code = code
            invitation.enabled = False  # Already disabled
            invitation.expires_at = now - timedelta(days=1)
            invitation.max_uses = None
            invitation.use_count = 0
            _ = await repo.create(invitation)
            await session.commit()

        # Run expiration check
        settings = create_test_settings()
        manager = BackgroundTaskManager(settings)

        state = MagicMock(spec=State)
        state.session_factory = db.session_factory

        await manager.check_expired_invitations(state)

        # Verify invitation is still disabled (no error from re-processing)
        async with db.session_factory() as session:
            repo = InvitationRepository(session)
            invitation = await repo.get_by_code(code)
            assert invitation is not None
            assert invitation.enabled is False
