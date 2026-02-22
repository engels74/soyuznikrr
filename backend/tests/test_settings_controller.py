"""Tests for SettingsController HTTP endpoints.

Integration tests via TestClient following test_env_credentials.py pattern.
"""

from collections.abc import AsyncGenerator

import pytest
from litestar import Litestar
from litestar.datastructures import State
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.errors import validation_error_handler
from zondarr.api.settings import SettingsController
from zondarr.config import Settings
from zondarr.core.exceptions import ValidationError
from zondarr.models.app_setting import AppSetting


def _make_test_settings(csrf_origin: str | None = None) -> Settings:
    """Create a Settings instance for testing."""
    return Settings(secret_key="a" * 32, csrf_origin=csrf_origin)


def _make_test_app(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> Litestar:
    """Create a Litestar test app with the SettingsController."""

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def provide_settings_fn(state: State) -> Settings:
        return state.settings  # pyright: ignore[reportAny]

    return Litestar(
        route_handlers=[SettingsController],
        state=State({"settings": settings}),
        dependencies={
            "session": Provide(provide_session),
            "settings": Provide(provide_settings_fn, sync_to_thread=False),
        },
        exception_handlers={ValidationError: validation_error_handler},
    )


class TestGetCsrfOriginEndpoint:
    """Tests for GET /api/v1/settings/csrf-origin."""

    @pytest.mark.asyncio
    async def test_returns_null_when_not_configured(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_test_app(session_factory, _make_test_settings())

            with TestClient(app) as client:
                response = client.get("/api/v1/settings/csrf-origin")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["csrf_origin"] is None
                assert data["is_locked"] is False
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_returns_env_var_as_locked(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_test_settings(csrf_origin="https://env.example.com")
            app = _make_test_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.get("/api/v1/settings/csrf-origin")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["csrf_origin"] == "https://env.example.com"
                assert data["is_locked"] is True
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_returns_db_value_as_unlocked(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            # Insert DB row directly
            async with session_factory() as session:
                session.add(
                    AppSetting(key="csrf_origin", value="https://db.example.com")
                )
                await session.commit()

            app = _make_test_app(session_factory, _make_test_settings())

            with TestClient(app) as client:
                response = client.get("/api/v1/settings/csrf-origin")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["csrf_origin"] == "https://db.example.com"
                assert data["is_locked"] is False
        finally:
            await engine.dispose()


class TestUpdateCsrfOriginEndpoint:
    """Tests for PUT /api/v1/settings/csrf-origin."""

    @pytest.mark.asyncio
    async def test_set_csrf_origin(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_test_app(session_factory, _make_test_settings())

            with TestClient(app) as client:
                response = client.put(
                    "/api/v1/settings/csrf-origin",
                    json={"csrf_origin": "https://new.com"},
                )
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["csrf_origin"] == "https://new.com"
                assert data["is_locked"] is False
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_clear_csrf_origin(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_test_app(session_factory, _make_test_settings())

            with TestClient(app) as client:
                # Set first
                _ = client.put(
                    "/api/v1/settings/csrf-origin",
                    json={"csrf_origin": "https://set.com"},
                )
                # Clear
                response = client.put(
                    "/api/v1/settings/csrf-origin",
                    json={"csrf_origin": None},
                )
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["csrf_origin"] is None
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_locked_by_env_returns_validation_error(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_test_settings(csrf_origin="https://locked.com")
            app = _make_test_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.put(
                    "/api/v1/settings/csrf-origin",
                    json={"csrf_origin": "https://new.com"},
                )
                assert response.status_code == 400
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["error_code"] == "VALIDATION_ERROR"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_set_then_get_round_trip(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_test_app(session_factory, _make_test_settings())

            with TestClient(app) as client:
                _ = client.put(
                    "/api/v1/settings/csrf-origin",
                    json={"csrf_origin": "https://round.trip"},
                )
                response = client.get("/api/v1/settings/csrf-origin")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["csrf_origin"] == "https://round.trip"
                assert data["is_locked"] is False
        finally:
            await engine.dispose()
