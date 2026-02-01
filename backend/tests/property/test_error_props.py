"""Property-based tests for error handling.

Feature: zondarr-foundation
Property: 13
Validates: Requirements 9.2, 9.3, 9.4, 9.5, 9.6
"""

import re
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from litestar import Litestar, get
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from zondarr.api.errors import (
    internal_error_handler,
    not_found_handler,
    validation_error_handler,
)
from zondarr.api.health import HealthController
from zondarr.core.exceptions import NotFoundError, ValidationError
from zondarr.models.base import Base

# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


async def create_test_engine() -> AsyncEngine:
    """Create an async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(  # pyright: ignore[reportUnusedFunction]
        dbapi_connection: Any,  # pyright: ignore[reportExplicitAny,reportAny]
        connection_record: Any,  # pyright: ignore[reportExplicitAny,reportUnusedParameter,reportAny]
    ) -> None:
        cursor = dbapi_connection.cursor()  # pyright: ignore[reportAny]
        cursor.execute("PRAGMA foreign_keys=ON")  # pyright: ignore[reportAny]
        cursor.close()  # pyright: ignore[reportAny]

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return engine


def create_test_app_with_error_routes(
    session_factory: async_sessionmaker[AsyncSession],
) -> Litestar:
    """Create a test Litestar app with error-triggering routes."""

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            yield session

    @get("/trigger-validation-error")
    async def trigger_validation_error(
        fields: str = "field1,field2",
    ) -> dict[str, str]:
        """Trigger a validation error with specified fields."""
        field_errors: dict[str, list[str]] = {}
        for field in fields.split(","):
            field_errors[field.strip()] = [f"Invalid value for {field.strip()}"]
        raise ValidationError("Validation failed", field_errors=field_errors)

    @get("/trigger-not-found/{resource_type:str}/{identifier:str}")
    async def trigger_not_found(
        resource_type: str,
        identifier: str,
    ) -> dict[str, str]:
        """Trigger a not found error with specified resource info."""
        raise NotFoundError(resource_type, identifier)

    @get("/trigger-internal-error")
    async def trigger_internal_error() -> dict[str, str]:
        """Trigger an internal server error."""
        raise RuntimeError(
            "Simulated internal error with sensitive info: /path/to/file"
        )

    return Litestar(
        route_handlers=[
            HealthController,
            trigger_validation_error,
            trigger_not_found,
            trigger_internal_error,
        ],
        dependencies={"session": Provide(provide_session)},
        exception_handlers={
            ValidationError: validation_error_handler,
            NotFoundError: not_found_handler,
            Exception: internal_error_handler,
        },
    )


# Strategies for generating test data
field_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_"),
    min_size=1,
    max_size=30,
)

resource_type_strategy = st.sampled_from(
    ["User", "MediaServer", "Invitation", "Identity", "Library"]
)

identifier_strategy = st.one_of(
    st.uuids().map(str),
    st.text(
        min_size=1,
        max_size=50,
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-_"),
    ),
)

# Patterns that should NEVER appear in error responses (security)
FORBIDDEN_PATTERNS = [
    r"Traceback \(most recent call last\)",  # Stack traces
    r"File \".*\.py\"",  # File paths
    r"line \d+",  # Line numbers
    r"/home/",  # Home directory paths
    r"/usr/",  # System paths
    r"/var/",  # Var paths
    r"\.py:",  # Python file references
    r"Exception:",  # Raw exception types
    r"RuntimeError:",  # Raw runtime errors
    r"at 0x[0-9a-fA-F]+",  # Memory addresses
]


def response_is_safe(response_text: str) -> bool:
    """Check that response doesn't contain sensitive information."""
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, response_text):
            return False
    return True


# =============================================================================
# Property Tests
# =============================================================================


