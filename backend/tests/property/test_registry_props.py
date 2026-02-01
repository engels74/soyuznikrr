"""Property-based tests for media client registry.

Feature: zondarr-foundation
Properties: 5, 6, 7
Validates: Requirements 4.2, 4.3, 4.4, 4.5
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from zondarr.media.clients.jellyfin import JellyfinClient
from zondarr.media.clients.plex import PlexClient
from zondarr.media.exceptions import UnknownServerTypeError
from zondarr.media.registry import ClientRegistry, registry
from zondarr.models.media_server import ServerType

# Strategy for valid URLs
valid_url = st.sampled_from(
    [
        "http://localhost:8096",
        "http://jellyfin.local:8096",
        "https://plex.example.com:32400",
        "http://192.168.1.100:8096",
    ]
)

# Strategy for valid API keys
valid_api_key = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=16,
    max_size=64,
)

# Strategy for server types
server_type_strategy = st.sampled_from(list(ServerType))


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    """Reset the registry before each test to ensure isolation."""
    registry.clear()
    registry.register(ServerType.JELLYFIN, JellyfinClient)
    registry.register(ServerType.PLEX, PlexClient)


class TestRegistryReturnsCorrectClient:
    """
    Feature: zondarr-foundation
    Property 5: Registry Returns Correct Client

    **Validates: Requirements 4.2, 4.3**
    """

    @settings(max_examples=50)
    @given(url=valid_url, api_key=valid_api_key)
    def test_jellyfin_client_returned_for_jellyfin_type(
        self, url: str, api_key: str
    ) -> None:
        """Registry returns JellyfinClient for JELLYFIN server type."""
        client = registry.create_client(ServerType.JELLYFIN, url=url, api_key=api_key)

        assert isinstance(client, JellyfinClient)
        assert client.url == url
        assert client.api_key == api_key

    @settings(max_examples=50)
    @given(url=valid_url, api_key=valid_api_key)
    def test_plex_client_returned_for_plex_type(self, url: str, api_key: str) -> None:
        """Registry returns PlexClient for PLEX server type."""
        client = registry.create_client(ServerType.PLEX, url=url, api_key=api_key)

        assert isinstance(client, PlexClient)
        assert client.url == url
        assert client.api_key == api_key

    @settings(max_examples=50)
    @given(server_type=server_type_strategy, url=valid_url, api_key=valid_api_key)
    def test_client_class_matches_registered_type(
        self, server_type: ServerType, url: str, api_key: str
    ) -> None:
        """Registry returns the correct client class for any registered server type."""
        client_class = registry.get_client_class(server_type)
        client = registry.create_client(server_type, url=url, api_key=api_key)

        expected_client = client_class(url=url, api_key=api_key)
        assert type(client) is type(expected_client)

    @settings(max_examples=50)
    @given(server_type=server_type_strategy)
    def test_capabilities_match_client_class(self, server_type: ServerType) -> None:
        """Registry capabilities match the client class capabilities."""
        client_class = registry.get_client_class(server_type)
        registry_caps = registry.get_capabilities(server_type)
        client_caps = client_class.capabilities()

        assert registry_caps == client_caps


class TestRegistryRaisesErrorForUnknownTypes:
    """
    Feature: zondarr-foundation
    Property 6: Registry Raises Error for Unknown Types

    **Validates: Requirements 4.4**
    """

    @settings(max_examples=25)
    @given(url=valid_url, api_key=valid_api_key)
    def test_get_client_class_raises_for_unregistered_type(
        self, url: str, api_key: str
    ) -> None:
        """get_client_class raises UnknownServerTypeError for unregistered types."""
        _ = url, api_key
        registry.clear()

        with pytest.raises(UnknownServerTypeError) as exc_info:
            _ = registry.get_client_class(ServerType.JELLYFIN)

        assert exc_info.value.server_type == ServerType.JELLYFIN
        assert exc_info.value.error_code == "UNKNOWN_SERVER_TYPE"

    @settings(max_examples=25)
    @given(url=valid_url, api_key=valid_api_key)
    def test_create_client_raises_for_unregistered_type(
        self, url: str, api_key: str
    ) -> None:
        """create_client raises UnknownServerTypeError for unregistered types."""
        registry.clear()

        with pytest.raises(UnknownServerTypeError) as exc_info:
            _ = registry.create_client(ServerType.PLEX, url=url, api_key=api_key)

        assert exc_info.value.server_type == ServerType.PLEX
        assert exc_info.value.error_code == "UNKNOWN_SERVER_TYPE"

    @settings(max_examples=25)
    @given(server_type=server_type_strategy)
    def test_get_capabilities_raises_for_unregistered_type(
        self, server_type: ServerType
    ) -> None:
        """get_capabilities raises UnknownServerTypeError for unregistered types."""
        registry.clear()

        with pytest.raises(UnknownServerTypeError) as exc_info:
            _ = registry.get_capabilities(server_type)

        assert exc_info.value.server_type == server_type
        assert exc_info.value.error_code == "UNKNOWN_SERVER_TYPE"


class TestRegistrySingletonBehavior:
    """
    Feature: zondarr-foundation
    Property 7: Registry Singleton Behavior

    **Validates: Requirements 4.5**
    """

    @settings(max_examples=25)
    @given(st.integers(min_value=2, max_value=10))
    def test_multiple_instantiations_return_same_instance(
        self, num_instances: int
    ) -> None:
        """Multiple ClientRegistry() calls return the same singleton instance."""
        instances = [ClientRegistry() for _ in range(num_instances)]

        first_instance = instances[0]
        for instance in instances[1:]:
            assert instance is first_instance

    @settings(max_examples=25)
    @given(url=valid_url, api_key=valid_api_key)
    def test_global_registry_is_singleton_instance(
        self, url: str, api_key: str
    ) -> None:
        """The global registry is the same as newly created instances."""
        _ = url, api_key
        new_instance = ClientRegistry()

        assert new_instance is registry

    @settings(max_examples=25)
    @given(server_type=server_type_strategy, url=valid_url, api_key=valid_api_key)
    def test_registration_visible_across_instances(
        self,
        server_type: ServerType,
        url: str,
        api_key: str,
    ) -> None:
        """Registrations made on one instance are visible on all instances."""
        _ = server_type, url, api_key

        registry.clear()
        registry.register(ServerType.JELLYFIN, JellyfinClient)

        new_instance = ClientRegistry()
        client_class = new_instance.get_client_class(ServerType.JELLYFIN)

        assert client_class is JellyfinClient

    @settings(max_examples=25)
    @given(st.integers(min_value=2, max_value=5))
    def test_clear_affects_all_instances(self, num_instances: int) -> None:
        """Clearing the registry affects all instances."""
        registry.register(ServerType.JELLYFIN, JellyfinClient)

        instances = [ClientRegistry() for _ in range(num_instances)]
        instances[0].clear()

        for instance in instances:
            with pytest.raises(UnknownServerTypeError):
                _ = instance.get_client_class(ServerType.JELLYFIN)
