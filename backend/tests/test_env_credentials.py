"""Tests for environment credential detection endpoint.

Tests for:
- mask_api_key helper (unit tests)
- GET /api/v1/servers/env-credentials endpoint (integration tests)
"""

from collections.abc import AsyncGenerator

import pytest
from litestar import Litestar
from litestar.datastructures import State
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.servers import (
    ServerController,
    mask_api_key,
)
from zondarr.config import Settings
from zondarr.media.providers.jellyfin import JellyfinProvider
from zondarr.media.providers.plex import PlexProvider
from zondarr.media.registry import registry

# Type alias for JSON credential dicts returned by the endpoint
type CredentialDict = dict[str, object]


def _make_test_settings(
    provider_credentials: dict[str, dict[str, str]] | None = None,
) -> Settings:
    """Create a Settings instance for testing."""
    return Settings(
        secret_key="a" * 32,
        provider_credentials=provider_credentials or {},
    )


def _ensure_registry() -> None:
    """Ensure the global registry has providers registered.

    Other tests may call registry.clear(), so we force re-registration
    unconditionally to avoid flaky ordering issues in parallel test runs.
    """
    if not registry.registered_types():
        registry.register(PlexProvider())
        registry.register(JellyfinProvider())


def _make_test_app(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> Litestar:
    """Create a Litestar test app with the ServerController."""
    _ensure_registry()

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def provide_settings_fn(state: State) -> Settings:
        return state.settings  # pyright: ignore[reportAny]

    return Litestar(
        route_handlers=[ServerController],
        state=State({"settings": settings}),
        dependencies={
            "session": Provide(provide_session),
            "settings": Provide(provide_settings_fn, sync_to_thread=False),
        },
    )


def _get_credentials(response_json: dict[str, object]) -> list[CredentialDict]:
    """Extract credentials list from response JSON with proper typing."""
    creds = response_json["credentials"]
    assert isinstance(creds, list)
    result: list[CredentialDict] = creds  # pyright: ignore[reportUnknownVariableType]
    return result


# =============================================================================
# Unit tests for mask_api_key
# =============================================================================


class TestMaskApiKey:
    """Unit tests for the mask_api_key helper."""

    def test_short_key_all_masked(self) -> None:
        """Keys shorter than 6 chars are fully masked."""
        assert mask_api_key("abc") == "***"
        assert mask_api_key("ab") == "**"
        assert mask_api_key("a") == "*"
        assert mask_api_key("12345") == "*****"

    def test_medium_key_shows_first2_last2(self) -> None:
        """Keys 6-11 chars show first 2 and last 2."""
        assert mask_api_key("abcdef") == "ab**ef"
        assert mask_api_key("abcdefgh") == "ab****gh"
        assert mask_api_key("abcdefghijk") == "ab*******jk"

    def test_long_key_shows_first4_last4(self) -> None:
        """Keys >= 12 chars show first 4 and last 4."""
        assert mask_api_key("abcdefghijkl") == "abcd****ijkl"
        assert mask_api_key("1234567890abcdef") == "1234********cdef"

    def test_boundary_at_6(self) -> None:
        """Key of exactly 6 chars uses medium masking."""
        result = mask_api_key("123456")
        assert result == "12**56"
        assert len(result) == 6

    def test_boundary_at_12(self) -> None:
        """Key of exactly 12 chars uses long masking."""
        result = mask_api_key("123456789012")
        assert result == "1234****9012"
        assert len(result) == 12

    def test_mask_preserves_length(self) -> None:
        """Masked output has the same length as input."""
        for key in ["a", "ab", "abc", "abcdef", "abcdefghij", "abcdefghijklmnop"]:
            assert len(mask_api_key(key)) == len(key)


# =============================================================================
# Integration tests for GET /api/v1/servers/env-credentials
# =============================================================================


class TestEnvCredentialsEndpoint:
    """Integration tests for the env-credentials endpoint."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_env_vars(self) -> None:
        """Returns empty credentials list when no env vars are set."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_test_settings()
            app = _make_test_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.get("/api/v1/servers/env-credentials")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["credentials"] == []
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_returns_detected_providers(self) -> None:
        """Returns detected providers when env vars are set."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_test_settings(
                provider_credentials={
                    "plex": {
                        "url": "http://plex.local:32400",
                        "api_key": "my-plex-token-here",
                    },
                }
            )
            app = _make_test_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.get("/api/v1/servers/env-credentials")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                creds = _get_credentials(data)
                assert len(creds) >= 1

                plex_cred: CredentialDict | None = next(
                    (c for c in creds if c["server_type"] == "plex"), None
                )
                assert plex_cred is not None
                assert plex_cred["url"] == "http://plex.local:32400"
                assert plex_cred["api_key"] == "my-plex-token-here"
                assert plex_cred["has_url"] is True
                assert plex_cred["has_api_key"] is True
                assert plex_cred["display_name"] == "Plex"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_only_includes_providers_with_credentials(self) -> None:
        """Only returns providers that have at least one env var set."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            # Set creds for plex only, not jellyfin
            settings = _make_test_settings(
                provider_credentials={
                    "plex": {"url": "http://plex.local:32400"},
                }
            )
            app = _make_test_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.get("/api/v1/servers/env-credentials")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                creds = _get_credentials(data)
                server_types: list[object] = [c["server_type"] for c in creds]
                assert "plex" in server_types
                assert "jellyfin" not in server_types
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_masked_key_format(self) -> None:
        """Masked API key is properly formatted."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_test_settings(
                provider_credentials={
                    "plex": {
                        "url": "http://plex.local:32400",
                        "api_key": "abcdefghijklmnop",
                    },
                }
            )
            app = _make_test_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.get("/api/v1/servers/env-credentials")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                creds = _get_credentials(data)
                plex_cred: CredentialDict = next(
                    c for c in creds if c["server_type"] == "plex"
                )
                # 16 char key: first 4 + 8 stars + last 4
                assert plex_cred["masked_api_key"] == "abcd********mnop"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_partial_credentials_url_only(self) -> None:
        """Provider with only URL set has has_api_key=false."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_test_settings(
                provider_credentials={
                    "plex": {"url": "http://plex.local:32400"},
                }
            )
            app = _make_test_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.get("/api/v1/servers/env-credentials")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                creds = _get_credentials(data)
                plex_cred: CredentialDict = next(
                    c for c in creds if c["server_type"] == "plex"
                )
                assert plex_cred["has_url"] is True
                assert plex_cred["has_api_key"] is False
                assert plex_cred["api_key"] is None
                assert plex_cred["masked_api_key"] is None
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_multiple_providers_detected(self) -> None:
        """Multiple providers are returned when multiple env vars are set."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_test_settings(
                provider_credentials={
                    "plex": {
                        "url": "http://plex.local:32400",
                        "api_key": "plex-token-12345",
                    },
                    "jellyfin": {
                        "url": "http://jellyfin.local:8096",
                        "api_key": "jellyfin-key-12345",
                    },
                }
            )
            app = _make_test_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.get("/api/v1/servers/env-credentials")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                creds = _get_credentials(data)
                server_types: set[object] = {c["server_type"] for c in creds}
                assert "plex" in server_types
                assert "jellyfin" in server_types
        finally:
            await engine.dispose()
