"""Property-based tests for model serialization.

Feature: zondarr-foundation
Property: 3
"""

from datetime import UTC, datetime
from uuid import UUID

import msgspec
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import KNOWN_SERVER_TYPES
from zondarr.models import (
    Identity,
    Invitation,
    Library,
    MediaServer,
    User,
)

# Type alias for serialized model data
type SerializedData = dict[str, str | int | bool | None]

# Custom strategies for model fields
uuid_strategy = st.uuids()
datetime_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(UTC),
)
optional_datetime_strategy = st.one_of(st.none(), datetime_strategy)
server_type_strategy = st.sampled_from(KNOWN_SERVER_TYPES)
name_strategy = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=100,
).filter(lambda x: x.strip())
url_strategy = st.from_regex(r"https?://[a-z0-9.-]+\.[a-z]{2,}", fullmatch=True)
code_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=6,
    max_size=20,
)
positive_int_strategy = st.integers(min_value=0, max_value=1000)
optional_positive_int_strategy = st.one_of(st.none(), positive_int_strategy)


def model_to_dict(model: object) -> SerializedData:
    """Convert a SQLAlchemy model to a dictionary for serialization."""
    result: SerializedData = {}
    for key in dir(model):
        if key.startswith("_") or key in ("metadata", "registry"):
            continue
        try:
            value: object = getattr(model, key)  # pyright: ignore[reportAny]
            if callable(value):
                continue
            if isinstance(value, UUID):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, list):
                continue
            elif isinstance(value, (str, int, bool)) or value is None:
                result[key] = value
        except AttributeError, TypeError:
            continue
    return result


