"""Property-based tests for PlexClient context manager and capabilities.

Feature: plex-integration
Properties: Context Manager Round-Trip, Capabilities Declaration
"""

from unittest.mock import patch

import pytest
from hypothesis import given, settings

from zondarr.media.types import Capability

from .conftest import (
    MockMyPlexAccount,
    MockPlexServer,
    api_key_strategy,
    server_name_strategy,
    url_strategy,
)


class TestContextManagerRoundTrip:
    """
    Feature: plex-integration
    Property 1: Context Manager Round-Trip

    For any PlexClient instance with valid URL and API key, entering the async
    context and then exiting should result in the client being in a clean state
    with _server and _account set to None.
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
        from zondarr.media.providers.plex.client import PlexClient

        # Create mock server that will be returned by PlexServer constructor
        mock_server = MockPlexServer(
            url, api_key, friendly_name=server_name, account=MockMyPlexAccount()
        )

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
        from zondarr.media.providers.plex.client import PlexClient

        mock_server = MockPlexServer(url, api_key, account=MockMyPlexAccount())

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
        from zondarr.media.providers.plex.client import PlexClient

        mock_server = MockPlexServer(url, api_key, account=MockMyPlexAccount())

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

    PlexClient declares CREATE_USER, DELETE_USER, LIBRARY_ACCESS, and
    REMOVE_SHARED_ACCESS capabilities.
    It does NOT declare ENABLE_DISABLE_USER or DOWNLOAD_PERMISSION.
    """

    @pytest.mark.parametrize(
        "capability",
        [
            Capability.CREATE_USER,
            Capability.DELETE_USER,
            Capability.LIBRARY_ACCESS,
            Capability.REMOVE_SHARED_ACCESS,
        ],
        ids=lambda c: c.name,
    )
    def test_capabilities_includes(self, capability: Capability) -> None:
        """PlexClient declares expected capabilities."""
        from zondarr.media.providers.plex.client import PlexClient

        assert capability in PlexClient.capabilities()

    @pytest.mark.parametrize(
        "capability",
        [
            Capability.ENABLE_DISABLE_USER,
            Capability.DOWNLOAD_PERMISSION,
        ],
        ids=lambda c: c.name,
    )
    def test_capabilities_excludes(self, capability: Capability) -> None:
        """PlexClient does NOT declare unsupported capabilities."""
        from zondarr.media.providers.plex.client import PlexClient

        assert capability not in PlexClient.capabilities()

    def test_capabilities_returns_expected_count(self) -> None:
        """PlexClient declares exactly 4 capabilities."""
        from zondarr.media.providers.plex.client import PlexClient

        capabilities = PlexClient.capabilities()
        assert len(capabilities) == 4
