"""Property-based tests for media client registry.

Feature: zondarr-foundation
Properties: 5, 6, 7
Validates: Requirements 4.2, 4.3, 4.4, 4.5
"""

from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import KNOWN_SERVER_TYPES
from zondarr.config import Settings
from zondarr.media.exceptions import UnknownServerTypeError
from zondarr.media.providers.jellyfin.client import JellyfinClient
from zondarr.media.providers.plex.client import PlexClient
from zondarr.media.registry import ClientRegistry, registry


def _make_descriptor(server_type: str, client_class: type) -> MagicMock:
    """Create a minimal mock ProviderDescriptor."""
    descriptor = MagicMock()
    metadata = MagicMock()
    metadata.server_type = server_type
    metadata.env_url_var = f"{server_type.upper()}_URL"
    metadata.env_api_key_var = f"{server_type.upper()}_API_KEY"
    descriptor.metadata = metadata
    descriptor.client_class = client_class
    return descriptor


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
server_type_strategy = st.sampled_from(KNOWN_SERVER_TYPES)


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    """Reset the registry before each test to ensure isolation."""
    registry.clear()
    registry.register(_make_descriptor("jellyfin", JellyfinClient))
    registry.register(_make_descriptor("plex", PlexClient))


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
        client = registry.create_client("jellyfin", url=url, api_key=api_key)

        assert isinstance(client, JellyfinClient)
        assert client.url == url
        assert client.api_key == api_key

    @settings(max_examples=50)
    @given(url=valid_url, api_key=valid_api_key)
    def test_plex_client_returned_for_plex_type(self, url: str, api_key: str) -> None:
        """Registry returns PlexClient for PLEX server type."""
        client = registry.create_client("plex", url=url, api_key=api_key)

        assert isinstance(client, PlexClient)
        assert client.url == url
        assert client.api_key == api_key

    @settings(max_examples=50)
    @given(server_type=server_type_strategy, url=valid_url, api_key=valid_api_key)
    def test_client_class_matches_registered_type(
        self, server_type: str, url: str, api_key: str
    ) -> None:
        """Registry returns the correct client class for any registered server type."""
        client_class = registry.get_client_class(server_type)
        client = registry.create_client(server_type, url=url, api_key=api_key)

        expected_client = client_class(url=url, api_key=api_key)
        assert type(client) is type(expected_client)

    @settings(max_examples=50)
    @given(server_type=server_type_strategy)
    def test_capabilities_match_client_class(self, server_type: str) -> None:
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
            _ = registry.get_client_class("jellyfin")

        assert exc_info.value.server_type == "jellyfin"
        assert exc_info.value.error_code == "UNKNOWN_SERVER_TYPE"

    @settings(max_examples=25)
    @given(url=valid_url, api_key=valid_api_key)
    def test_create_client_raises_for_unregistered_type(
        self, url: str, api_key: str
    ) -> None:
        """create_client raises UnknownServerTypeError for unregistered types."""
        registry.clear()

        with pytest.raises(UnknownServerTypeError) as exc_info:
            _ = registry.create_client("plex", url=url, api_key=api_key)

        assert exc_info.value.server_type == "plex"
        assert exc_info.value.error_code == "UNKNOWN_SERVER_TYPE"

    @settings(max_examples=25)
    @given(server_type=server_type_strategy)
    def test_get_capabilities_raises_for_unregistered_type(
        self, server_type: str
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
        server_type: str,
        url: str,
        api_key: str,
    ) -> None:
        """Registrations made on one instance are visible on all instances."""
        _ = server_type, url, api_key

        registry.clear()
        registry.register(_make_descriptor("jellyfin", JellyfinClient))

        new_instance = ClientRegistry()
        client_class = new_instance.get_client_class("jellyfin")

        assert client_class is JellyfinClient

    @settings(max_examples=25)
    @given(st.integers(min_value=2, max_value=5))
    def test_clear_affects_all_instances(self, num_instances: int) -> None:
        """Clearing the registry affects all instances."""
        registry.register(_make_descriptor("jellyfin", JellyfinClient))

        instances = [ClientRegistry() for _ in range(num_instances)]
        instances[0].clear()

        for instance in instances:
            with pytest.raises(UnknownServerTypeError):
                _ = instance.get_client_class("jellyfin")


