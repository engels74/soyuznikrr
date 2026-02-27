"""Tests for onboarding step state and transitions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.core.exceptions import AuthenticationError
from zondarr.repositories.admin import AdminAccountRepository
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.onboarding import ONBOARDING_STEP_KEY, OnboardingService


def _make_service(session: AsyncSession) -> OnboardingService:
    return OnboardingService(
        admin_repo=AdminAccountRepository(session),
        app_setting_repo=AppSettingRepository(session),
    )


async def _create_admin(session: AsyncSession) -> None:
    repo = AdminAccountRepository(session)
    admin = await repo.create_first_admin(
        username="admin",
        password_hash="hash",
        email=None,
        auth_method="local",
    )
    assert admin is not None
    await session.flush()


class TestGetStatus:
    """Tests for OnboardingService.get_status."""

    @pytest.mark.asyncio
    async def test_no_admin_returns_account_step(self, session: AsyncSession) -> None:
        service = _make_service(session)

        required, step = await service.get_status()

        assert required is True
        assert step == "account"

    @pytest.mark.asyncio
    async def test_existing_admin_defaults_to_security(self, session: AsyncSession) -> None:
        await _create_admin(session)
        service = _make_service(session)

        required, step = await service.get_status()

        assert required is True
        assert step == "security"

        setting = await AppSettingRepository(session).get_by_key(ONBOARDING_STEP_KEY)
        assert setting is not None
        assert setting.value == "security"

    @pytest.mark.asyncio
    async def test_existing_admin_uses_persisted_step(self, session: AsyncSession) -> None:
        await _create_admin(session)
        repo = AppSettingRepository(session)
        _ = await repo.upsert(ONBOARDING_STEP_KEY, "complete")
        service = _make_service(session)

        required, step = await service.get_status()

        assert required is False
        assert step == "complete"


class TestTransitions:
    """Tests for onboarding transition methods."""

    @pytest.mark.asyncio
    async def test_initialize_after_admin_setup_sets_security(
        self, session: AsyncSession
    ) -> None:
        await _create_admin(session)
        service = _make_service(session)

        await service.initialize_after_admin_setup()
        required, step = await service.get_status()

        assert required is True
        assert step == "security"

    @pytest.mark.asyncio
    async def test_advance_skip_step_transitions_security_then_complete(
        self, session: AsyncSession
    ) -> None:
        await _create_admin(session)
        service = _make_service(session)

        first = await service.advance_skip_step()
        second = await service.advance_skip_step()
        third = await service.advance_skip_step()

        assert first == "server"
        assert second == "complete"
        assert third == "complete"

    @pytest.mark.asyncio
    async def test_advance_skip_step_requires_admin(self, session: AsyncSession) -> None:
        service = _make_service(session)

        with pytest.raises(AuthenticationError, match="Admin setup is required"):
            _ = await service.advance_skip_step()

    @pytest.mark.asyncio
    async def test_complete_security_only_advances_from_security(
        self, session: AsyncSession
    ) -> None:
        await _create_admin(session)
        repo = AppSettingRepository(session)
        _ = await repo.upsert(ONBOARDING_STEP_KEY, "server")
        service = _make_service(session)

        step = await service.complete_security_step()

        assert step == "server"

    @pytest.mark.asyncio
    async def test_complete_server_only_advances_from_server(
        self, session: AsyncSession
    ) -> None:
        await _create_admin(session)
        repo = AppSettingRepository(session)
        _ = await repo.upsert(ONBOARDING_STEP_KEY, "security")
        service = _make_service(session)

        step = await service.complete_server_step()

        assert step == "security"
