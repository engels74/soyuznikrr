"""Property-based tests for error handling.

Feature: zondarr-foundation
Property: 13
Validates: Requirements 9.2, 9.3, 9.4, 9.5, 9.6
"""

import re
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st
from litestar import Litestar, get
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.errors import (
    internal_error_handler,
    not_found_handler,
    validation_error_handler,
)
from zondarr.api.health import HealthController
from zondarr.core.exceptions import NotFoundError, ValidationError


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
    r"Traceback \(most recent call last\)",
    r"File \".*\.py\"",
    r"line \d+",
    r"/home/",
    r"/usr/",
    r"/var/",
    r"\.py:",
    r"Exception:",
    r"RuntimeError:",
    r"at 0x[0-9a-fA-F]+",
]


def response_is_safe(response_text: str) -> bool:
    """Check that response doesn't contain sensitive information."""
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, response_text):
            return False
    return True


class TestErrorResponsesAreSafeAndTraceable:
    """
    Feature: zondarr-foundation
    Property 13: Error Responses Are Safe and Traceable

    **Validates: Requirements 9.2, 9.3, 9.4, 9.5, 9.6**
    """

    @given(
        field_names=st.lists(field_name_strategy, min_size=1, max_size=3, unique=True),
    )
    @pytest.mark.asyncio
    async def test_validation_errors_include_field_details(
        self,
        field_names: list[str],
    ) -> None:
        """Validation errors (400) SHALL include field-level details."""
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
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

                assert "detail" in data
                assert "error_code" in data
                assert data["error_code"] == "VALIDATION_ERROR"
                assert "field_errors" in data
                assert "correlation_id" in data
                assert response_is_safe(response.text)
        finally:
            await engine.dispose()

    @given(
        resource_type=resource_type_strategy,
        identifier=identifier_strategy,
    )
    @pytest.mark.asyncio
    async def test_not_found_errors_include_resource_info(
        self,
        resource_type: str,
        identifier: str,
    ) -> None:
        """Not found errors (404) SHALL include resource type and identifier."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                response = client.get(
                    f"/trigger-not-found/{resource_type}/{identifier}"
                )

                assert response.status_code == 404
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

                assert "detail" in data
                assert "error_code" in data
                assert data["error_code"] == "NOT_FOUND"
                assert resource_type in str(data["detail"])
                assert identifier in str(data["detail"])
                assert "correlation_id" in data
                assert response_is_safe(response.text)
        finally:
            await engine.dispose()

    @given(num_requests=st.integers(min_value=1, max_value=5))
    @pytest.mark.asyncio
    async def test_internal_errors_include_correlation_id(
        self,
        num_requests: int,
    ) -> None:
        """Internal errors (500) SHALL include a correlation ID."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                correlation_ids: set[str] = set()

                for _ in range(num_requests):
                    response = client.get("/trigger-internal-error")

                    assert response.status_code == 500
                    data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

                    assert "correlation_id" in data
                    correlation_id = str(data["correlation_id"])
                    _ = UUID(correlation_id)  # Validates UUID format

                    assert correlation_id not in correlation_ids
                    correlation_ids.add(correlation_id)
        finally:
            await engine.dispose()

    @given(num_requests=st.integers(min_value=1, max_value=3))
    @pytest.mark.asyncio
    async def test_internal_errors_never_expose_details(
        self,
        num_requests: int,
    ) -> None:
        """Internal errors SHALL NOT contain stack traces or internal details."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                for _ in range(num_requests):
                    response = client.get("/trigger-internal-error")

                    assert response.status_code == 500
                    data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

                    assert data["detail"] == "An internal error occurred"
                    assert "Simulated internal error" not in str(data["detail"])
                    assert "/path/to/file" not in str(data["detail"])
                    assert response_is_safe(response.text)
        finally:
            await engine.dispose()

    @given(error_type=st.sampled_from(["validation", "not_found", "internal"]))
    @pytest.mark.asyncio
    async def test_all_errors_have_timestamps(
        self,
        error_type: str,
    ) -> None:
        """All error responses SHALL include timestamps."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = create_test_app_with_error_routes(session_factory)

            with TestClient(app) as client:
                if error_type == "validation":
                    response = client.get("/trigger-validation-error?fields=test_field")
                elif error_type == "not_found":
                    response = client.get("/trigger-not-found/TestResource/test-id")
                else:
                    response = client.get("/trigger-internal-error")

                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

                assert "timestamp" in data
                timestamp_str = str(data["timestamp"])
                _ = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        finally:
            await engine.dispose()
