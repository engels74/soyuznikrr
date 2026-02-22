"""Tests for CSRFMiddleware and _CsrfOriginCache.

Tests origin-based CSRF protection via a Litestar app with the middleware.
"""

import time
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from litestar import Litestar, get, post
from litestar.datastructures import State
from litestar.di import Provide
from litestar.middleware import DefineMiddleware
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.config import Settings
from zondarr.core.csrf import (
    CSRFMiddleware,
    _CsrfOriginCache,  # pyright: ignore[reportPrivateUsage]
)
from zondarr.models.app_setting import AppSetting


def _make_test_settings(csrf_origin: str | None = None) -> Settings:
    """Create a Settings instance for testing."""
    return Settings(secret_key="a" * 32, csrf_origin=csrf_origin)


def _make_csrf_app(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> Litestar:
    """Create a Litestar test app with CSRF middleware and dummy handlers."""

    @get("/test-get")
    async def handle_get() -> dict[str, str]:
        return {"status": "ok"}

    @post("/test-post")
    async def handle_post() -> dict[str, str]:
        return {"status": "ok"}

    # Excluded paths
    @post("/api/auth/login")
    async def handle_login() -> dict[str, str]:
        return {"status": "ok"}

    @post("/api/v1/join/test")
    async def handle_join() -> dict[str, str]:
        return {"status": "ok"}

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            yield session

    return Litestar(
        route_handlers=[handle_get, handle_post, handle_login, handle_join],
        middleware=[DefineMiddleware(CSRFMiddleware)],
        state=State({"settings": settings, "session_factory": session_factory}),
        dependencies={"session": Provide(provide_session)},
    )


class TestCSRFSafeMethods:
    """Safe HTTP methods bypass CSRF checks."""

    @pytest.mark.asyncio
    async def test_get_bypasses_csrf(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.get("/test-get")
                assert response.status_code == 200
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_head_bypasses_csrf(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.head("/test-get")
                # HEAD may return 405 if the route doesn't support it; the key is no 403
                assert response.status_code != 403
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_options_bypasses_csrf(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.options("/test-get")
                # Litestar may return 204 or 200 for OPTIONS
                assert response.status_code < 400
        finally:
            await engine.dispose()


class TestCSRFExcludedPaths:
    """Excluded paths bypass CSRF checks."""

    @pytest.mark.asyncio
    async def test_excluded_exact_path_bypasses_csrf(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/login",
                    json={},
                    headers={"Origin": "https://evil.com"},
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_excluded_prefix_bypasses_csrf(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/join/test",
                    json={},
                    headers={"Origin": "https://evil.com"},
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()


class TestCSRFOriginValidation:
    """Tests for Origin header validation with env var CSRF origin."""

    @pytest.mark.asyncio
    async def test_matching_origin_allows_request(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Origin": "https://app.example.com"},
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_mismatching_origin_returns_403(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Origin": "https://evil.com"},
                )
                assert response.status_code == 403
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["error_code"] == "CSRF_ORIGIN_MISMATCH"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_missing_origin_header_returns_403(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post("/test-post", json={})
                assert response.status_code == 403
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_case_insensitive_comparison(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Origin": "HTTPS://APP.EXAMPLE.COM"},
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_trailing_slash_stripped(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Origin": "https://app.example.com/"},
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_null_origin_treated_as_missing(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Origin": "null"},
                )
                assert response.status_code == 403
        finally:
            await engine.dispose()


class TestCSRFOriginFromDB:
    """Tests for CSRF origin sourced from the database."""

    @pytest.mark.asyncio
    async def test_db_origin_allows_matching_request(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            # Insert csrf_origin in DB
            async with sf() as session:
                session.add(
                    AppSetting(key="csrf_origin", value="https://db.example.com")
                )
                await session.commit()

            app = _make_csrf_app(sf, _make_test_settings())

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Origin": "https://db.example.com"},
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_db_origin_rejects_mismatching_request(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            async with sf() as session:
                session.add(
                    AppSetting(key="csrf_origin", value="https://db.example.com")
                )
                await session.commit()

            app = _make_csrf_app(sf, _make_test_settings())

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Origin": "https://evil.com"},
                )
                assert response.status_code == 403
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_no_origin_configured_allows_all(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(sf, _make_test_settings())

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Origin": "https://anything.com"},
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()


class TestCSRFRefererFallback:
    """Tests for Referer header fallback when Origin is absent."""

    @pytest.mark.asyncio
    async def test_referer_used_when_origin_missing(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Referer": "https://app.example.com/dashboard"},
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_referer_with_port(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="http://app.example.com:8080")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Referer": "http://app.example.com:8080/path"},
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_referer_mismatch_returns_403(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Referer": "https://evil.com/page"},
                )
                assert response.status_code == 403
        finally:
            await engine.dispose()


class TestCsrfOriginCache:
    """Unit tests for _CsrfOriginCache."""

    def test_cache_returns_invalid_when_empty(self) -> None:
        cache = _CsrfOriginCache()
        value, is_valid = cache.get()
        assert value is None
        assert is_valid is False

    def test_cache_returns_valid_after_set(self) -> None:
        cache = _CsrfOriginCache()
        cache.set("https://cached.com")
        value, is_valid = cache.get()
        assert value == "https://cached.com"
        assert is_valid is True

    def test_cache_expires_after_ttl(self) -> None:
        cache = _CsrfOriginCache()
        cache.set("https://cached.com")

        # Advance past 60s TTL
        with patch.object(time, "monotonic", return_value=time.monotonic() + 61):
            value, is_valid = cache.get()
            assert value is None
            assert is_valid is False

    def test_cache_set_none_is_valid(self) -> None:
        cache = _CsrfOriginCache()
        cache.set(None)
        value, is_valid = cache.get()
        assert value is None
        assert is_valid is True


class TestCSRF403Response:
    """Tests for the structure of CSRF 403 responses."""

    @pytest.mark.asyncio
    async def test_403_response_is_json(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Origin": "https://evil.com"},
                )
                assert response.status_code == 403
                assert response.headers["content-type"] == "application/json"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_403_response_body_structure(self) -> None:
        engine = await create_test_engine()
        try:
            sf = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_csrf_app(
                sf, _make_test_settings(csrf_origin="https://app.example.com")
            )

            with TestClient(app) as client:
                response = client.post(
                    "/test-post",
                    json={},
                    headers={"Origin": "https://evil.com"},
                )
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert "detail" in data
                assert "error_code" in data
                assert "timestamp" in data
        finally:
            await engine.dispose()