def decode_json(json_bytes: bytes) -> SerializedData:
    """Decode JSON bytes to SerializedData with proper typing."""
    result: object = msgspec.json.decode(json_bytes)  # pyright: ignore[reportAny]
    if not isinstance(result, dict):
        msg = "Expected dict from JSON decode"
        raise TypeError(msg)
    return {str(k): v for k, v in result.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


class TestModelSerializationRoundTrip:
    """
    Feature: zondarr-foundation
    Property 3: Model Serialization Round-Trip
    """

    @settings(max_examples=25)
    @given(
        id=uuid_strategy,
        name=name_strategy,
        server_type=server_type_strategy,
        url=url_strategy,
        api_key=name_strategy,
        enabled=st.booleans(),
        created_at=datetime_strategy,
    )
    def test_media_server_serialization_round_trip(
        self,
        id: UUID,
        name: str,
        server_type: str,
        url: str,
        api_key: str,
        enabled: bool,
        created_at: datetime,
    ) -> None:
        """MediaServer serializes with UUIDs as strings and datetimes as ISO."""
        server = MediaServer()
        server.id = id
        server.name = name
        server.server_type = server_type
        server.url = url
        server.api_key = api_key
        server.enabled = enabled
        server.created_at = created_at

        data = model_to_dict(server)

        assert isinstance(data["id"], str)
        assert data["id"] == str(id)
        assert isinstance(data["created_at"], str)
        assert data["created_at"] == created_at.isoformat()
        assert isinstance(data["server_type"], str)
        assert data["server_type"] == server_type

        json_bytes = msgspec.json.encode(data)
        decoded = decode_json(json_bytes)

        assert decoded["id"] == str(id)
        assert decoded["name"] == name
        assert decoded["server_type"] == server_type
        assert decoded["url"] == url
        assert decoded["api_key"] == api_key
        assert decoded["enabled"] == enabled

    @settings(max_examples=25)
    @given(
        id=uuid_strategy,
        media_server_id=uuid_strategy,
        external_id=name_strategy,
        name=name_strategy,
        library_type=st.sampled_from(["movies", "tvshows", "music", "photos"]),
        created_at=datetime_strategy,
    )
    def test_library_serialization_round_trip(
        self,
        id: UUID,
        media_server_id: UUID,
        external_id: str,
        name: str,
        library_type: str,
        created_at: datetime,
    ) -> None:
        """Library serializes with UUIDs as strings and datetimes as ISO."""
        library = Library()
        library.id = id
        library.media_server_id = media_server_id
        library.external_id = external_id
        library.name = name
        library.library_type = library_type
        library.created_at = created_at

        data = model_to_dict(library)

        assert isinstance(data["id"], str)
        assert data["id"] == str(id)
        assert isinstance(data["media_server_id"], str)
        assert data["media_server_id"] == str(media_server_id)

        json_bytes = msgspec.json.encode(data)
        decoded = decode_json(json_bytes)

        assert decoded["id"] == str(id)
        assert decoded["media_server_id"] == str(media_server_id)
        assert decoded["external_id"] == external_id
        assert decoded["name"] == name
        assert decoded["library_type"] == library_type

    @settings(max_examples=25)
    @given(
        id=uuid_strategy,
        code=code_strategy,
        max_uses=optional_positive_int_strategy,
        use_count=positive_int_strategy,
        enabled=st.booleans(),
        created_at=datetime_strategy,
    )
    def test_invitation_serialization_round_trip(
        self,
        id: UUID,
        code: str,
        max_uses: int | None,
        use_count: int,
        enabled: bool,
        created_at: datetime,
    ) -> None:
        """Invitation serializes with UUIDs as strings and datetimes as ISO."""
        invitation = Invitation()
        invitation.id = id
        invitation.code = code
        invitation.max_uses = max_uses
        invitation.use_count = use_count
        invitation.enabled = enabled
        invitation.created_at = created_at

        data = model_to_dict(invitation)

        assert isinstance(data["id"], str)
        assert data["id"] == str(id)
        assert isinstance(data["created_at"], str)

        json_bytes = msgspec.json.encode(data)
        decoded = decode_json(json_bytes)

        assert decoded["id"] == str(id)
        assert decoded["code"] == code
        assert decoded["use_count"] == use_count
        assert decoded["enabled"] == enabled

    @settings(max_examples=25)
    @given(
        id=uuid_strategy,
        display_name=name_strategy,
        enabled=st.booleans(),
        created_at=datetime_strategy,
    )
    def test_identity_serialization_round_trip(
        self,
        id: UUID,
        display_name: str,
        enabled: bool,
        created_at: datetime,
    ) -> None:
        """Identity serializes with UUIDs as strings and datetimes as ISO."""
        identity = Identity()
        identity.id = id
        identity.display_name = display_name
        identity.enabled = enabled
        identity.created_at = created_at

        data = model_to_dict(identity)

        assert isinstance(data["id"], str)
        assert data["id"] == str(id)

        json_bytes = msgspec.json.encode(data)
        decoded = decode_json(json_bytes)

        assert decoded["id"] == str(id)
        assert decoded["display_name"] == display_name
        assert decoded["enabled"] == enabled

    @settings(max_examples=25)
    @given(
        id=uuid_strategy,
        identity_id=uuid_strategy,
        media_server_id=uuid_strategy,
        external_user_id=name_strategy,
        username=name_strategy,
        enabled=st.booleans(),
        created_at=datetime_strategy,
    )
    def test_user_serialization_round_trip(
        self,
        id: UUID,
        identity_id: UUID,
        media_server_id: UUID,
        external_user_id: str,
        username: str,
        enabled: bool,
        created_at: datetime,
    ) -> None:
        """User serializes with UUIDs as strings and datetimes as ISO."""
        user = User()
        user.id = id
        user.identity_id = identity_id
        user.media_server_id = media_server_id
        user.external_user_id = external_user_id
        user.username = username
        user.enabled = enabled
        user.created_at = created_at

        data = model_to_dict(user)

        assert isinstance(data["id"], str)
        assert data["id"] == str(id)
        assert isinstance(data["identity_id"], str)
        assert data["identity_id"] == str(identity_id)
        assert isinstance(data["media_server_id"], str)
        assert data["media_server_id"] == str(media_server_id)

        json_bytes = msgspec.json.encode(data)
        decoded = decode_json(json_bytes)

        assert decoded["id"] == str(id)
        assert decoded["identity_id"] == str(identity_id)
        assert decoded["media_server_id"] == str(media_server_id)
        assert decoded["external_user_id"] == external_user_id
        assert decoded["username"] == username
        assert decoded["enabled"] == enabled
