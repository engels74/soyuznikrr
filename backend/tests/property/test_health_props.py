"""Property-based tests for health endpoints.

Feature: zondarr-foundation
Property: 12
Validates: Requirements 8.4, 8.5, 8.6, 8.7
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st
from litestar import Litestar
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.health import HealthController


def create_test_app(session_factory: async_sessionmaker[AsyncSession]) -> Litestar:
    """Create a test Litestar app with the health controller."""

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            yield session

    return Litestar(
        route_handlers=[HealthController],
        dependencies={"session": Provide(provide_session)},
    )


class TestHealthEndpointsReturnCorrectStatus:
    """
    Feature: zondarr-foundation
    Property 12: Health Endpoints Return Correct Status

    **Validates: Requirements 8.4, 8.5, 8.6, 8.7**
    """

    @given(num_requests=st.integers(min_value=1, max_value=5))
    @pytest.mark.asyncio
    async def test_liveness_always_returns_200(
        self,
        num_requests: int,
    ) -> None:
        """Liveness probe always returns HTTP 200 if process is running."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app(session_factory)

            with TestClient(app) as client:
                for _ in range(num_requests):
                    response = client.get("/health/live")
                    assert response.status_code == 200
                    assert response.json()["status"] == "alive"
        finally:
            await engine.dispose()

    @given(num_requests=st.integers(min_value=1, max_value=5))
    @pytest.mark.asyncio
    async def test_health_returns_200_when_database_healthy(
        self,
        num_requests: int,
    ) -> None:
        """Health endpoint returns HTTP 200 with status "healthy" when database is reachable."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app(session_factory)

            with TestClient(app) as client:
                for _ in range(num_requests):
                    response = client.get("/health")
                    assert response.status_code == 200
                    assert response.json()["status"] == "healthy"
                    assert response.json()["checks"]["database"] is True
        finally:
            await engine.dispose()

    @given(num_requests=st.integers(min_value=1, max_value=5))
    @pytest.mark.asyncio
    async def test_health_returns_503_when_database_unhealthy(
        self,
        num_requests: int,
    ) -> None:
        """Health endpoint returns HTTP 503 with status "degraded" when database is unreachable."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app(session_factory)

            with TestClient(app) as client:
                with patch.object(
                    HealthController,
                    "_check_database",
                    new_callable=AsyncMock,
                    return_value=False,
                ):
                    for _ in range(num_requests):
                        response = client.get("/health")
                        assert response.status_code == 503
                        assert response.json()["status"] == "degraded"
                        assert response.json()["checks"]["database"] is False
        finally:
            await engine.dispose()

    @given(num_requests=st.integers(min_value=1, max_value=5))
    @pytest.mark.asyncio
    async def test_readiness_returns_200_when_database_healthy(
        self,
        num_requests: int,
    ) -> None:
        """Readiness probe returns HTTP 200 when database is reachable."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app(session_factory)

            with TestClient(app) as client:
                for _ in range(num_requests):
                    response = client.get("/health/ready")
                    assert response.status_code == 200
                    assert response.json()["status"] == "ready"
        finally:
            await engine.dispose()

    @given(num_requests=st.integers(min_value=1, max_value=5))
    @pytest.mark.asyncio
    async def test_readiness_returns_503_when_database_unhealthy(
        self,
        num_requests: int,
    ) -> None:
        """Readiness probe returns HTTP 503 when database is unreachable."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app(session_factory)

            with TestClient(app) as client:
                with patch.object(
                    HealthController,
                    "_check_database",
                    new_callable=AsyncMock,
                    return_value=False,
                ):
                    for _ in range(num_requests):
                        response = client.get("/health/ready")
                        assert response.status_code == 503
                        assert response.json()["status"] == "not ready"
        finally:
            await engine.dispose()

    @given(db_healthy=st.booleans())
    @pytest.mark.asyncio
    async def test_health_status_matches_dependency_state(
        self,
        db_healthy: bool,
    ) -> None:
        """Health status correctly reflects dependency state."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app(session_factory)

            with TestClient(app) as client:
                with patch.object(
                    HealthController,
                    "_check_database",
                    new_callable=AsyncMock,
                    return_value=db_healthy,
                ):
                    response = client.get("/health")

                    if db_healthy:
                        assert response.status_code == 200
                        assert response.json()["status"] == "healthy"
                    else:
                        assert response.status_code == 503
                        assert response.json()["status"] == "degraded"

                    assert response.json()["checks"]["database"] is db_healthy
        finally:
            await engine.dispose()

    @given(db_healthy=st.booleans())
    @pytest.mark.asyncio
    async def test_liveness_independent_of_database_state(
        self,
        db_healthy: bool,
    ) -> None:
        """Liveness probe returns 200 regardless of database state."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app(session_factory)

            with TestClient(app) as client:
                with patch.object(
                    HealthController,
                    "_check_database",
                    new_callable=AsyncMock,
                    return_value=db_healthy,
                ):
                    response = client.get("/health/live")
                    assert response.status_code == 200
                    assert response.json()["status"] == "alive"
        finally:
            await engine.dispose()
