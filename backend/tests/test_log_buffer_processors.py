"""Tests for the structlog content_type normaliser.

Litestar's ``request.content_type`` is ``(mimetype, params)``. The structlog
processor at ``zondarr.core.log_buffer.normalize_content_type_processor``
flattens the tuple to its mimetype string so log lines render as
``content_type=application/json`` instead of ``content_type=('', {})``.
"""

from collections.abc import MutableMapping

from zondarr.core.log_buffer import normalize_content_type_processor


def _run(event_dict: MutableMapping[str, object]) -> MutableMapping[str, object]:
    """Invoke the processor with dummy logger/name; return the mutated dict."""
    return normalize_content_type_processor(None, "info", event_dict)


def test_flattens_populated_content_type_tuple() -> None:
    event_dict: MutableMapping[str, object] = {
        "event": "HTTP Request",
        "method": "POST",
        "content_type": ("application/json", {"charset": "utf-8"}),
    }
    out = _run(event_dict)
    assert out["content_type"] == "application/json"
    assert out["method"] == "POST"
    assert out["event"] == "HTTP Request"


def test_flattens_empty_content_type_tuple_to_empty_string() -> None:
    event_dict: MutableMapping[str, object] = {
        "event": "HTTP Request",
        "content_type": ("", {}),
    }
    out = _run(event_dict)
    assert out["content_type"] == ""


def test_passes_through_string_content_type_unchanged() -> None:
    event_dict: MutableMapping[str, object] = {
        "event": "HTTP Request",
        "content_type": "text/plain",
    }
    out = _run(event_dict)
    assert out["content_type"] == "text/plain"


def test_does_not_add_content_type_when_missing() -> None:
    event_dict: MutableMapping[str, object] = {
        "event": "HTTP Response",
        "status_code": 200,
    }
    out = _run(event_dict)
    assert "content_type" not in out
    assert out["status_code"] == 200


def test_handles_non_string_first_tuple_element() -> None:
    """Defensive: if Litestar ever puts something weird in slot 0, fall back to ''."""
    event_dict: MutableMapping[str, object] = {
        "event": "HTTP Request",
        "content_type": (None, {}),
    }
    out = _run(event_dict)
    assert out["content_type"] == ""


def test_other_fields_are_preserved() -> None:
    event_dict: MutableMapping[str, object] = {
        "event": "HTTP Request",
        "method": "GET",
        "path": "/api/v1/users",
        "query": {"page": "1"},
        "path_params": {},
        "content_type": ("application/json", {}),
    }
    out = _run(event_dict)
    assert out["method"] == "GET"
    assert out["path"] == "/api/v1/users"
    assert out["query"] == {"page": "1"}
    assert out["path_params"] == {}
    assert out["content_type"] == "application/json"
