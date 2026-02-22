"""Tests for SettingsService business logic.

Tests the env-var-overrides-DB pattern for CSRF origin settings.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.config import Settings
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.settings import SettingsService


def _make_settings(csrf_origin: str | None = None) -> Settings:
    """Create a Settings instance for testing."""
    return Settings(secret_key="a" * 32, csrf_origin=csrf_origin)


class TestGetCsrfOrigin:
    """Tests for SettingsService.get_csrf_origin."""

    @pytest.mark.asyncio
    async def test_returns_env_var_when_set(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        service = SettingsService(
            repo, settings=_make_settings(csrf_origin="https://x.com")
        )

        origin, is_locked = await service.get_csrf_origin()
        assert origin == "https://x.com"
        assert is_locked is True

    @pytest.mark.asyncio
    async def test_returns_db_value_when_no_env(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        _ = await repo.upsert("csrf_origin", "https://db.com")

        service = SettingsService(repo, settings=_make_settings())
        origin, is_locked = await service.get_csrf_origin()
        assert origin == "https://db.com"
        assert is_locked is False

    @pytest.mark.asyncio
    async def test_returns_none_when_nothing_configured(
        self, session: AsyncSession
    ) -> None:
        repo = AppSettingRepository(session)
        service = SettingsService(repo, settings=_make_settings())

        origin, is_locked = await service.get_csrf_origin()
        assert origin is None
        assert is_locked is False

    @pytest.mark.asyncio
    async def test_env_takes_precedence_over_db(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        _ = await repo.upsert("csrf_origin", "https://db.com")

        service = SettingsService(
            repo, settings=_make_settings(csrf_origin="https://env.com")
        )
        origin, is_locked = await service.get_csrf_origin()
        assert origin == "https://env.com"
        assert is_locked is True

    @pytest.mark.asyncio
    async def test_none_settings_falls_to_db(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        _ = await repo.upsert("csrf_origin", "https://db.com")

        service = SettingsService(repo, settings=None)
        origin, is_locked = await service.get_csrf_origin()
        assert origin == "https://db.com"
        assert is_locked is False


class TestSetCsrfOrigin:
    """Tests for SettingsService.set_csrf_origin."""

    @pytest.mark.asyncio
    async def test_set_creates_new_setting(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        service = SettingsService(repo, settings=_make_settings())

        result = await service.set_csrf_origin("https://new.com")
        assert result.key == "csrf_origin"
        assert result.value == "https://new.com"

    @pytest.mark.asyncio
    async def test_set_updates_existing_setting(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        service = SettingsService(repo, settings=_make_settings())

        _ = await service.set_csrf_origin("https://first.com")
        result = await service.set_csrf_origin("https://second.com")
        assert result.value == "https://second.com"

    @pytest.mark.asyncio
    async def test_set_none_clears_value(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        service = SettingsService(repo, settings=_make_settings())

        _ = await service.set_csrf_origin("https://set.com")
        result = await service.set_csrf_origin(None)
        assert result.value is None

    @pytest.mark.asyncio
    async def test_set_then_get_round_trip(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        service = SettingsService(repo, settings=_make_settings())

        _ = await service.set_csrf_origin("https://round.trip")
        origin, is_locked = await service.get_csrf_origin()
        assert origin == "https://round.trip"
        assert is_locked is False