class TestEffectiveCredentials:
    """Tests for env var credential overrides via _get_effective_credentials."""

    def test_returns_db_values_when_no_settings(self) -> None:
        """When _settings is None, DB values are returned unchanged."""
        url, api_key = registry._get_effective_credentials(  # pyright: ignore[reportPrivateUsage]
            "plex", db_url="http://db.url", db_api_key="db-key"
        )
        assert url == "http://db.url"
        assert api_key == "db-key"

    def test_returns_db_values_when_env_vars_not_set(self) -> None:
        """When settings exist but media env vars are None, DB values are used."""
        s = Settings(secret_key="a" * 32)
        registry.set_settings(s)

        url, api_key = registry._get_effective_credentials(  # pyright: ignore[reportPrivateUsage]
            "plex", db_url="http://db.url", db_api_key="db-key"
        )
        assert url == "http://db.url"
        assert api_key == "db-key"

    def test_plex_url_overrides_db_url(self) -> None:
        """Provider credentials URL overrides DB URL; api_key preserved from DB."""
        s = Settings(
            secret_key="a" * 32,
            provider_credentials={"plex": {"url": "http://env.plex"}},
        )
        registry.set_settings(s)

        url, api_key = registry._get_effective_credentials(  # pyright: ignore[reportPrivateUsage]
            "plex", db_url="http://db.url", db_api_key="db-key"
        )
        assert url == "http://env.plex"
        assert api_key == "db-key"

    def test_plex_token_overrides_db_api_key(self) -> None:
        """Provider credentials api_key overrides DB api_key; URL preserved from DB."""
        s = Settings(
            secret_key="a" * 32,
            provider_credentials={"plex": {"api_key": "env-token"}},
        )
        registry.set_settings(s)

        url, api_key = registry._get_effective_credentials(  # pyright: ignore[reportPrivateUsage]
            "plex", db_url="http://db.url", db_api_key="db-key"
        )
        assert url == "http://db.url"
        assert api_key == "env-token"

    def test_both_plex_env_vars_override_both_db_values(self) -> None:
        """Both provider URL and api_key override both DB values."""
        s = Settings(
            secret_key="a" * 32,
            provider_credentials={
                "plex": {"url": "http://env.plex", "api_key": "env-token"}
            },
        )
        registry.set_settings(s)

        url, api_key = registry._get_effective_credentials(  # pyright: ignore[reportPrivateUsage]
            "plex", db_url="http://db.url", db_api_key="db-key"
        )
        assert url == "http://env.plex"
        assert api_key == "env-token"

    def test_jellyfin_env_vars_override_db_values(self) -> None:
        """Jellyfin provider credentials override DB values."""
        s = Settings(
            secret_key="a" * 32,
            provider_credentials={
                "jellyfin": {"url": "http://env.jf", "api_key": "env-jf-key"}
            },
        )
        registry.set_settings(s)

        url, api_key = registry._get_effective_credentials(  # pyright: ignore[reportPrivateUsage]
            "jellyfin", db_url="http://db.url", db_api_key="db-key"
        )
        assert url == "http://env.jf"
        assert api_key == "env-jf-key"

    def test_plex_env_vars_do_not_affect_jellyfin(self) -> None:
        """Plex provider credentials don't leak into Jellyfin credential resolution."""
        s = Settings(
            secret_key="a" * 32,
            provider_credentials={
                "plex": {"url": "http://env.plex", "api_key": "env-plex-token"}
            },
        )
        registry.set_settings(s)

        url, api_key = registry._get_effective_credentials(  # pyright: ignore[reportPrivateUsage]
            "jellyfin", db_url="http://jf.db", db_api_key="jf-db-key"
        )
        assert url == "http://jf.db"
        assert api_key == "jf-db-key"

    def test_jellyfin_env_vars_do_not_affect_plex(self) -> None:
        """Jellyfin provider credentials don't leak into Plex credential resolution."""
        s = Settings(
            secret_key="a" * 32,
            provider_credentials={
                "jellyfin": {"url": "http://env.jf", "api_key": "env-jf-key"}
            },
        )
        registry.set_settings(s)

        url, api_key = registry._get_effective_credentials(  # pyright: ignore[reportPrivateUsage]
            "plex", db_url="http://plex.db", db_api_key="plex-db-key"
        )
        assert url == "http://plex.db"
        assert api_key == "plex-db-key"

    def test_create_client_for_server_uses_effective_credentials(self) -> None:
        """create_client_for_server resolves credentials and creates client."""
        s = Settings(
            secret_key="a" * 32,
            provider_credentials={
                "jellyfin": {"url": "http://env.jf:8096", "api_key": "env-api-key"}
            },
        )
        registry.set_settings(s)

        server = MagicMock()
        server.server_type = "jellyfin"
        server.url = "http://db.jf:8096"
        server.api_key = "db-api-key"

        client = registry.create_client_for_server(server)
        assert isinstance(client, JellyfinClient)
        assert client.url == "http://env.jf:8096"
        assert client.api_key == "env-api-key"

    def test_clear_resets_settings(self) -> None:
        """clear() resets _settings to None."""
        s = Settings(
            secret_key="a" * 32,
            provider_credentials={"plex": {"url": "http://env.plex"}},
        )
        registry.set_settings(s)
        registry.clear()

        url, api_key = registry._get_effective_credentials(  # pyright: ignore[reportPrivateUsage]
            "plex", db_url="http://db.url", db_api_key="db-key"
        )
        assert url == "http://db.url"
        assert api_key == "db-key"
