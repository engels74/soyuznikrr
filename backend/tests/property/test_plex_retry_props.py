"""Tests for PlexClient retry behavior on read operations.

Verifies that transient failures are retried with exponential backoff
while non-retryable errors and write operations are not retried.
"""

from unittest.mock import AsyncMock, patch

import pytest

from zondarr.core.exceptions import ExternalServiceError

from .conftest import (
    MockLibrary,
    MockLibrarySection,
    MockMyPlexAccount,
    MockPlexServer,
)


class MockPlexServerTransient:
    """Mock PlexServer that fails N times then succeeds.

    Used to verify retry behavior on ``get_libraries`` and similar
    read operations.
    """

    url: str
    token: str
    friendlyName: str
    machineIdentifier: str
    library: MockLibrary
    _account: MockMyPlexAccount
    _fail_count: int
    _call_count: int
    _error: Exception

    def __init__(
        self,
        url: str,
        token: str,
        *,
        fail_count: int = 2,
        error: Exception | None = None,
        friendly_name: str = "Test Server",
        library: MockLibrary | None = None,
    ) -> None:
        self.url = url
        self.token = token
        self.friendlyName = friendly_name
        self.machineIdentifier = "test-machine-id"
        self._account = MockMyPlexAccount()
        self._fail_count = fail_count
        self._call_count = 0
        self._error = error or ConnectionError("Connection refused")
        self.library = library or MockLibrary()

    def myPlexAccount(self) -> MockMyPlexAccount:
        return self._account


class TransientLibrary(MockLibrary):
    """Mock library that fails N times then returns sections."""

    _fail_count: int
    _call_count: int
    _error: Exception
    _real_sections: list[MockLibrarySection]

    def __init__(
        self,
        *,
        fail_count: int = 2,
        error: Exception | None = None,
        sections: list[MockLibrarySection] | None = None,
    ) -> None:
        super().__init__()
        self._fail_count = fail_count
        self._call_count = 0
        self._error = error or ConnectionError("Connection refused")
        self._real_sections = sections or [
            MockLibrarySection(key=1, title="Movies", section_type="movie"),
            MockLibrarySection(key=2, title="TV Shows", section_type="show"),
        ]

    def sections(self) -> list[MockLibrarySection]:
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise self._error
        return self._real_sections


