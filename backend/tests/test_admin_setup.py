"""Tests for admin setup race condition fix.

Tests:
- AdminAccountRepository.create_first_admin (atomic INSERT ... WHERE NOT EXISTS)
- AuthService.setup_admin (lock + atomic DB call)
- Concurrent setup attempts (only one wins)
"""

import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.core.exceptions import AuthenticationError
from zondarr.models.admin import AdminAccount
from zondarr.repositories.admin import AdminAccountRepository, RefreshTokenRepository
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.auth import AuthService

# =============================================================================
# Repository: create_first_admin
# =============================================================================


class TestCreateFirstAdmin:
    """Tests for AdminAccountRepository.create_first_admin."""

    @pytest.mark.asyncio
    async def test_creates_admin_when_table_empty(self) -> None:
        """Returns an AdminAccount with correct fields when table is empty."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = AdminAccountRepository(session)
                admin = await repo.create_first_admin(
                    username="admin",
                    password_hash="hashed_pw",
                    email="admin@example.com",
                    auth_method="local",
                )
                await session.commit()

                assert admin is not None
                assert admin.username == "admin"
                assert admin.password_hash == "hashed_pw"  # noqa: S105
                assert admin.email == "admin@example.com"
                assert admin.auth_method == "local"
                assert admin.enabled is True
                assert admin.id is not None
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_returns_none_when_admin_exists(self) -> None:
        """Returns None on second call; DB still has exactly 1 admin."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = AdminAccountRepository(session)
                first = await repo.create_first_admin(
                    username="admin1",
                    password_hash="hash1",
                    email=None,
                    auth_method="local",
                )
                await session.commit()
                assert first is not None

            async with session_factory() as session:
                repo = AdminAccountRepository(session)
                second = await repo.create_first_admin(
                    username="admin2",
                    password_hash="hash2",
                    email=None,
                    auth_method="local",
                )
                await session.commit()
                assert second is None

                # Verify only one admin exists
                count = await _count_admins(session)
                assert count == 1
        finally:
            await engine.dispose()


# =============================================================================
# Service: setup_admin
# =============================================================================


class TestSetupAdmin:
    """Tests for AuthService.setup_admin."""

    @pytest.mark.asyncio
    async def test_setup_admin_succeeds(self) -> None:
        """First call returns an admin with correct username."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                service = _make_service(session)
                admin = await service.setup_admin("myadmin", "strong_password")
                await session.commit()

                assert admin.username == "myadmin"
                assert admin.auth_method == "local"
                assert admin.password_hash is not None
                assert admin.password_hash != "strong_password"  # noqa: S105
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_setup_admin_rejects_second_call(self) -> None:
        """Second call raises AuthenticationError with SETUP_NOT_REQUIRED."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                service = _make_service(session)
                _ = await service.setup_admin("admin1", "password1")
                await session.commit()

            async with session_factory() as session:
                service = _make_service(session)
                with pytest.raises(
                    AuthenticationError, match="Setup already completed"
                ):
                    _ = await service.setup_admin("admin2", "password2")
        finally:
            await engine.dispose()


# =============================================================================
# Concurrency: only one setup wins
# =============================================================================


class TestConcurrentSetup:
    """Tests for concurrent setup_admin calls."""

    @pytest.mark.asyncio
    async def test_concurrent_setup_only_one_wins(self) -> None:
        """N concurrent setup_admin calls: exactly 1 succeeds, rest fail."""
        engine = await create_test_engine()
        n = 5
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async def attempt_setup(idx: int) -> AdminAccount | None:
                async with session_factory() as session:
                    service = _make_service(session)
                    try:
                        admin = await service.setup_admin(
                            f"admin{idx}", f"password{idx}"
                        )
                        await session.commit()
                        return admin
                    except AuthenticationError:
                        return None

            results = await asyncio.gather(*[attempt_setup(i) for i in range(n)])

            successes = [r for r in results if r is not None]
            failures = [r for r in results if r is None]

            assert len(successes) == 1
            assert len(failures) == n - 1

            # Verify exactly 1 admin in DB
            async with session_factory() as session:
                count = await _count_admins(session)
                assert count == 1
        finally:
            await engine.dispose()


# =============================================================================
# Helpers
# =============================================================================


def _make_service(session: AsyncSession) -> AuthService:
    return AuthService(
        admin_repo=AdminAccountRepository(session),
        token_repo=RefreshTokenRepository(session),
        app_setting_repo=AppSettingRepository(session),
    )


async def _count_admins(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(AdminAccount))
    return result.scalar_one()
