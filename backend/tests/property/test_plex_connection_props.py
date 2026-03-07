"""Property-based tests for PlexClient connection testing.

Feature: plex-integration
Property: Connection Test Return Value Correctness
"""

from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from .conftest import (
    MockLibrary,
    MockMyPlexAccount,
    MockPlexServer,
    api_key_strategy,
    server_name_strategy,
    url_strategy,
)


class MockPlexServerWithError:
    """Mock PlexServer that raises an error when friendlyName is accessed.

    This cannot use the generic MockPlexServer because friendlyName must be
    a @property that raises, not a plain attribute.
    """

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
        from zondarr.media.providers.plex.client import PlexClient

        mock_server = MockPlexServer(
            url, api_key, friendly_name=server_name, account=MockMyPlexAccount()
        )

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
        from zondarr.media.providers.plex.client import PlexClient

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
        from zondarr.media.providers.plex.client import PlexClient

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
        from zondarr.media.providers.plex.client import PlexClient

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