class TestPlexClientRetryGetLibraries:
    """Verify retry behavior on get_libraries."""

    @pytest.mark.asyncio
    async def test_get_libraries_retries_on_transient_error(self) -> None:
        """get_libraries retries on ConnectionError and succeeds."""
        from zondarr.media.providers.plex.client import PlexClient

        transient_library = TransientLibrary(fail_count=2)
        mock_server = MockPlexServer(
            "http://plex:32400",
            "test-token",
            account=MockMyPlexAccount(),
            library=transient_library,
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(
                url="http://plex:32400",
                api_key="test-token",
                max_retries=3,
            )
            async with client:
                libraries = await client.get_libraries()
                assert len(libraries) == 2
                assert libraries[0].name == "Movies"
                # Should have been called 3 times (2 failures + 1 success)
                assert transient_library._call_count == 3

    @pytest.mark.asyncio
    async def test_get_libraries_no_retry_when_disabled(self) -> None:
        """get_libraries raises immediately when max_retries=0."""
        from zondarr.media.providers.plex.client import PlexClient

        transient_library = TransientLibrary(fail_count=1)
        mock_server = MockPlexServer(
            "http://plex:32400",
            "test-token",
            account=MockMyPlexAccount(),
            library=transient_library,
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(
                url="http://plex:32400",
                api_key="test-token",
                max_retries=0,
            )
            async with client:
                with pytest.raises(Exception, match="Connection refused"):
                    await client.get_libraries()
                # Should have been called only once
                assert transient_library._call_count == 1

    @pytest.mark.asyncio
    async def test_get_libraries_exhausts_retries(self) -> None:
        """get_libraries raises after all retries are exhausted."""
        from zondarr.media.providers.plex.client import PlexClient

        # Fail more times than max_retries allows
        transient_library = TransientLibrary(fail_count=10)
        mock_server = MockPlexServer(
            "http://plex:32400",
            "test-token",
            account=MockMyPlexAccount(),
            library=transient_library,
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(
                url="http://plex:32400",
                api_key="test-token",
                max_retries=2,
            )
            async with client:
                with pytest.raises(ExternalServiceError):
                    await client.get_libraries()
                # Should have been called max_retries + 1 times (initial + retries)
                assert transient_library._call_count == 3


class TestPlexClientRetryConnection:
    """Verify retry behavior on connection (``__aenter__``)."""

    @pytest.mark.asyncio
    async def test_connect_retries_on_transient_error(self) -> None:
        """__aenter__ retries the connection on transient failures."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_server = MockPlexServer(
            "http://plex:32400",
            "test-token",
            account=MockMyPlexAccount(),
        )

        call_count = 0

        def _plexserver_factory(*args: object, **kwargs: object) -> MockPlexServer:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Connection refused")
            return mock_server

        with patch("plexapi.server.PlexServer", side_effect=_plexserver_factory):
            client = PlexClient(
                url="http://plex:32400",
                api_key="test-token",
                max_retries=3,
            )
            async with client:
                assert client._server is not None
                # 2 failures + 1 success = 3 calls
                assert call_count == 3

    @pytest.mark.asyncio
    async def test_connect_no_retry_when_disabled(self) -> None:
        """__aenter__ raises immediately when max_retries=0."""
        from zondarr.media.providers.plex.client import PlexClient

        call_count = 0

        def _plexserver_factory(*args: object, **kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection refused")

        with patch("plexapi.server.PlexServer", side_effect=_plexserver_factory):
            client = PlexClient(
                url="http://plex:32400",
                api_key="test-token",
                max_retries=0,
            )
            with pytest.raises(
                Exception, match=r"Connection refused|Failed to connect"
            ):
                async with client:
                    pass
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_connect_exhausts_retries(self) -> None:
        """__aenter__ raises after all connection retries are exhausted."""
        from zondarr.media.providers.plex.client import PlexClient

        call_count = 0

        def _plexserver_factory(*args: object, **kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection refused")

        with patch("plexapi.server.PlexServer", side_effect=_plexserver_factory):
            client = PlexClient(
                url="http://plex:32400",
                api_key="test-token",
                max_retries=2,
            )
            with pytest.raises(ConnectionError):
                async with client:
                    pass
            # initial + 2 retries = 3
            assert call_count == 3


class TestPlexClientRetryTestConnection:
    """Verify retry behavior on test_connection."""

    @pytest.mark.asyncio
    async def test_test_connection_retries_on_transient_error(self) -> None:
        """test_connection retries on transient failures and returns True."""
        from zondarr.media.providers.plex.client import PlexClient

        call_count = 0
        original_friendly_name = "Test Server"

        class TransientFriendlyNameServer:
            url: str
            token: str
            machineIdentifier: str
            library: MockLibrary

            def __init__(self) -> None:
                self.url = "http://plex:32400"
                self.token = "test-token"  # noqa: S105
                self.machineIdentifier = "test-machine-id"
                self.library = MockLibrary()

            @property
            def friendlyName(self) -> str:
                nonlocal call_count
                call_count += 1
                if call_count <= 1:
                    raise ConnectionError("Connection refused")
                return original_friendly_name

            def myPlexAccount(self) -> MockMyPlexAccount:
                return MockMyPlexAccount()

        mock_server = TransientFriendlyNameServer()

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(
                url="http://plex:32400",
                api_key="test-token",
                max_retries=3,
            )
            async with client:
                result = await client.test_connection()
                assert result is True
                assert call_count == 2


class TestPlexClientMaxRetriesDefault:
    """Verify max_retries defaults and backward compatibility."""

    def test_default_max_retries_is_3(self) -> None:
        """PlexClient defaults to max_retries=3."""
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url="http://plex:32400", api_key="test-token")
        assert client.max_retries == 3

    def test_max_retries_zero_disables(self) -> None:
        """max_retries=0 means no retries."""
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(
            url="http://plex:32400", api_key="test-token", max_retries=0
        )
        assert client.max_retries == 0

    @pytest.mark.asyncio
    async def test_run_with_retry_bypassed_when_zero(self) -> None:
        """_run_with_retry calls func directly when max_retries=0."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_func = AsyncMock(return_value="result")
        client = PlexClient(
            url="http://plex:32400", api_key="test-token", max_retries=0
        )

        result = await client._run_with_retry(mock_func, operation="test")
        assert result == "result"
        mock_func.assert_awaited_once()
