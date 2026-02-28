"""Property-based tests for error handling.

Feature: zondarr-foundation
Property: 13

Phase 6 Polish additions:
Property 5: Error Response Structure
Property 6: Validation Error Field Mapping
Property 7: NotFound Error Resource Identification
Property 8: External Service Error Mapping
"""

import re
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import cast
from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from litestar import Litestar, get
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import TestDB
from zondarr.api.errors import (
    external_service_error_handler,
    internal_error_handler,
    not_found_handler,
    validation_error_handler,
)
from zondarr.api.health import HealthController
from zondarr.core.exceptions import ExternalServiceError, NotFoundError, ValidationError


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

    @get("/trigger-validation-error-multi")
    async def trigger_validation_error_multi(
        fields: str = "field1,field2",
        messages_per_field: int = 1,
    ) -> dict[str, str]:
        """Trigger a validation error with multiple messages per field."""
        field_errors: dict[str, list[str]] = {}
        for field in fields.split(","):
            field_name = field.strip()
            field_errors[field_name] = [
                f"Error {i + 1} for {field_name}" for i in range(messages_per_field)
            ]
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

    @get("/trigger-external-service-error/{service_name:str}")
    async def trigger_external_service_error(
        service_name: str,
    ) -> dict[str, str]:
        """Trigger an external service error with specified service name."""
        raise ExternalServiceError(
            service_name,
            f"Failed to connect to {service_name}",
            original=ConnectionError(f"Connection refused by {service_name}"),
        )

    return Litestar(
        route_handlers=[
            HealthController,
            trigger_validation_error,
            trigger_validation_error_multi,
            trigger_not_found,
            trigger_internal_error,
            trigger_external_service_error,
        ],
        dependencies={"session": Provide(provide_session)},
        exception_handlers={
            ValidationError: validation_error_handler,
            NotFoundError: not_found_handler,
            ExternalServiceError: external_service_error_handler,
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

# Strategy for external service names
service_name_strategy = st.sampled_from(
    ["Plex", "Jellyfin", "Emby", "Audiobookshelf", "MyMediaServer"]
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
    """

    @given(
        field_names=st.lists(field_name_strategy, min_size=1, max_size=3, unique=True),
    )
    @pytest.mark.asyncio
    async def test_validation_errors_include_field_details(
        self,
        db: TestDB,
        field_names: list[str],
    ) -> None:
        """Validation errors (400) SHALL include field-level details."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            fields_param = ",".join(field_names)
            response = client.get(f"/trigger-validation-error?fields={fields_param}")

            assert response.status_code == 400
            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            assert "detail" in data
            assert "error_code" in data
            assert data["error_code"] == "VALIDATION_ERROR"
            assert "field_errors" in data
            assert "correlation_id" in data
            assert response_is_safe(response.text)

    @given(
        resource_type=resource_type_strategy,
        identifier=identifier_strategy,
    )
    @pytest.mark.asyncio
    async def test_not_found_errors_include_resource_info(
        self,
        db: TestDB,
        resource_type: str,
        identifier: str,
    ) -> None:
        """Not found errors (404) SHALL include resource type and identifier."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            response = client.get(f"/trigger-not-found/{resource_type}/{identifier}")

            assert response.status_code == 404
            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            assert "detail" in data
            assert "error_code" in data
            assert data["error_code"] == "NOT_FOUND"
            assert resource_type in str(data["detail"])
            assert identifier in str(data["detail"])
            assert "correlation_id" in data
            assert response_is_safe(response.text)

    @pytest.mark.asyncio
    async def test_internal_errors_include_correlation_id(
        self,
        db: TestDB,
    ) -> None:
        """Internal errors (500) SHALL include a correlation ID."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            correlation_ids: set[str] = set()

            for _ in range(3):
                response = client.get("/trigger-internal-error")

                assert response.status_code == 500
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

                assert "correlation_id" in data
                correlation_id = str(data["correlation_id"])
                _ = UUID(correlation_id)  # Validates UUID format

                assert correlation_id not in correlation_ids
                correlation_ids.add(correlation_id)

    @pytest.mark.asyncio
    async def test_internal_errors_never_expose_details(
        self,
        db: TestDB,
    ) -> None:
        """Internal errors SHALL NOT contain stack traces or internal details."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            for _ in range(3):
                response = client.get("/trigger-internal-error")

                assert response.status_code == 500
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

                assert data["detail"] == "An internal error occurred"
                assert "Simulated internal error" not in str(data["detail"])
                assert "/path/to/file" not in str(data["detail"])
                assert response_is_safe(response.text)

    @given(error_type=st.sampled_from(["validation", "not_found", "internal"]))
    @pytest.mark.asyncio
    async def test_all_errors_have_timestamps(
        self,
        db: TestDB,
        error_type: str,
    ) -> None:
        """All error responses SHALL include timestamps."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

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


class TestErrorResponseStructure:
    """
    Feature: phase-6-polish
    Property 5: Error Response Structure

    *For any* error returned by the API, the response body SHALL contain
    `detail` (string), `error_code` (string), and `timestamp` (ISO datetime string).
    """

    @given(
        error_type=st.sampled_from(
            ["validation", "not_found", "internal", "external_service"]
        ),
    )
    @settings(max_examples=5)
    @pytest.mark.asyncio
    async def test_all_errors_contain_required_fields(
        self,
        db: TestDB,
        error_type: str,
    ) -> None:
        """All error responses SHALL contain detail, error_code, and timestamp."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            if error_type == "validation":
                response = client.get("/trigger-validation-error?fields=test_field")
            elif error_type == "not_found":
                response = client.get("/trigger-not-found/TestResource/test-id")
            elif error_type == "external_service":
                response = client.get("/trigger-external-service-error/TestService")
            else:
                response = client.get("/trigger-internal-error")

            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            # Property 5: All errors must have detail, error_code, timestamp
            assert "detail" in data, "Response must contain 'detail' field"
            assert isinstance(data["detail"], str), "'detail' must be a string"
            assert len(str(data["detail"])) > 0, "'detail' must not be empty"

            assert "error_code" in data, "Response must contain 'error_code' field"
            assert isinstance(data["error_code"], str), "'error_code' must be a string"
            assert len(str(data["error_code"])) > 0, "'error_code' must not be empty"

            assert "timestamp" in data, "Response must contain 'timestamp' field"
            timestamp_str = str(data["timestamp"])
            # Validate ISO datetime format
            parsed_timestamp = datetime.fromisoformat(
                timestamp_str.replace("Z", "+00:00")
            )
            assert parsed_timestamp is not None, "'timestamp' must be valid ISO format"

    @given(
        field_names=st.lists(field_name_strategy, min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_error_response_detail_is_descriptive(
        self,
        db: TestDB,
        field_names: list[str],
    ) -> None:
        """Error detail field SHALL provide meaningful description."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            fields_param = ",".join(field_names)
            response = client.get(f"/trigger-validation-error?fields={fields_param}")

            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            # Detail should be a non-empty descriptive string
            detail = str(data["detail"])
            assert len(detail) >= 5, "Detail should be descriptive (>= 5 chars)"
            assert detail != "error", "Detail should not be generic 'error'"


class TestValidationErrorFieldMapping:
    """
    Feature: phase-6-polish
    Property 6: Validation Error Field Mapping

    *For any* validation error with field-level errors, the API response SHALL
    include a `field_errors` array where each entry contains the field name
    and associated error messages.
    """

    @given(
        field_names=st.lists(field_name_strategy, min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_validation_errors_include_field_errors_array(
        self,
        db: TestDB,
        field_names: list[str],
    ) -> None:
        """Validation errors SHALL include field_errors array with field names."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            fields_param = ",".join(field_names)
            response = client.get(f"/trigger-validation-error?fields={fields_param}")

            assert response.status_code == 400
            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            # Property 6: Must have field_errors array
            assert "field_errors" in data, "Validation error must have field_errors"
            field_errors = data["field_errors"]
            assert isinstance(field_errors, list), "field_errors must be an array"

            # Each field in the request should have a corresponding error entry
            error_fields: set[str] = set()
            field_errors_list = cast(list[dict[str, object]], field_errors)
            for err in field_errors_list:
                if "field" in err:
                    error_fields.add(str(err["field"]))
            for field_name in field_names:
                assert field_name in error_fields, (
                    f"Field '{field_name}' should be in field_errors"
                )

    @given(
        field_names=st.lists(field_name_strategy, min_size=1, max_size=3, unique=True),
        messages_per_field=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_field_errors_contain_field_and_messages(
        self,
        db: TestDB,
        field_names: list[str],
        messages_per_field: int,
    ) -> None:
        """Each field_error entry SHALL contain field name and messages array."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            fields_param = ",".join(field_names)
            response = client.get(
                f"/trigger-validation-error-multi?fields={fields_param}&messages_per_field={messages_per_field}"
            )

            assert response.status_code == 400
            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            assert isinstance(data.get("field_errors"), list)
            field_errors_list = cast(list[dict[str, object]], data["field_errors"])

            for field_error in field_errors_list:
                # Each entry must have 'field' (string)
                assert "field" in field_error, "field_error must have 'field'"
                field_val = field_error["field"]
                assert isinstance(field_val, str), "'field' must be a string"

                # Each entry must have 'messages' (array of strings)
                assert "messages" in field_error, "field_error must have 'messages'"
                messages_val = cast(list[str], field_error["messages"])
                assert isinstance(messages_val, list), "'messages' must be an array"
                assert len(messages_val) > 0, "'messages' must not be empty"

                for msg in messages_val:
                    assert isinstance(msg, str), "Each message must be a string"


class TestNotFoundErrorResourceIdentification:
    """
    Feature: phase-6-polish
    Property 7: NotFound Error Resource Identification

    *For any* NotFoundError raised with a resource type and identifier,
    the API response SHALL include the resource type in the error detail message.
    """

    @given(
        resource_type=resource_type_strategy,
        identifier=identifier_strategy,
    )
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_not_found_includes_resource_type_in_detail(
        self,
        db: TestDB,
        resource_type: str,
        identifier: str,
    ) -> None:
        """NotFound errors SHALL include resource type in detail message."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            response = client.get(f"/trigger-not-found/{resource_type}/{identifier}")

            assert response.status_code == 404
            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            # Property 7: Resource type must be in detail
            detail = str(data["detail"])
            assert resource_type in detail, (
                f"Resource type '{resource_type}' must be in detail: {detail}"
            )

    @given(
        resource_type=resource_type_strategy,
        identifier=identifier_strategy,
    )
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_not_found_includes_identifier_in_detail(
        self,
        db: TestDB,
        resource_type: str,
        identifier: str,
    ) -> None:
        """NotFound errors SHALL include identifier in detail message."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            response = client.get(f"/trigger-not-found/{resource_type}/{identifier}")

            assert response.status_code == 404
            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            # Property 7: Identifier must be in detail
            detail = str(data["detail"])
            assert identifier in detail, (
                f"Identifier '{identifier}' must be in detail: {detail}"
            )

    @given(
        resource_type=resource_type_strategy,
        identifier=identifier_strategy,
    )
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_not_found_has_correct_error_code(
        self,
        db: TestDB,
        resource_type: str,
        identifier: str,
    ) -> None:
        """NotFound errors SHALL have error_code 'NOT_FOUND'."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            response = client.get(f"/trigger-not-found/{resource_type}/{identifier}")

            assert response.status_code == 404
            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            assert data["error_code"] == "NOT_FOUND"


class TestExternalServiceErrorMapping:
    """
    Feature: phase-6-polish
    Property 8: External Service Error Mapping

    *For any* ExternalServiceError raised with a service name, the API response
    SHALL return HTTP 502 and include the service name in the error detail.
    """

    @given(service_name=service_name_strategy)
    @settings(max_examples=8)
    @pytest.mark.asyncio
    async def test_external_service_error_returns_502(
        self,
        db: TestDB,
        service_name: str,
    ) -> None:
        """ExternalServiceError SHALL return HTTP 502 Bad Gateway."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            response = client.get(f"/trigger-external-service-error/{service_name}")

            # Property 8: Must return HTTP 502
            assert response.status_code == 502, (
                f"Expected 502, got {response.status_code}"
            )

    @given(service_name=service_name_strategy)
    @settings(max_examples=8)
    @pytest.mark.asyncio
    async def test_external_service_error_includes_service_name(
        self,
        db: TestDB,
        service_name: str,
    ) -> None:
        """ExternalServiceError SHALL include service name in detail."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            response = client.get(f"/trigger-external-service-error/{service_name}")

            assert response.status_code == 502
            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            # Property 8: Service name must be in detail
            detail = str(data["detail"])
            assert service_name in detail, (
                f"Service name '{service_name}' must be in detail: {detail}"
            )

    @given(service_name=service_name_strategy)
    @settings(max_examples=8)
    @pytest.mark.asyncio
    async def test_external_service_error_has_correct_error_code(
        self,
        db: TestDB,
        service_name: str,
    ) -> None:
        """ExternalServiceError SHALL have error_code 'EXTERNAL_SERVICE_ERROR'."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            response = client.get(f"/trigger-external-service-error/{service_name}")

            assert response.status_code == 502
            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            assert data["error_code"] == "EXTERNAL_SERVICE_ERROR"

    @given(service_name=service_name_strategy)
    @settings(max_examples=8)
    @pytest.mark.asyncio
    async def test_external_service_error_has_required_fields(
        self,
        db: TestDB,
        service_name: str,
    ) -> None:
        """ExternalServiceError response SHALL have all required error fields."""
        await db.clean()
        app = create_test_app_with_error_routes(db.session_factory)

        with TestClient(app) as client:
            response = client.get(f"/trigger-external-service-error/{service_name}")

            assert response.status_code == 502
            data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

            # Must have all standard error response fields
            assert "detail" in data
            assert "error_code" in data
            assert "timestamp" in data
            assert "correlation_id" in data

            # Validate timestamp format
            timestamp_str = str(data["timestamp"])
            _ = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            # Validate correlation_id is a valid UUID
            correlation_id = str(data["correlation_id"])
            _ = UUID(correlation_id)
