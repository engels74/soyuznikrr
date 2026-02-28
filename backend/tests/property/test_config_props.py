"""Property-based tests for configuration module.

Feature: zondarr-foundation
Properties: 1, 2
"""

import os

import msgspec
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from zondarr.config import load_settings
from zondarr.core.exceptions import ConfigurationError

# Strategy for valid secret keys (min 32 chars)
valid_secret_key = st.text(
    alphabet=st.characters(categories=("L", "N", "P")),
    min_size=32,
    max_size=128,
)

# Strategy for valid port numbers
valid_port = st.integers(min_value=1, max_value=65535)

# Strategy for valid host strings
valid_host = st.sampled_from(["0.0.0.0", "127.0.0.1", "localhost", "::1"])  # noqa: S104

# Strategy for valid database URLs
valid_database_url = st.sampled_from(
    [
        "sqlite+aiosqlite:///./test.db",
        "sqlite+aiosqlite:///:memory:",
        "postgresql+asyncpg://user:pass@localhost/db",
    ]
)

# Strategy for debug flag values
debug_values = st.sampled_from(["true", "false", "1", "0", "yes", "no", ""])


class TestConfigurationLoadingWithDefaults:
    """
    Feature: zondarr-foundation
    Property 1: Configuration Loading with Defaults
    """

    @settings(max_examples=25)
    @given(secret_key=valid_secret_key)
    def test_loads_with_only_required_values(self, secret_key: str) -> None:
        """Configuration loads successfully with only SECRET_KEY provided."""
        env_vars = ["SECRET_KEY", "DATABASE_URL", "HOST", "PORT", "DEBUG"]
        original_env: dict[str, str | None] = {}
        for var in env_vars:
            original_env[var] = os.environ.pop(var, None)

        try:
            os.environ["SECRET_KEY"] = secret_key

            result = load_settings()

            assert result.secret_key == secret_key
            assert result.database_url == "sqlite+aiosqlite:///./zondarr.db"
            assert result.host == "0.0.0.0"  # noqa: S104
            assert result.port == 8000
            assert result.debug is False
        finally:
            for var, value in original_env.items():
                if value is not None:
                    os.environ[var] = value
                elif var in os.environ:
                    del os.environ[var]

    @settings(max_examples=25)
    @given(
        secret_key=valid_secret_key,
        database_url=valid_database_url,
        host=valid_host,
        port=valid_port,
        debug=debug_values,
    )
    def test_loads_with_all_values_provided(
        self,
        secret_key: str,
        database_url: str,
        host: str,
        port: int,
        debug: str,
    ) -> None:
        """Configuration loads successfully with all values provided."""
        env_vars = ["SECRET_KEY", "DATABASE_URL", "HOST", "PORT", "DEBUG"]
        original_env: dict[str, str | None] = {}
        for var in env_vars:
            original_env[var] = os.environ.pop(var, None)

        try:
            os.environ["SECRET_KEY"] = secret_key
            os.environ["DATABASE_URL"] = database_url
            os.environ["HOST"] = host
            os.environ["PORT"] = str(port)
            os.environ["DEBUG"] = debug

            result = load_settings()

            assert result.secret_key == secret_key
            assert result.database_url == database_url
            assert result.host == host
            assert result.port == port
            assert result.debug == (debug.lower() in ("true", "1", "yes"))
        finally:
            for var, value in original_env.items():
                if value is not None:
                    os.environ[var] = value
                elif var in os.environ:
                    del os.environ[var]


class TestConfigurationValidationFailsFast:
    """
    Feature: zondarr-foundation
    Property 2: Configuration Validation Fails Fast
    """

    @settings(max_examples=25)
    @given(
        database_url=valid_database_url,
        host=valid_host,
        port=valid_port,
        debug=debug_values,
    )
    def test_fails_without_secret_key(
        self,
        database_url: str,
        host: str,
        port: int,
        debug: str,
    ) -> None:
        """Configuration fails fast when SECRET_KEY is missing."""
        env_vars = ["SECRET_KEY", "DATABASE_URL", "HOST", "PORT", "DEBUG"]
        original_env: dict[str, str | None] = {}
        for var in env_vars:
            original_env[var] = os.environ.pop(var, None)

        try:
            os.environ["DATABASE_URL"] = database_url
            os.environ["HOST"] = host
            os.environ["PORT"] = str(port)
            os.environ["DEBUG"] = debug

            with pytest.raises(ConfigurationError) as exc_info:
                _ = load_settings()

            assert "SECRET_KEY" in str(exc_info.value)
            assert exc_info.value.error_code == "MISSING_CONFIG"
            assert exc_info.value.context.get("field") == "SECRET_KEY"
        finally:
            for var, value in original_env.items():
                if value is not None:
                    os.environ[var] = value
                elif var in os.environ:
                    del os.environ[var]

    @settings(max_examples=25)
    @given(short_key=st.text(min_size=0, max_size=31).filter(lambda x: "\x00" not in x))
    def test_fails_with_short_secret_key(self, short_key: str) -> None:
        """Configuration fails when SECRET_KEY is too short (< 32 chars)."""
        env_vars = ["SECRET_KEY", "DATABASE_URL", "HOST", "PORT", "DEBUG"]
        original_env: dict[str, str | None] = {}
        for var in env_vars:
            original_env[var] = os.environ.pop(var, None)

        try:
            os.environ["SECRET_KEY"] = short_key

            with pytest.raises((msgspec.ValidationError, ConfigurationError)):
                _ = load_settings()
        finally:
            for var, value in original_env.items():
                if value is not None:
                    os.environ[var] = value
                elif var in os.environ:
                    del os.environ[var]

    @settings(max_examples=25)
    @given(
        secret_key=valid_secret_key,
        invalid_port=st.one_of(
            st.integers(max_value=0),
            st.integers(min_value=65536),
        ),
    )
    def test_fails_with_invalid_port(self, secret_key: str, invalid_port: int) -> None:
        """Configuration fails when PORT is outside valid range."""
        env_vars = ["SECRET_KEY", "DATABASE_URL", "HOST", "PORT", "DEBUG"]
        original_env: dict[str, str | None] = {}
        for var in env_vars:
            original_env[var] = os.environ.pop(var, None)

        try:
            os.environ["SECRET_KEY"] = secret_key
            os.environ["PORT"] = str(invalid_port)

            with pytest.raises(msgspec.ValidationError):
                _ = load_settings()
        finally:
            for var, value in original_env.items():
                if value is not None:
                    os.environ[var] = value
                elif var in os.environ:
                    del os.environ[var]