class TestErrorResponsesAreSafeAndTraceable:
    """
    Feature: zondarr-foundation
    Property 13: Error Responses Are Safe and Traceable

    *For any* error response:
    - Validation errors (400) SHALL include field-level details
    - Not found errors (404) SHALL include resource type and identifier
    - Internal errors (500) SHALL include a correlation ID
    - No error response SHALL contain stack traces, file paths, or internal implementation details

    **Validates: Requirements 9.2, 9.3, 9.4, 9.5, 9.6**
    """

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        field_names=st.lists(field_name_strategy, min_size=1, max_size=5, unique=True),
    )
    @pytest.mark.asyncio
    async def test_validation_errors_include_field_details(
        self, field_names: list[str]
    ) -> None:
        """Validation errors (400) SHALL include field-level details.

        **Validates: Requirement 9.2**
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                fields_param = ",".join(field_names)
                response = client.get(
                    f"/trigger-validation-error?fields={fields_param}"
                )

                # Should return 400
                assert response.status_code == 400

                data = response.json()  # pyright: ignore[reportAny]

                # Should have standard error structure
                assert "detail" in data
                assert "error_code" in data
                assert "timestamp" in data
                assert data["error_code"] == "VALIDATION_ERROR"

                # Should have field-level errors
                assert "field_errors" in data
                field_errors: list[dict[str, object]] = data["field_errors"]  # pyright: ignore[reportAny]
                assert isinstance(field_errors, list)

                # Each requested field should have an error entry
                error_fields: set[str] = {str(fe["field"]) for fe in field_errors}
                for field_name in field_names:
                    assert field_name in error_fields

                # Should have correlation ID for traceability
                assert "correlation_id" in data
                assert data["correlation_id"] is not None

                # Response should be safe (no internal details)
                assert response_is_safe(response.text)
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        resource_type=resource_type_strategy,
        identifier=identifier_strategy,
    )
    @pytest.mark.asyncio
    async def test_not_found_errors_include_resource_info(
        self, resource_type: str, identifier: str
    ) -> None:
        """Not found errors (404) SHALL include resource type and identifier.

        **Validates: Requirement 9.3**
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                response = client.get(
                    f"/trigger-not-found/{resource_type}/{identifier}"
                )

                # Should return 404
                assert response.status_code == 404

                data = response.json()  # pyright: ignore[reportAny]

                # Should have standard error structure
                assert "detail" in data
                assert "error_code" in data
                assert "timestamp" in data
                assert data["error_code"] == "NOT_FOUND"

                # Detail should mention resource type and identifier
                detail = data["detail"]  # pyright: ignore[reportAny]
                assert resource_type in detail
                assert identifier in detail

                # Should have correlation ID for traceability
                assert "correlation_id" in data
                assert data["correlation_id"] is not None

                # Response should be safe (no internal details)
                assert response_is_safe(response.text)
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        num_requests=st.integers(min_value=1, max_value=10),
    )
    @pytest.mark.asyncio
    async def test_internal_errors_include_correlation_id(
        self, num_requests: int
    ) -> None:
        """Internal errors (500) SHALL include a correlation ID.

        **Validates: Requirement 9.4**
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                correlation_ids: set[str] = set()

                for _ in range(num_requests):
                    response = client.get("/trigger-internal-error")

                    # Should return 500
                    assert response.status_code == 500

                    data = response.json()  # pyright: ignore[reportAny]

                    # Should have standard error structure
                    assert "detail" in data
                    assert "error_code" in data
                    assert "timestamp" in data
                    assert data["error_code"] == "INTERNAL_ERROR"

                    # Should have correlation ID for traceability
                    assert "correlation_id" in data
                    correlation_id: str = str(data["correlation_id"])  # pyright: ignore[reportAny]
                    assert correlation_id is not None

                    # Correlation ID should be a valid UUID
                    _ = UUID(correlation_id)  # Raises if invalid

                    # Each request should get a unique correlation ID
                    assert correlation_id not in correlation_ids
                    correlation_ids.add(correlation_id)
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        num_requests=st.integers(min_value=1, max_value=5),
    )
    @pytest.mark.asyncio
    async def test_internal_errors_never_expose_details(
        self, num_requests: int
    ) -> None:
        """Internal errors SHALL NOT contain stack traces, file paths, or internal details.

        **Validates: Requirements 9.5, 9.6**
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                for _ in range(num_requests):
                    response = client.get("/trigger-internal-error")

                    # Should return 500
                    assert response.status_code == 500

                    data = response.json()  # pyright: ignore[reportAny]

                    # Detail should be generic, not exposing internal info
                    detail = data["detail"]  # pyright: ignore[reportAny]
                    assert detail == "An internal error occurred"

                    # The original error message should NOT appear
                    assert "Simulated internal error" not in detail
                    assert "/path/to/file" not in detail

                    # Full response should be safe
                    assert response_is_safe(response.text)
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        field_names=st.lists(field_name_strategy, min_size=1, max_size=3, unique=True),
    )
    @pytest.mark.asyncio
    async def test_validation_errors_are_safe(self, field_names: list[str]) -> None:
        """Validation error responses SHALL NOT contain internal details.

        **Validates: Requirements 9.5, 9.6**
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                fields_param = ",".join(field_names)
                response = client.get(
                    f"/trigger-validation-error?fields={fields_param}"
                )

                assert response.status_code == 400

                # Full response should be safe
                assert response_is_safe(response.text)

                # Should have valid timestamp
                data = response.json()  # pyright: ignore[reportAny]
                timestamp_str: str = str(data["timestamp"])  # pyright: ignore[reportAny]
                # Should be parseable as ISO datetime
                _ = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        resource_type=resource_type_strategy,
        identifier=identifier_strategy,
    )
    @pytest.mark.asyncio
    async def test_not_found_errors_are_safe(
        self, resource_type: str, identifier: str
    ) -> None:
        """Not found error responses SHALL NOT contain internal details.

        **Validates: Requirements 9.5, 9.6**
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                response = client.get(
                    f"/trigger-not-found/{resource_type}/{identifier}"
                )

                assert response.status_code == 404

                # Full response should be safe
                assert response_is_safe(response.text)

                # Should have valid timestamp
                data = response.json()  # pyright: ignore[reportAny]
                timestamp_str: str = str(data["timestamp"])  # pyright: ignore[reportAny]
                # Should be parseable as ISO datetime
                _ = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        error_type=st.sampled_from(["validation", "not_found", "internal"]),
    )
    @pytest.mark.asyncio
    async def test_all_errors_have_correlation_ids(self, error_type: str) -> None:
        """All error responses SHALL include correlation IDs for traceability.

        **Validates: Requirement 9.5**
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                if error_type == "validation":
                    response = client.get("/trigger-validation-error?fields=test_field")
                    expected_status = 400
                elif error_type == "not_found":
                    response = client.get("/trigger-not-found/TestResource/test-id")
                    expected_status = 404
                else:  # internal
                    response = client.get("/trigger-internal-error")
                    expected_status = 500

                assert response.status_code == expected_status

                data = response.json()  # pyright: ignore[reportAny]

                # All error types should have correlation ID
                assert "correlation_id" in data
                correlation_id: str = str(data["correlation_id"])  # pyright: ignore[reportAny]
                assert correlation_id is not None

                # Should be a valid UUID
                _ = UUID(correlation_id)
        finally:
            await engine.dispose()

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        error_type=st.sampled_from(["validation", "not_found", "internal"]),
    )
    @pytest.mark.asyncio
    async def test_all_errors_have_timestamps(self, error_type: str) -> None:
        """All error responses SHALL include timestamps.

        **Validates: Requirement 9.1**
        """
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                if error_type == "validation":
                    response = client.get("/trigger-validation-error?fields=test_field")
                elif error_type == "not_found":
                    response = client.get("/trigger-not-found/TestResource/test-id")
                else:  # internal
                    response = client.get("/trigger-internal-error")

                data = response.json()  # pyright: ignore[reportAny]

                # All error types should have timestamp
                assert "timestamp" in data
                timestamp_str: str = str(data["timestamp"])  # pyright: ignore[reportAny]
                assert timestamp_str is not None

                # Should be parseable as ISO datetime
                parsed = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                assert parsed is not None
        finally:
            await engine.dispose()
