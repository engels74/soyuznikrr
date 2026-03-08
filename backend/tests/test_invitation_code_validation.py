"""Tests for InvitationCode schema-level pattern validation.

Ensures the backend rejects invitation codes with special characters,
matching the frontend's alphanumeric-only constraint.
"""

import msgspec
import pytest

from zondarr.api.schemas import CreateInvitationRequest

DUMMY_SERVER_ID = "00000000-0000-0000-0000-000000000001"


class TestInvitationCodePattern:
    """InvitationCode type rejects non-alphanumeric characters."""

    @pytest.mark.parametrize(
        "code",
        [
            "VALID123",
            "abc",
            "A",
            "test",
            "X" * 20,
        ],
    )
    def test_valid_alphanumeric_codes_accepted(self, code: str) -> None:
        data = {"server_ids": [DUMMY_SERVER_ID], "code": code}
        result = msgspec.json.decode(
            msgspec.json.encode(data), type=CreateInvitationRequest
        )
        assert result.code == code

    @pytest.mark.parametrize(
        "code",
        [
            "TEST@#$%",
            "hello world",
            "code-with-dash",
            "code_underscore",
            "code.dot",
            "abc!",
            "inv/code",
        ],
    )
    def test_special_characters_rejected(self, code: str) -> None:
        data = {"server_ids": [DUMMY_SERVER_ID], "code": code}
        with pytest.raises(msgspec.ValidationError):
            _ = msgspec.json.decode(
                msgspec.json.encode(data), type=CreateInvitationRequest
            )

    def test_empty_code_rejected(self) -> None:
        data = {"server_ids": [DUMMY_SERVER_ID], "code": ""}
        with pytest.raises(msgspec.ValidationError):
            _ = msgspec.json.decode(
                msgspec.json.encode(data), type=CreateInvitationRequest
            )

    def test_code_exceeding_max_length_rejected(self) -> None:
        data = {"server_ids": [DUMMY_SERVER_ID], "code": "A" * 21}
        with pytest.raises(msgspec.ValidationError):
            _ = msgspec.json.decode(
                msgspec.json.encode(data), type=CreateInvitationRequest
            )
