"""Property-based tests for PlexClient.

Feature: plex-integration
Properties: 1, 2, 3
Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2
"""

from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from zondarr.media.types import Capability

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


class MockPlexServer:
    """Mock PlexServer for testing."""

    url: str
    token: str
    friendlyName: str
    library: MockLibrary

    def __init__(
        self, url: str, token: str, *, friendly_name: str = "Test Server"
    ) -> None:
        self.url = url
        self.token = token
        self.friendlyName = friendly_name
        self.library = MockLibrary()

    def myPlexAccount(self) -> MockMyPlexAccount:
        """Return a mock MyPlexAccount."""
        return MockMyPlexAccount()


class MockMyPlexAccount:
    """Mock MyPlexAccount for testing."""

    pass


class MockLibrary:
    """Mock Plex library for testing."""

    _sections: list[MockLibrarySection]

    def __init__(self) -> None:
        self._sections = []

    def sections(self) -> list[MockLibrarySection]:
        """Return mock library sections."""
        return self._sections


class MockLibrarySection:
    """Mock Plex library section for testing."""

    key: int
    title: str
    type: str

    def __init__(self, *, key: int, title: str, section_type: str) -> None:
        self.key = key
        self.title = title
        self.type = section_type


class TestContextManagerRoundTrip:
    """
    Feature: plex-integration
    Property 1: Context Manager Round-Trip

    For any PlexClient instance with valid URL and API key, entering the async
    context and then exiting should result in the client being in a clean state
    with _server and _account set to None.

    **Validates: Requirements 1.1, 1.2**
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        server_name=server_name_strategy,
    )
    @pytest.mark.asyncio
    async def test_context_manager_initializes_and_cleans_up(
        self,
        url: str,
        api_key: str,
        server_name: str,
    ) -> None:
        """Context manager initializes _server and _account on enter, cleans up on exit."""
        from zondarr.media.clients.plex import PlexClient

        # Create mock server that will be returned by PlexServer constructor
        mock_server = MockPlexServer(url, api_key, friendly_name=server_name)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            # Before entering context, _server and _account should be None
            assert client._server is None  # pyright: ignore[reportPrivateUsage]
            assert client._account is None  # pyright: ignore[reportPrivateUsage]

            # Enter context
            async with client:
                # Inside context, _server and _account should be set
                assert client._server is not None  # pyright: ignore[reportPrivateUsage]
                assert client._account is not None  # pyright: ignore[reportPrivateUsage]

            # After exiting context, _server and _account should be None
            assert client._server is None  # pyright: ignore[reportPrivateUsage]
            assert client._account is None  # pyright: ignore[reportPrivateUsage]

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_context_manager_returns_self(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """Context manager __aenter__ returns self."""
        from zondarr.media.clients.plex import PlexClient

        mock_server = MockPlexServer(url, api_key)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client as entered_client:
                assert entered_client is client

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_context_manager_cleans_up_on_exception(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """Context manager cleans up _server and _account even when exception occurs."""
        from zondarr.media.clients.plex import PlexClient

        mock_server = MockPlexServer(url, api_key)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            with pytest.raises(ValueError, match="test exception"):
                async with client:
                    assert client._server is not None  # pyright: ignore[reportPrivateUsage]
                    raise ValueError("test exception")

            # After exception, _server and _account should still be None
            assert client._server is None  # pyright: ignore[reportPrivateUsage]
            assert client._account is None  # pyright: ignore[reportPrivateUsage]


class TestCapabilitiesDeclaration:
    """
    Feature: plex-integration
    Property: Capabilities Declaration

    PlexClient declares CREATE_USER, DELETE_USER, and LIBRARY_ACCESS capabilities.
    It does NOT declare ENABLE_DISABLE_USER or DOWNLOAD_PERMISSION.

    **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
    """

    def test_capabilities_includes_create_user(self) -> None:
        """PlexClient declares CREATE_USER capability."""
        from zondarr.media.clients.plex import PlexClient

        capabilities = PlexClient.capabilities()
        assert Capability.CREATE_USER in capabilities

    def test_capabilities_includes_delete_user(self) -> None:
        """PlexClient declares DELETE_USER capability."""
        from zondarr.media.clients.plex import PlexClient

        capabilities = PlexClient.capabilities()
        assert Capability.DELETE_USER in capabilities

    def test_capabilities_includes_library_access(self) -> None:
        """PlexClient declares LIBRARY_ACCESS capability."""
        from zondarr.media.clients.plex import PlexClient

        capabilities = PlexClient.capabilities()
        assert Capability.LIBRARY_ACCESS in capabilities

    def test_capabilities_excludes_enable_disable_user(self) -> None:
        """PlexClient does NOT declare ENABLE_DISABLE_USER capability."""
        from zondarr.media.clients.plex import PlexClient

        capabilities = PlexClient.capabilities()
        assert Capability.ENABLE_DISABLE_USER not in capabilities

    def test_capabilities_excludes_download_permission(self) -> None:
        """PlexClient does NOT declare DOWNLOAD_PERMISSION capability."""
        from zondarr.media.clients.plex import PlexClient

        capabilities = PlexClient.capabilities()
        assert Capability.DOWNLOAD_PERMISSION not in capabilities

    def test_capabilities_returns_exactly_three(self) -> None:
        """PlexClient declares exactly 3 capabilities."""
        from zondarr.media.clients.plex import PlexClient

        capabilities = PlexClient.capabilities()
        assert len(capabilities) == 3


class MockPlexServerWithError:
    """Mock PlexServer that raises an error when friendlyName is accessed."""

    url: str
    token: str
    library: MockLibrary
    _error: Exception

    def __init__(self, url: str, token: str, *, error: Exception) -> None:
        self.url = url
        self.token = token
        self.library = MockLibrary()
        self._error = error

    @property
    def friendlyName(self) -> str:
        """Raise the configured error."""
        raise self._error

    def myPlexAccount(self) -> MockMyPlexAccount:
        """Return a mock MyPlexAccount."""
        return MockMyPlexAccount()


class TestConnectionTestReturnValues:
    """
    Feature: plex-integration
    Property 2: Connection Test Return Value Correctness

    For any PlexClient instance, test_connection() should return True if and only
    if the server is reachable and the token is valid; otherwise it should return
    False without raising an exception.

    **Validates: Requirements 1.3, 1.4, 1.5**
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        server_name=server_name_strategy,
    )
    @pytest.mark.asyncio
    async def test_connection_returns_true_on_success(
        self,
        url: str,
        api_key: str,
        server_name: str,
    ) -> None:
        """test_connection returns True when server is reachable and token is valid."""
        from zondarr.media.clients.plex import PlexClient

        mock_server = MockPlexServer(url, api_key, friendly_name=server_name)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.test_connection()
                assert result is True

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_connection_returns_false_when_not_initialized(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """test_connection returns False when client is not initialized (outside context)."""
        from zondarr.media.clients.plex import PlexClient

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _server is None
        result = await client.test_connection()
        assert result is False

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        error_message=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    )
    @pytest.mark.asyncio
    async def test_connection_returns_false_on_exception(
        self,
        url: str,
        api_key: str,
        error_message: str,
    ) -> None:
        """test_connection returns False (not raises) when server query fails."""
        from zondarr.media.clients.plex import PlexClient

        # Create a mock server that raises an exception when friendlyName is accessed
        mock_server = MockPlexServerWithError(
            url, api_key, error=ConnectionError(error_message)
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                # Should return False, not raise
                result = await client.test_connection()
                assert result is False

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_connection_never_raises_exception(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """test_connection never raises exceptions, always returns bool."""
        from zondarr.media.clients.plex import PlexClient

        # Create a mock server that raises a RuntimeError
        mock_server = MockPlexServerWithError(
            url, api_key, error=RuntimeError("Server error")
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                # Should not raise, should return False
                result = await client.test_connection()
                assert isinstance(result, bool)
                assert result is False


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


class TestLibraryRetrievalProducesValidStructs:
    """
    Feature: plex-integration
    Property 3: Library Retrieval Produces Valid Structs

    For any connected PlexClient with accessible libraries, get_libraries()
    should return a sequence where each element is a valid LibraryInfo with
    non-empty external_id, name, and library_type fields.

    **Validates: Requirements 3.1, 3.2**
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        sections=st.lists(
            st.tuples(
                section_key_strategy, library_title_strategy, library_type_strategy
            ),
            min_size=0,
            max_size=10,
        ),
    )
    @pytest.mark.asyncio
    async def test_get_libraries_returns_valid_library_info(
        self,
        url: str,
        api_key: str,
        sections: list[tuple[int, str, str]],
    ) -> None:
        """get_libraries returns valid LibraryInfo structs for each section."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.types import LibraryInfo

        mock_server = MockPlexServer(url, api_key)
        mock_server.library._sections = [  # pyright: ignore[reportPrivateUsage]
            MockLibrarySection(key=key, title=title, section_type=lib_type)
            for key, title, lib_type in sections
        ]

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                libraries = await client.get_libraries()

                # Should return same number of libraries as sections
                assert len(libraries) == len(sections)

                # Each library should be a valid LibraryInfo
                for lib in libraries:
                    assert isinstance(lib, LibraryInfo)
                    assert lib.external_id  # non-empty
                    assert lib.name  # non-empty
                    assert lib.library_type  # non-empty

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        key=section_key_strategy,
        title=library_title_strategy,
        lib_type=library_type_strategy,
    )
    @pytest.mark.asyncio
    async def test_get_libraries_maps_fields_correctly(
        self,
        url: str,
        api_key: str,
        key: int,
        title: str,
        lib_type: str,
    ) -> None:
        """get_libraries maps section key→external_id, title→name, type→library_type."""
        from zondarr.media.clients.plex import PlexClient

        mock_server = MockPlexServer(url, api_key)
        mock_server.library._sections = [  # pyright: ignore[reportPrivateUsage]
            MockLibrarySection(key=key, title=title, section_type=lib_type)
        ]

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                libraries = await client.get_libraries()

                assert len(libraries) == 1
                lib = libraries[0]
                assert lib.external_id == str(key)
                assert lib.name == title
                assert lib.library_type == lib_type

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_get_libraries_returns_empty_for_no_sections(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """get_libraries returns empty sequence when server has no sections."""
        from zondarr.media.clients.plex import PlexClient

        mock_server = MockPlexServer(url, api_key)
        mock_server.library._sections = []  # pyright: ignore[reportPrivateUsage]

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                libraries = await client.get_libraries()
                assert len(libraries) == 0

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_get_libraries_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """get_libraries raises MediaClientError when client is not initialized."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _server is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.get_libraries()

        assert exc_info.value.operation == "get_libraries"
        assert exc_info.value.server_url == url


# Strategy for valid email addresses
email_strategy = st.emails()

# Strategy for valid usernames (alphanumeric, 3-32 chars)
username_strategy = st.text(
    alphabet=st.characters(categories=("L", "N"), whitelist_characters="_"),
    min_size=3,
    max_size=32,
).filter(lambda s: s.strip() and s[0].isalpha())


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


class MockMyPlexAccountWithInvite:
    """Mock MyPlexAccount that supports inviteFriend."""

    _invite_result: MockMyPlexUser | None
    _invite_error: Exception | None

    def __init__(
        self,
        *,
        invite_result: MockMyPlexUser | None = None,
        invite_error: Exception | None = None,
    ) -> None:
        self._invite_result = invite_result
        self._invite_error = invite_error

    def inviteFriend(self, user: str, server: object) -> MockMyPlexUser:
        """Mock inviteFriend method."""
        _ = server  # Unused but required by API signature
        if self._invite_error is not None:
            raise self._invite_error
        if self._invite_result is not None:
            return self._invite_result
        # Default: return a mock user with the email
        return MockMyPlexUser(user_id=12345, username=user, email=user)


class MockPlexServerWithAccount:
    """Mock PlexServer that returns a configurable MyPlexAccount."""

    url: str
    token: str
    friendlyName: str
    library: MockLibrary
    _account: MockMyPlexAccountWithInvite

    def __init__(
        self,
        url: str,
        token: str,
        *,
        friendly_name: str = "Test Server",
        account: MockMyPlexAccountWithInvite | None = None,
    ) -> None:
        self.url = url
        self.token = token
        self.friendlyName = friendly_name
        self.library = MockLibrary()
        self._account = account or MockMyPlexAccountWithInvite()

    def myPlexAccount(self) -> MockMyPlexAccountWithInvite:
        """Return the configured mock MyPlexAccount."""
        return self._account


class TestFriendCreationReturnsValidExternalUser:
    """
    Feature: plex-integration
    Property 4: Friend Creation Returns Valid ExternalUser

    For any valid email address and connected PlexClient, creating a Friend
    user should return an ExternalUser where external_user_id is non-empty
    and email matches the input email.

    **Validates: Requirements 4.1, 4.2**
    """

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_friend_creation_returns_valid_external_user(
        self,
        url: str,
        api_key: str,
        email: str,
        user_id: int,
    ) -> None:
        """Friend creation returns ExternalUser with non-empty external_user_id and matching email."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.types import ExternalUser

        mock_user = MockMyPlexUser(user_id=user_id, username=email, email=email)
        mock_account = MockMyPlexAccountWithInvite(invite_result=mock_user)
        mock_server = MockPlexServerWithAccount(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

                # Verify result is ExternalUser
                assert isinstance(result, ExternalUser)
                # external_user_id should be non-empty
                assert result.external_user_id
                assert len(result.external_user_id) > 0
                # email should match input
                assert result.email == email

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_friend_creation_uses_returned_user_id(
        self,
        url: str,
        api_key: str,
        email: str,
        user_id: int,
        username: str,
    ) -> None:
        """Friend creation uses the user ID returned by inviteFriend."""
        from zondarr.media.clients.plex import PlexClient

        mock_user = MockMyPlexUser(user_id=user_id, username=username, email=email)
        mock_account = MockMyPlexAccountWithInvite(invite_result=mock_user)
        mock_server = MockPlexServerWithAccount(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

                # external_user_id should be the string representation of user_id
                assert result.external_user_id == str(user_id)
                # username should be from the returned user
                assert result.username == username

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_friend_creation_raises_user_already_exists_on_duplicate(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """Friend creation raises MediaClientError with USER_ALREADY_EXISTS on duplicate."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError

        # Simulate duplicate user error from Plex API
        mock_account = MockMyPlexAccountWithInvite(
            invite_error=Exception("User is already shared with this server")
        )
        mock_server = MockPlexServerWithAccount(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(MediaClientError) as exc_info:
                    _ = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

                assert exc_info.value.media_error_code == "USER_ALREADY_EXISTS"
                assert exc_info.value.operation == "create_friend"

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_friend_creation_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """Friend creation raises MediaClientError when client is not initialized."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

        assert exc_info.value.operation == "create_friend"
        assert exc_info.value.server_url == url


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


class MockPlexServerWithHomeUserAccount:
    """Mock PlexServer that returns a configurable MyPlexAccount for Home User creation."""

    url: str
    token: str
    friendlyName: str
    library: MockLibrary
    _account: MockMyPlexAccountWithHomeUser

    def __init__(
        self,
        url: str,
        token: str,
        *,
        friendly_name: str = "Test Server",
        account: MockMyPlexAccountWithHomeUser | None = None,
    ) -> None:
        self.url = url
        self.token = token
        self.friendlyName = friendly_name
        self.library = MockLibrary()
        self._account = account or MockMyPlexAccountWithHomeUser()

    def myPlexAccount(self) -> MockMyPlexAccountWithHomeUser:
        """Return the configured mock MyPlexAccount."""
        return self._account


class TestHomeUserCreationReturnsValidExternalUser:
    """
    Feature: plex-integration
    Property 5: Home User Creation Returns Valid ExternalUser

    For any valid username and connected PlexClient, creating a Home User
    should return an ExternalUser where external_user_id is non-empty
    and username matches the input username.

    **Validates: Requirements 5.1, 5.2**
    """

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_home_user_creation_returns_valid_external_user(
        self,
        url: str,
        api_key: str,
        username: str,
        user_id: int,
    ) -> None:
        """Home User creation returns ExternalUser with non-empty external_user_id and matching username."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.types import ExternalUser

        mock_user = MockMyPlexUser(user_id=user_id, username=username, email=None)
        mock_account = MockMyPlexAccountWithHomeUser(create_result=mock_user)
        mock_server = MockPlexServerWithHomeUserAccount(
            url, api_key, account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

                # Verify result is ExternalUser
                assert isinstance(result, ExternalUser)
                # external_user_id should be non-empty
                assert result.external_user_id
                assert len(result.external_user_id) > 0
                # username should match input
                assert result.username == username
                # email should be None for Home Users
                assert result.email is None

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_home_user_creation_uses_returned_user_id(
        self,
        url: str,
        api_key: str,
        username: str,
        user_id: int,
    ) -> None:
        """Home User creation uses the user ID returned by createHomeUser."""
        from zondarr.media.clients.plex import PlexClient

        mock_user = MockMyPlexUser(user_id=user_id, username=username, email=None)
        mock_account = MockMyPlexAccountWithHomeUser(create_result=mock_user)
        mock_server = MockPlexServerWithHomeUserAccount(
            url, api_key, account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

                # external_user_id should be the string representation of user_id
                assert result.external_user_id == str(user_id)

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_home_user_creation_raises_username_taken_on_duplicate(
        self,
        url: str,
        api_key: str,
        username: str,
    ) -> None:
        """Home User creation raises MediaClientError with USERNAME_TAKEN on duplicate."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError

        # Simulate duplicate username error from Plex API
        mock_account = MockMyPlexAccountWithHomeUser(
            create_error=Exception("Username already taken")
        )
        mock_server = MockPlexServerWithHomeUserAccount(
            url, api_key, account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(MediaClientError) as exc_info:
                    _ = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

                assert exc_info.value.media_error_code == "USERNAME_TAKEN"
                assert exc_info.value.operation == "create_home_user"

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_home_user_creation_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
        username: str,
    ) -> None:
        """Home User creation raises MediaClientError when client is not initialized."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

        assert exc_info.value.operation == "create_home_user"
        assert exc_info.value.server_url == url


class MockMyPlexAccountWithBothMethods:
    """Mock MyPlexAccount that supports both inviteFriend and createHomeUser."""

    _invite_result: MockMyPlexUser | None
    _invite_error: Exception | None
    _create_result: MockMyPlexUser | None
    _create_error: Exception | None
    invite_friend_called: bool
    create_home_user_called: bool
    last_invite_email: str | None
    last_create_username: str | None

    def __init__(
        self,
        *,
        invite_result: MockMyPlexUser | None = None,
        invite_error: Exception | None = None,
        create_result: MockMyPlexUser | None = None,
        create_error: Exception | None = None,
    ) -> None:
        self._invite_result = invite_result
        self._invite_error = invite_error
        self._create_result = create_result
        self._create_error = create_error
        self.invite_friend_called = False
        self.create_home_user_called = False
        self.last_invite_email = None
        self.last_create_username = None

    def inviteFriend(self, user: str, server: object) -> MockMyPlexUser:
        """Mock inviteFriend method."""
        _ = server  # Unused but required by API signature
        self.invite_friend_called = True
        self.last_invite_email = user
        if self._invite_error is not None:
            raise self._invite_error
        if self._invite_result is not None:
            return self._invite_result
        return MockMyPlexUser(user_id=12345, username=user, email=user)

    def createHomeUser(self, user: str, server: object) -> MockMyPlexUser:
        """Mock createHomeUser method."""
        _ = server  # Unused but required by API signature
        self.create_home_user_called = True
        self.last_create_username = user
        if self._create_error is not None:
            raise self._create_error
        if self._create_result is not None:
            return self._create_result
        return MockMyPlexUser(user_id=12345, username=user, email=None)


class MockPlexServerWithBothMethods:
    """Mock PlexServer that returns a configurable MyPlexAccount with both methods."""

    url: str
    token: str
    friendlyName: str
    library: MockLibrary
    _account: MockMyPlexAccountWithBothMethods

    def __init__(
        self,
        url: str,
        token: str,
        *,
        friendly_name: str = "Test Server",
        account: MockMyPlexAccountWithBothMethods | None = None,
    ) -> None:
        self.url = url
        self.token = token
        self.friendlyName = friendly_name
        self.library = MockLibrary()
        self._account = account or MockMyPlexAccountWithBothMethods()

    def myPlexAccount(self) -> MockMyPlexAccountWithBothMethods:
        """Return the configured mock MyPlexAccount."""
        return self._account


class TestUserTypeRoutingCorrectness:
    """
    Feature: plex-integration
    Property 6: User Type Routing Correctness

    For any call to create_user, if plex_user_type is FRIEND and email is provided,
    the Friend creation path is used; if plex_user_type is HOME, the Home User
    creation path is used; if plex_user_type is FRIEND but no email is provided,
    MediaClientError is raised.

    **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    """

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
        email=email_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_friend_type_with_email_routes_to_invite_friend(
        self,
        url: str,
        api_key: str,
        username: str,
        email: str,
        user_id: int,
    ) -> None:
        """create_user with FRIEND type and email routes to inviteFriend."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.types import PlexUserType

        mock_user = MockMyPlexUser(user_id=user_id, username=email, email=email)
        mock_account = MockMyPlexAccountWithBothMethods(invite_result=mock_user)
        mock_server = MockPlexServerWithBothMethods(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.create_user(
                    username,
                    "ignored_password",
                    email=email,
                    plex_user_type=PlexUserType.FRIEND,
                )

                # Verify inviteFriend was called, not createHomeUser
                assert mock_account.invite_friend_called is True
                assert mock_account.create_home_user_called is False
                assert mock_account.last_invite_email == email
                # Result should have the email
                assert result.email == email

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_home_type_routes_to_create_home_user(
        self,
        url: str,
        api_key: str,
        username: str,
        user_id: int,
    ) -> None:
        """create_user with HOME type routes to createHomeUser."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.types import PlexUserType

        mock_user = MockMyPlexUser(user_id=user_id, username=username, email=None)
        mock_account = MockMyPlexAccountWithBothMethods(create_result=mock_user)
        mock_server = MockPlexServerWithBothMethods(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.create_user(
                    username, "ignored_password", plex_user_type=PlexUserType.HOME
                )

                # Verify createHomeUser was called, not inviteFriend
                assert mock_account.create_home_user_called is True
                assert mock_account.invite_friend_called is False
                assert mock_account.last_create_username == username
                # Result should have the username
                assert result.username == username
                # Result should not have email for Home Users
                assert result.email is None

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_friend_type_without_email_raises_email_required(
        self,
        url: str,
        api_key: str,
        username: str,
    ) -> None:
        """create_user with FRIEND type but no email raises MediaClientError with EMAIL_REQUIRED."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.types import PlexUserType

        mock_account = MockMyPlexAccountWithBothMethods()
        mock_server = MockPlexServerWithBothMethods(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(MediaClientError) as exc_info:
                    _ = await client.create_user(
                        username, "ignored_password", plex_user_type=PlexUserType.FRIEND
                    )

                assert exc_info.value.media_error_code == "EMAIL_REQUIRED"
                assert exc_info.value.operation == "create_user"
                # Neither method should have been called
                assert mock_account.invite_friend_called is False
                assert mock_account.create_home_user_called is False

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
        email=email_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_default_user_type_is_friend(
        self,
        url: str,
        api_key: str,
        username: str,
        email: str,
        user_id: int,
    ) -> None:
        """create_user defaults to FRIEND type when plex_user_type is not specified."""
        from zondarr.media.clients.plex import PlexClient

        mock_user = MockMyPlexUser(user_id=user_id, username=email, email=email)
        mock_account = MockMyPlexAccountWithBothMethods(invite_result=mock_user)
        mock_server = MockPlexServerWithBothMethods(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                # Don't specify plex_user_type - should default to FRIEND
                result = await client.create_user(
                    username, "ignored_password", email=email
                )

                # Verify inviteFriend was called (default is FRIEND)
                assert mock_account.invite_friend_called is True
                assert mock_account.create_home_user_called is False
                assert result.email == email


class MockMyPlexAccountWithUserManagement:
    """Mock MyPlexAccount that supports user listing and deletion."""

    _users: list[MockMyPlexUser]
    _remove_friend_error: Exception | None
    _remove_home_user_error: Exception | None
    removed_users: list[str]

    def __init__(
        self,
        *,
        users: list[MockMyPlexUser] | None = None,
        remove_friend_error: Exception | None = None,
        remove_home_user_error: Exception | None = None,
    ) -> None:
        self._users = users or []
        self._remove_friend_error = remove_friend_error
        self._remove_home_user_error = remove_home_user_error
        self.removed_users = []

    def users(self) -> list[MockMyPlexUser]:
        """Return the list of mock users."""
        return self._users

    def removeFriend(self, user: MockMyPlexUser) -> None:
        """Mock removeFriend method."""
        if self._remove_friend_error is not None:
            raise self._remove_friend_error
        self.removed_users.append(str(user.id))

    def removeHomeUser(self, user: MockMyPlexUser) -> None:
        """Mock removeHomeUser method."""
        if self._remove_home_user_error is not None:
            raise self._remove_home_user_error
        self.removed_users.append(str(user.id))


class MockMyPlexUserWithHome(MockMyPlexUser):
    """Mock MyPlexUser with home attribute for Home Users."""

    home: bool

    def __init__(
        self,
        *,
        user_id: int,
        username: str,
        email: str | None = None,
        home: bool = False,
    ) -> None:
        super().__init__(user_id=user_id, username=username, email=email)
        self.home = home


class MockPlexServerWithUserManagement:
    """Mock PlexServer that returns a configurable MyPlexAccount for user management."""

    url: str
    token: str
    friendlyName: str
    library: MockLibrary
    _account: MockMyPlexAccountWithUserManagement

    def __init__(
        self,
        url: str,
        token: str,
        *,
        friendly_name: str = "Test Server",
        account: MockMyPlexAccountWithUserManagement | None = None,
    ) -> None:
        self.url = url
        self.token = token
        self.friendlyName = friendly_name
        self.library = MockLibrary()
        self._account = account or MockMyPlexAccountWithUserManagement()

    def myPlexAccount(self) -> MockMyPlexAccountWithUserManagement:
        """Return the configured mock MyPlexAccount."""
        return self._account


class TestDeleteUserReturnValueCorrectness:
    """
    Feature: plex-integration
    Property 7: Delete User Return Value Correctness

    For any connected PlexClient and user identifier, delete_user() should
    return True if the user existed and was deleted, False if the user was
    not found, and raise MediaClientError only for other failures.

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
    """

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_delete_user_returns_true_when_friend_deleted(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """delete_user returns True when Friend is successfully deleted."""
        from zondarr.media.clients.plex import PlexClient

        # Create a Friend user (home=False)
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithUserManagement(users=[mock_user])
        mock_server = MockPlexServerWithUserManagement(
            url, api_key, account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.delete_user(str(user_id))

                assert result is True
                assert str(user_id) in mock_account.removed_users

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_delete_user_returns_true_when_home_user_deleted(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """delete_user returns True when Home User is successfully deleted."""
        from zondarr.media.clients.plex import PlexClient

        # Create a Home User (home=True)
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=None, home=True
        )
        mock_account = MockMyPlexAccountWithUserManagement(users=[mock_user])
        mock_server = MockPlexServerWithUserManagement(
            url, api_key, account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.delete_user(str(user_id))

                assert result is True
                assert str(user_id) in mock_account.removed_users

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_delete_user_returns_false_when_user_not_found(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """delete_user returns False when user is not found."""
        from zondarr.media.clients.plex import PlexClient

        # Empty user list - user won't be found
        mock_account = MockMyPlexAccountWithUserManagement(users=[])
        mock_server = MockPlexServerWithUserManagement(
            url, api_key, account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.delete_user(str(user_id))

                assert result is False
                assert len(mock_account.removed_users) == 0

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_delete_user_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """delete_user raises MediaClientError when client is not initialized."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.delete_user(str(user_id))

        assert exc_info.value.operation == "delete_user"
        assert exc_info.value.server_url == url

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
        error_message=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    )
    @pytest.mark.asyncio
    async def test_delete_user_raises_on_api_failure(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
        error_message: str,
    ) -> None:
        """delete_user raises ExternalServiceError on API failure (not 'not found')."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.clients.plex import PlexClient

        # Create a Friend user that will fail to delete
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithUserManagement(
            users=[mock_user],
            remove_friend_error=RuntimeError(error_message),
        )
        mock_server = MockPlexServerWithUserManagement(
            url, api_key, account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client.delete_user(str(user_id))

                assert f"Plex ({url})" in exc_info.value.service_name


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


class MockMyPlexAccountWithLibraryAccess:
    """Mock MyPlexAccount that supports user listing and library access updates."""

    _users: list[MockMyPlexUserWithHome]
    _update_friend_error: Exception | None
    update_friend_calls: list[dict[str, object]]

    def __init__(
        self,
        *,
        users: list[MockMyPlexUserWithHome] | None = None,
        update_friend_error: Exception | None = None,
    ) -> None:
        self._users = users or []
        self._update_friend_error = update_friend_error
        self.update_friend_calls = []

    def users(self) -> list[MockMyPlexUserWithHome]:
        """Return the list of mock users."""
        return self._users

    def updateFriend(
        self, user: object, server: object, sections: list[object]
    ) -> None:
        """Mock updateFriend method."""
        if self._update_friend_error is not None:
            raise self._update_friend_error
        self.update_friend_calls.append(
            {"user": user, "server": server, "sections": sections}
        )


class MockPlexServerWithLibraryAccess:
    """Mock PlexServer that supports library access operations."""

    url: str
    token: str
    friendlyName: str
    library: MockLibraryWithSections
    _account: MockMyPlexAccountWithLibraryAccess

    def __init__(
        self,
        url: str,
        token: str,
        *,
        friendly_name: str = "Test Server",
        account: MockMyPlexAccountWithLibraryAccess | None = None,
        library_sections: list[MockLibrarySection] | None = None,
    ) -> None:
        self.url = url
        self.token = token
        self.friendlyName = friendly_name
        self.library = MockLibraryWithSections(library_sections)
        self._account = account or MockMyPlexAccountWithLibraryAccess()

    def myPlexAccount(self) -> MockMyPlexAccountWithLibraryAccess:
        """Return the configured mock MyPlexAccount."""
        return self._account


class TestLibraryAccessUpdateReturnValueCorrectness:
    """
    Feature: plex-integration
    Property 8: Library Access Update Return Value Correctness

    For any connected PlexClient, valid user identifier, and library ID list,
    set_library_access() should return True if the user exists and access was
    updated, False if the user was not found.

    **Validates: Requirements 8.1, 8.2, 8.3, 9.1, 9.2, 9.3**
    """

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
        library_ids=st.lists(
            st.integers(min_value=1, max_value=100), min_size=1, max_size=5
        ),
    )
    @pytest.mark.asyncio
    async def test_set_library_access_returns_true_for_friend(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
        library_ids: list[int],
    ) -> None:
        """set_library_access returns True when Friend's access is updated."""
        from zondarr.media.clients.plex import PlexClient

        # Create a Friend user
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithLibraryAccess(users=[mock_user])

        # Create library sections
        sections = [
            MockLibrarySection(
                key=lib_id, title=f"Library {lib_id}", section_type="movie"
            )
            for lib_id in library_ids
        ]

        mock_server = MockPlexServerWithLibraryAccess(
            url, api_key, account=mock_account, library_sections=sections
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.set_library_access(
                    str(user_id), [str(lib_id) for lib_id in library_ids]
                )

                assert result is True
                assert len(mock_account.update_friend_calls) == 1

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
        library_ids=st.lists(
            st.integers(min_value=1, max_value=100), min_size=1, max_size=5
        ),
    )
    @pytest.mark.asyncio
    async def test_set_library_access_returns_true_for_home_user(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
        library_ids: list[int],
    ) -> None:
        """set_library_access returns True when Home User's access is updated."""
        from zondarr.media.clients.plex import PlexClient

        # Create a Home User
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=None, home=True
        )
        mock_account = MockMyPlexAccountWithLibraryAccess(users=[mock_user])

        # Create library sections
        sections = [
            MockLibrarySection(
                key=lib_id, title=f"Library {lib_id}", section_type="movie"
            )
            for lib_id in library_ids
        ]

        mock_server = MockPlexServerWithLibraryAccess(
            url, api_key, account=mock_account, library_sections=sections
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.set_library_access(
                    str(user_id), [str(lib_id) for lib_id in library_ids]
                )

                assert result is True
                assert len(mock_account.update_friend_calls) == 1

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_set_library_access_returns_false_when_user_not_found(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """set_library_access returns False when user is not found."""
        from zondarr.media.clients.plex import PlexClient

        # Empty user list - user won't be found
        mock_account = MockMyPlexAccountWithLibraryAccess(users=[])
        mock_server = MockPlexServerWithLibraryAccess(
            url, api_key, account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.set_library_access(str(user_id), ["1", "2"])

                assert result is False
                assert len(mock_account.update_friend_calls) == 0

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_set_library_access_with_empty_list_revokes_access(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """set_library_access with empty list revokes all access."""
        from zondarr.media.clients.plex import PlexClient

        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithLibraryAccess(users=[mock_user])
        mock_server = MockPlexServerWithLibraryAccess(
            url, api_key, account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.set_library_access(str(user_id), [])

                assert result is True
                assert len(mock_account.update_friend_calls) == 1
                # Empty sections list should be passed
                assert mock_account.update_friend_calls[0]["sections"] == []

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_set_library_access_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """set_library_access raises MediaClientError when client is not initialized."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.set_library_access(str(user_id), ["1"])

        assert exc_info.value.operation == "set_library_access"
        assert exc_info.value.server_url == url


class MockMyPlexAccountWithPermissions:
    """Mock MyPlexAccount that supports user listing and permission updates."""

    _users: list[MockMyPlexUserWithHome]
    _update_friend_error: Exception | None
    update_friend_calls: list[dict[str, object]]

    def __init__(
        self,
        *,
        users: list[MockMyPlexUserWithHome] | None = None,
        update_friend_error: Exception | None = None,
    ) -> None:
        self._users = users or []
        self._update_friend_error = update_friend_error
        self.update_friend_calls = []

    def users(self) -> list[MockMyPlexUserWithHome]:
        """Return the list of mock users."""
        return self._users

    def updateFriend(
        self,
        user: object,
        server: object,
        allowSync: bool | None = None,
        **kwargs: object,
    ) -> None:
        """Mock updateFriend method with permission support."""
        if self._update_friend_error is not None:
            raise self._update_friend_error
        self.update_friend_calls.append(
            {"user": user, "server": server, "allowSync": allowSync, **kwargs}
        )


class MockPlexServerWithPermissions:
    """Mock PlexServer that supports permission operations."""

    url: str
    token: str
    friendlyName: str
    library: MockLibrary
    _account: MockMyPlexAccountWithPermissions

    def __init__(
        self,
        url: str,
        token: str,
        *,
        friendly_name: str = "Test Server",
        account: MockMyPlexAccountWithPermissions | None = None,
    ) -> None:
        self.url = url
        self.token = token
        self.friendlyName = friendly_name
        self.library = MockLibrary()
        self._account = account or MockMyPlexAccountWithPermissions()

    def myPlexAccount(self) -> MockMyPlexAccountWithPermissions:
        """Return the configured mock MyPlexAccount."""
        return self._account


class TestPermissionUpdateMappingAndReturnValue:
    """
    Feature: plex-integration
    Property 9: Permission Update Mapping and Return Value

    For any connected PlexClient, valid user identifier, and permissions dict
    containing can_download, update_permissions() should map can_download to
    the Plex allowSync setting and return True on success, False if user not found.

    **Validates: Requirements 11.1, 11.2, 11.3, 11.5**
    """

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
        can_download=st.booleans(),
    )
    @pytest.mark.asyncio
    async def test_update_permissions_maps_can_download_to_allow_sync(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
        can_download: bool,
    ) -> None:
        """update_permissions maps can_download to Plex allowSync setting."""
        from zondarr.media.clients.plex import PlexClient

        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithPermissions(users=[mock_user])
        mock_server = MockPlexServerWithPermissions(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.update_permissions(
                    str(user_id), permissions={"can_download": can_download}
                )

                assert result is True
                assert len(mock_account.update_friend_calls) == 1
                # Verify can_download was mapped to allowSync
                assert mock_account.update_friend_calls[0]["allowSync"] == can_download

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_update_permissions_returns_true_on_success(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """update_permissions returns True when permissions are successfully updated."""
        from zondarr.media.clients.plex import PlexClient

        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithPermissions(users=[mock_user])
        mock_server = MockPlexServerWithPermissions(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.update_permissions(
                    str(user_id), permissions={"can_download": True}
                )

                assert result is True

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_update_permissions_returns_false_when_user_not_found(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """update_permissions returns False when user is not found."""
        from zondarr.media.clients.plex import PlexClient

        # Empty user list - user won't be found
        mock_account = MockMyPlexAccountWithPermissions(users=[])
        mock_server = MockPlexServerWithPermissions(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.update_permissions(
                    str(user_id), permissions={"can_download": True}
                )

                assert result is False
                assert len(mock_account.update_friend_calls) == 0

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_update_permissions_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """update_permissions raises MediaClientError when client is not initialized."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.update_permissions(
                str(user_id), permissions={"can_download": True}
            )

        assert exc_info.value.operation == "update_permissions"
        assert exc_info.value.server_url == url

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_update_permissions_with_empty_dict_returns_true(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """update_permissions with empty dict returns True (no-op for existing user)."""
        from zondarr.media.clients.plex import PlexClient

        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithPermissions(users=[mock_user])
        mock_server = MockPlexServerWithPermissions(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.update_permissions(str(user_id), permissions={})

                assert result is True
                # No updateFriend call should be made for empty permissions
                assert len(mock_account.update_friend_calls) == 0


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


class MockPlexServerWithUserList:
    """Mock PlexServer that supports user listing."""

    url: str
    token: str
    friendlyName: str
    library: MockLibrary
    _account: MockMyPlexAccountWithUserList

    def __init__(
        self,
        url: str,
        token: str,
        *,
        friendly_name: str = "Test Server",
        account: MockMyPlexAccountWithUserList | None = None,
    ) -> None:
        self.url = url
        self.token = token
        self.friendlyName = friendly_name
        self.library = MockLibrary()
        self._account = account or MockMyPlexAccountWithUserList()

    def myPlexAccount(self) -> MockMyPlexAccountWithUserList:
        """Return the configured mock MyPlexAccount."""
        return self._account


class TestListUsersReturnsAllUsersAsExternalUserStructs:
    """
    Feature: plex-integration
    Property 10: List Users Returns All Users as ExternalUser Structs

    For any connected PlexClient, list_users() should return a sequence
    containing all Friends and Home Users, where each element is a valid
    ExternalUser with non-empty external_user_id and username.

    **Validates: Requirements 12.1, 12.2, 12.3**
    """

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        users_data=st.lists(
            st.tuples(
                st.integers(min_value=1, max_value=999999999),
                username_strategy,
                st.one_of(email_strategy, st.none()),
                st.booleans(),
            ),
            min_size=0,
            max_size=10,
        ),
    )
    @pytest.mark.asyncio
    async def test_list_users_returns_all_users(
        self,
        url: str,
        api_key: str,
        users_data: list[tuple[int, str, str | None, bool]],
    ) -> None:
        """list_users returns all Friends and Home Users as ExternalUser structs."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.types import ExternalUser

        # Create mock users
        mock_users = [
            MockMyPlexUserWithHome(
                user_id=user_id, username=username, email=email, home=is_home
            )
            for user_id, username, email, is_home in users_data
        ]
        mock_account = MockMyPlexAccountWithUserList(users=mock_users)
        mock_server = MockPlexServerWithUserList(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.list_users()

                # Should return same number of users
                assert len(result) == len(users_data)

                # Each result should be a valid ExternalUser
                for user in result:
                    assert isinstance(user, ExternalUser)
                    assert user.external_user_id  # non-empty
                    assert user.username is not None

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_list_users_maps_fields_correctly(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
        email: str,
    ) -> None:
        """list_users maps user fields correctly to ExternalUser."""
        from zondarr.media.clients.plex import PlexClient

        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=email, home=False
        )
        mock_account = MockMyPlexAccountWithUserList(users=[mock_user])
        mock_server = MockPlexServerWithUserList(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.list_users()

                assert len(result) == 1
                user = result[0]
                assert user.external_user_id == str(user_id)
                assert user.username == username
                assert user.email == email

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_list_users_returns_empty_for_no_users(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """list_users returns empty sequence when no users exist."""
        from zondarr.media.clients.plex import PlexClient

        mock_account = MockMyPlexAccountWithUserList(users=[])
        mock_server = MockPlexServerWithUserList(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.list_users()
                assert len(result) == 0

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_list_users_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """list_users raises MediaClientError when client is not initialized."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.list_users()

        assert exc_info.value.operation == "list_users"
        assert exc_info.value.server_url == url

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        error_message=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    )
    @pytest.mark.asyncio
    async def test_list_users_raises_on_api_failure(
        self,
        url: str,
        api_key: str,
        error_message: str,
    ) -> None:
        """list_users raises ExternalServiceError on API failure."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.clients.plex import PlexClient

        mock_account = MockMyPlexAccountWithUserList(
            users_error=RuntimeError(error_message)
        )
        mock_server = MockPlexServerWithUserList(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client.list_users()

                assert f"Plex ({url})" in exc_info.value.service_name


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


class TestErrorStructureContainsRequiredFields:
    """
    Feature: plex-integration
    Property 14: Error Structure Contains Required Fields

    For any MediaClientError raised by PlexClient, the error should contain
    non-empty operation field, and the server_url should match the client's
    configured URL.

    **Validates: Requirements 17.1**
    """

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_get_libraries_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """get_libraries error contains operation and server_url fields."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, should raise with proper error structure
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.get_libraries()

        error = exc_info.value
        # operation field must be non-empty
        assert error.operation
        assert len(error.operation) > 0
        assert error.operation == "get_libraries"
        # server_url must match client's configured URL
        assert error.server_url == url
        # cause field must be present (can be empty string but not None)
        assert error.cause is not None

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_user_email_required_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """create_user EMAIL_REQUIRED error contains operation and server_url fields."""
        from zondarr.media.clients.plex import PlexClient, PlexErrorCode
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.types import PlexUserType

        mock_server = MockPlexServer(url, api_key)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                # Try to create Friend without email
                with pytest.raises(MediaClientError) as exc_info:
                    _ = await client.create_user(
                        "testuser",
                        "password",
                        plex_user_type=PlexUserType.FRIEND,
                        email=None,
                    )

                error = exc_info.value
                # operation field must be non-empty
                assert error.operation
                assert len(error.operation) > 0
                assert error.operation == "create_user"
                # server_url must match client's configured URL
                assert error.server_url == url
                # error_code should be EMAIL_REQUIRED
                assert error.media_error_code == PlexErrorCode.EMAIL_REQUIRED
                # cause field must be present
                assert error.cause is not None

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_friend_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """create_friend error contains service_name field for external errors."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.clients.plex import PlexClient

        # Create mock that raises an error
        mock_account = MockMyPlexAccountWithInvite(
            invite_error=RuntimeError("Test API error")
        )
        mock_server = MockPlexServerWithAccount(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

                error = exc_info.value
                # service_name must contain the server URL
                assert f"Plex ({url})" in error.service_name

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_home_user_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        username: str,
    ) -> None:
        """create_home_user error contains service_name field for external errors."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.clients.plex import PlexClient

        # Create mock that raises an error
        mock_account = MockMyPlexAccountWithHomeUser(
            create_error=RuntimeError("Test API error")
        )
        mock_server = MockPlexServerWithHomeUserAccount(
            url, api_key, account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

                error = exc_info.value
                # service_name must contain the server URL
                assert f"Plex ({url})" in error.service_name

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.text(min_size=1, max_size=20).filter(lambda s: s.strip()),
    )
    @pytest.mark.asyncio
    async def test_delete_user_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        user_id: str,
    ) -> None:
        """delete_user error contains service_name field for external errors."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.clients.plex import PlexClient

        # Create mock that raises an error
        mock_account = MockMyPlexAccountWithUserList(
            users_error=RuntimeError("Test API error")
        )
        mock_server = MockPlexServerWithUserList(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client.delete_user(user_id)

                error = exc_info.value
                # service_name must contain the server URL
                assert f"Plex ({url})" in error.service_name

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_list_users_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """list_users error contains operation and server_url fields."""
        from zondarr.media.clients.plex import PlexClient
        from zondarr.media.exceptions import MediaClientError

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, should raise with proper error structure
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.list_users()

        error = exc_info.value
        # operation field must be non-empty
        assert error.operation
        assert len(error.operation) > 0
        assert error.operation == "list_users"
        # server_url must match client's configured URL
        assert error.server_url == url
        # cause field must be present
        assert error.cause is not None

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.text(min_size=1, max_size=20).filter(lambda s: s.strip()),
        library_ids=st.lists(
            st.integers(min_value=1, max_value=1000).map(str),
            min_size=0,
            max_size=5,
        ),
    )
    @pytest.mark.asyncio
    async def test_set_library_access_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        user_id: str,
        library_ids: list[str],
    ) -> None:
        """set_library_access error contains service_name field for external errors."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.clients.plex import PlexClient

        # Create mock that raises an error
        mock_account = MockMyPlexAccountWithUserList(
            users_error=RuntimeError("Test API error")
        )
        mock_server = MockPlexServerWithUserList(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client.set_library_access(user_id, library_ids)

                error = exc_info.value
                # service_name must contain the server URL
                assert f"Plex ({url})" in error.service_name

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.text(min_size=1, max_size=20).filter(lambda s: s.strip()),
        permissions=st.fixed_dictionaries({"can_download": st.booleans()}),
    )
    @pytest.mark.asyncio
    async def test_update_permissions_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        user_id: str,
        permissions: dict[str, bool],
    ) -> None:
        """update_permissions error contains service_name field for external errors."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.clients.plex import PlexClient

        # Create mock that raises an error
        mock_account = MockMyPlexAccountWithUserList(
            users_error=RuntimeError("Test API error")
        )
        mock_server = MockPlexServerWithUserList(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client.update_permissions(
                        user_id, permissions=permissions
                    )

                error = exc_info.value
                # service_name must contain the server URL
                assert f"Plex ({url})" in error.service_name

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_user_already_exists_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """USER_ALREADY_EXISTS error contains operation, server_url, and error_code."""
        from zondarr.media.clients.plex import PlexClient, PlexErrorCode
        from zondarr.media.exceptions import MediaClientError

        # Create mock that raises "already shared" error
        mock_account = MockMyPlexAccountWithInvite(
            invite_error=Exception("User is already shared with this server")
        )
        mock_server = MockPlexServerWithAccount(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(MediaClientError) as exc_info:
                    _ = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

                error = exc_info.value
                # operation field must be non-empty
                assert error.operation
                assert error.operation == "create_friend"
                # server_url must match client's configured URL
                assert error.server_url == url
                # error_code should be USER_ALREADY_EXISTS
                assert error.media_error_code == PlexErrorCode.USER_ALREADY_EXISTS
                # cause field must be present
                assert error.cause is not None

    @settings(max_examples=100)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_username_taken_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        username: str,
    ) -> None:
        """USERNAME_TAKEN error contains operation, server_url, and error_code."""
        from zondarr.media.clients.plex import PlexClient, PlexErrorCode
        from zondarr.media.exceptions import MediaClientError

        # Create mock that raises "username taken" error
        mock_account = MockMyPlexAccountWithHomeUser(
            create_error=Exception("Username is already taken")
        )
        mock_server = MockPlexServerWithHomeUserAccount(
            url, api_key, account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(MediaClientError) as exc_info:
                    _ = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

                error = exc_info.value
                # operation field must be non-empty
                assert error.operation
                assert error.operation == "create_home_user"
                # server_url must match client's configured URL
                assert error.server_url == url
                # error_code should be USERNAME_TAKEN
                assert error.media_error_code == PlexErrorCode.USERNAME_TAKEN
                # cause field must be present
                assert error.cause is not None
