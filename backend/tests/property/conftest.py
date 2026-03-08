"""Shared Hypothesis strategies and base mock classes for Plex property tests."""

from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for valid URLs
url_strategy = st.from_regex(
    r"https?://[a-z0-9.-]+:\d{1,5}",
    fullmatch=True,
).filter(lambda s: len(s) <= 100)

# Strategy for API keys (Plex tokens are typically alphanumeric)
api_key_strategy = st.text(
    alphabet=st.characters(categories=("L", "N"), whitelist_characters="-_"),
    min_size=10,
    max_size=50,
).filter(lambda s: s.strip())

# Strategy for server names
server_name_strategy = st.text(
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# Valid Plex library types
VALID_PLEX_LIBRARY_TYPES = [
    "movie",
    "show",
    "artist",
    "photo",
]

# Strategy for library section keys (positive integers)
section_key_strategy = st.integers(min_value=1, max_value=10000)

# Strategy for library titles
library_title_strategy = st.text(
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# Strategy for library types
library_type_strategy = st.sampled_from(VALID_PLEX_LIBRARY_TYPES)

# Strategy for valid email addresses
email_strategy = st.emails()

# Strategy for valid usernames (alphanumeric, 3-32 chars)
username_strategy = st.text(
    alphabet=st.characters(categories=("L", "N"), whitelist_characters="_"),
    min_size=3,
    max_size=32,
).filter(lambda s: s.strip() and s[0].isalpha())

# Strategy for operation names
operation_strategy = st.sampled_from(
    [
        "get_libraries",
        "create_user",
        "create_friend",
        "create_home_user",
        "delete_user",
        "set_library_access",
        "update_permissions",
        "list_users",
        "test_connection",
    ]
)

# Strategy for error messages
error_message_strategy = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())


# ---------------------------------------------------------------------------
# Base mock classes
# ---------------------------------------------------------------------------


class MockLibrarySection:
    """Mock Plex library section for testing."""

    key: int
    title: str
    type: str

    def __init__(self, *, key: int, title: str, section_type: str) -> None:
        self.key = key
        self.title = title
        self.type = section_type


class MockLibrary:
    """Mock Plex library for testing."""

    _sections: list[MockLibrarySection]

    def __init__(self) -> None:
        self._sections = []

    def sections(self) -> list[MockLibrarySection]:
        """Return mock library sections."""
        return self._sections


class MockLibraryWithSections(MockLibrary):
    """Mock Plex library that supports sectionByID."""

    _sections: list[MockLibrarySection]
    _sections_by_id: dict[int, MockLibrarySection]

    def __init__(self, sections: list[MockLibrarySection] | None = None) -> None:
        super().__init__()
        self._sections = sections or []
        self._sections_by_id = {s.key: s for s in self._sections}

    def sectionByID(self, section_id: int) -> MockLibrarySection:
        """Return section by ID or raise."""
        if section_id not in self._sections_by_id:
            raise Exception(f"Section {section_id} not found")
        return self._sections_by_id[section_id]


class MockMyPlexAccount:
    """Mock MyPlexAccount for testing."""

    pass


class MockPlexServer[T]:
    """Generic mock PlexServer that works with any account type."""

    url: str
    token: str
    friendlyName: str
    machineIdentifier: str
    library: MockLibrary | MockLibraryWithSections
    _account: T

    def __init__(
        self,
        url: str,
        token: str,
        *,
        friendly_name: str = "Test Server",
        machine_identifier: str = "test-machine-id",
        account: T,
        library: MockLibrary | MockLibraryWithSections | None = None,
    ) -> None:
        self.url = url
        self.token = token
        self.friendlyName = friendly_name
        self.machineIdentifier = machine_identifier
        self._account = account
        self.library = library or MockLibrary()

    def myPlexAccount(self) -> T:
        """Return the configured mock account."""
        return self._account


class MockMyPlexUser:
    """Mock MyPlexUser returned by inviteFriend/createHomeUser."""

    id: int
    username: str
    email: str | None

    def __init__(
        self, *, user_id: int, username: str, email: str | None = None
    ) -> None:
        self.id = user_id
        self.username = username
        self.email = email


class MockMyPlexServerShare:
    """Mock MyPlexServerShare for user server access classification."""

    machineIdentifier: str

    def __init__(self, *, machine_identifier: str) -> None:
        self.machineIdentifier = machine_identifier


class MockMyPlexUserWithHome(MockMyPlexUser):
    """Mock MyPlexUser with home attribute for Home Users."""

    home: bool
    servers: list[MockMyPlexServerShare]

    def __init__(
        self,
        *,
        user_id: int,
        username: str,
        email: str | None = None,
        home: bool = False,
        servers: list[MockMyPlexServerShare] | None = None,
    ) -> None:
        super().__init__(user_id=user_id, username=username, email=email)
        self.home = home
        self.servers = servers or []


class MockHTTPResponse:
    """Mock HTTP response."""

    _json_data: dict[str, object]

    def __init__(self, *, json_data: dict[str, object] | None = None) -> None:
        self._json_data = json_data or {}

    def raise_for_status(self) -> None:
        """No-op for success responses."""

    def json(self) -> dict[str, object]:
        """Return mock JSON data."""
        return self._json_data


class MockResponse:
    """Mock HTTP response for the direct share API call."""

    _status_code: int

    def __init__(self, *, status_code: int = 200) -> None:
        self._status_code = status_code

    def raise_for_status(self) -> None:
        if self._status_code >= 400:
            raise Exception(f"HTTP {self._status_code}")


# ---------------------------------------------------------------------------
# Domain-specific mock classes shared across multiple test files
# ---------------------------------------------------------------------------


class MockMyPlexAccountWithInvite:
    """Mock MyPlexAccount that supports inviteFriend."""

    _invite_result: MockMyPlexUser | None
    _invite_error: Exception | None
    _last_invited: MockMyPlexUser | None

    def __init__(
        self,
        *,
        invite_result: MockMyPlexUser | None = None,
        invite_error: Exception | None = None,
    ) -> None:
        self._invite_result = invite_result
        self._invite_error = invite_error
        self._last_invited = None

    def inviteFriend(
        self, user: str, server: object, sections: object = None
    ) -> MockMyPlexUser:
        """Mock inviteFriend method."""
        _ = server, sections  # Unused but required by API signature
        if self._invite_error is not None:
            raise self._invite_error
        result = self._invite_result or MockMyPlexUser(
            user_id=12345, username=user, email=user
        )
        self._last_invited = result
        return result

    def users(self) -> list[MockMyPlexUser]:
        """Mock users() method returning the invited user."""
        if self._last_invited is not None:
            return [self._last_invited]
        return []


class MockMyPlexAccountWithHomeUser:
    """Mock MyPlexAccount that supports createHomeUser."""

    _create_result: MockMyPlexUser | None
    _create_error: Exception | None

    def __init__(
        self,
        *,
        create_result: MockMyPlexUser | None = None,
        create_error: Exception | None = None,
    ) -> None:
        self._create_result = create_result
        self._create_error = create_error

    def createHomeUser(self, user: str, server: object) -> MockMyPlexUser:
        """Mock createHomeUser method."""
        _ = server  # Unused but required by API signature
        if self._create_error is not None:
            raise self._create_error
        if self._create_result is not None:
            return self._create_result
        # Default: return a mock user with the username
        return MockMyPlexUser(user_id=12345, username=user, email=None)


class MockMyPlexAccountWithUserList:
    """Mock MyPlexAccount that supports user listing."""

    _users: list[MockMyPlexUserWithHome]
    _users_error: Exception | None

    def __init__(
        self,
        *,
        users: list[MockMyPlexUserWithHome] | None = None,
        users_error: Exception | None = None,
    ) -> None:
        self._users = users or []
        self._users_error = users_error

    def users(self) -> list[MockMyPlexUserWithHome]:
        """Return the list of mock users."""
        if self._users_error is not None:
            raise self._users_error
        return self._users
