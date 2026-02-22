"""Tests for AppSettingRepository CRUD operations.

Tests get_by_key and upsert methods against in-memory SQLite.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.models.app_setting import AppSetting
from zondarr.repositories.app_setting import AppSettingRepository


class TestGetByKey:
    """Tests for AppSettingRepository.get_by_key."""

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_key(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        result = await repo.get_by_key("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_setting_for_existing_key(
        self, session: AsyncSession
    ) -> None:
        setting = AppSetting(key="test_key", value="test_value")
        session.add(setting)
        await session.flush()

        repo = AppSettingRepository(session)
        result = await repo.get_by_key("test_key")
        assert result is not None
        assert result.key == "test_key"
        assert result.value == "test_value"

    @pytest.mark.asyncio
    async def test_returns_setting_with_null_value(self, session: AsyncSession) -> None:
        setting = AppSetting(key="null_key", value=None)
        session.add(setting)
        await session.flush()

        repo = AppSettingRepository(session)
        result = await repo.get_by_key("null_key")
        assert result is not None
        assert result.key == "null_key"
        assert result.value is None


class TestUpsert:
    """Tests for AppSettingRepository.upsert."""

    @pytest.mark.asyncio
    async def test_creates_new_setting(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        result = await repo.upsert("new_key", "new_value")

        assert result.key == "new_key"
        assert result.value == "new_value"

        fetched = await repo.get_by_key("new_key")
        assert fetched is not None
        assert fetched.value == "new_value"

    @pytest.mark.asyncio
    async def test_updates_existing_setting(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        _ = await repo.upsert("key", "first")
        result = await repo.upsert("key", "second")

        assert result.value == "second"

        fetched = await repo.get_by_key("key")
        assert fetched is not None
        assert fetched.value == "second"

    @pytest.mark.asyncio
    async def test_upsert_with_none_value(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        result = await repo.upsert("k", None)

        assert result.key == "k"
        assert result.value is None

    @pytest.mark.asyncio
    async def test_upsert_update_to_none(self, session: AsyncSession) -> None:
        repo = AppSettingRepository(session)
        _ = await repo.upsert("k", "has_value")
        result = await repo.upsert("k", None)

        assert result.value is None

        fetched = await repo.get_by_key("k")
        assert fetched is not None
        assert fetched.value is None
