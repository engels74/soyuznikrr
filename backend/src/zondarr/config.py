"""Application configuration with environment variable loading.

Uses msgspec.Struct for high-performance serialization and validation.
"""

import os
from typing import Annotated

import msgspec


class Settings(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Application settings loaded from environment variables.

    Uses Python 3.14 deferred annotations - no forward reference quotes needed.
    """

    # Database
    database_url: Annotated[
        str,
        msgspec.Meta(
            description="Database connection URL (sqlite+aiosqlite:// or postgresql+asyncpg://)"
        ),
    ] = "sqlite+aiosqlite:///./zondarr.db"

    # Server
    host: str = "0.0.0.0"  # noqa: S104
    port: Annotated[int, msgspec.Meta(ge=1, le=65535)] = 8000
    debug: bool = False
    skip_auth: bool = False

    # CORS
    cors_origins: Annotated[
        list[str],
        msgspec.Meta(
            description=(
                "Allowed CORS origins (empty = CORS disabled)."
                " From comma-separated CORS_ORIGINS env var."
            )
        ),
    ] = []

    # Security
    secret_key: Annotated[str, msgspec.Meta(min_length=32)]
    secure_cookies: Annotated[
        bool,
        msgspec.Meta(
            description="Set True when serving over HTTPS to enforce Secure flag on cookies"
        ),
    ] = False

    # CSRF origin for origin-based CSRF protection
    csrf_origin: Annotated[
        str | None,
        msgspec.Meta(
            description="Trusted origin for CSRF protection (e.g., https://zondarr.example.com)"
        ),
    ] = None

    # Bootstrap token for initial admin setup
    bootstrap_token: str | None = None

    # File path to write the bootstrap token to (for frontend SSR to read)
    bootstrap_token_file: str | None = None

    # Dynamic provider credentials populated from env vars
    # Keyed by server_type (e.g., "plex", "jellyfin")
    # Each value is a dict with "url" and "api_key" keys
    provider_credentials: dict[str, dict[str, str]] = {}

    # Background task intervals (in seconds)
    expiration_check_interval_seconds: Annotated[
        int,
        msgspec.Meta(
            ge=60,
            description="Interval in seconds for checking expired invitations (default: 1 hour)",
        ),
    ] = 3600
    sync_interval_seconds: Annotated[
        int,
        msgspec.Meta(
            ge=60,
            description="Interval in seconds for syncing media servers (default: 15 minutes)",
        ),
    ] = 900

    # Per-server sync timeout (seconds) — wraps each server's library + user
    # sync in asyncio.wait_for to prevent a single slow server from blocking
    # the entire sync cycle
    sync_per_server_timeout_seconds: Annotated[
        int,
        msgspec.Meta(
            ge=30,
            description="Timeout in seconds for syncing a single media server (default: 300)",
        ),
    ] = 300

    # Retry / circuit-breaker settings for media-server sync
    sync_max_retries: Annotated[
        int,
        msgspec.Meta(
            ge=0,
            le=10,
            description="Maximum retry attempts per server sync operation (default: 2)",
        ),
    ] = 2
    sync_backoff_base_seconds: Annotated[
        float,
        msgspec.Meta(
            ge=0.5,
            le=60.0,
            description="Base delay in seconds for exponential backoff between retries (default: 2.0)",
        ),
    ] = 2.0
    sync_circuit_failure_threshold: Annotated[
        int,
        msgspec.Meta(
            ge=1,
            le=20,
            description="Consecutive failures before circuit breaker opens (default: 3)",
        ),
    ] = 3
    sync_circuit_recovery_seconds: Annotated[
        int,
        msgspec.Meta(
            ge=60,
            le=3600,
            description="Seconds before a tripped circuit breaker allows a retry (default: 300)",
        ),
    ] = 300

    # Plex API timeout (seconds) — applies to plexapi requests.Session
    # and as an asyncio.wait_for safety net around all PlexClient operations
    plex_api_timeout_seconds: Annotated[
        int,
        msgspec.Meta(
            ge=5,
            description="Timeout in seconds for Plex API requests (default: 30)",
        ),
    ] = 30

    # Allow media server URLs pointing to private/internal networks.
    # Default True because Zondarr is self-hosted and most users run
    # Plex/Jellyfin on the same LAN.  Set False in multi-tenant or
    # public-facing deployments to block SSRF to internal hosts.
    allow_private_networks: Annotated[
        bool,
        msgspec.Meta(
            description="Allow media server URLs targeting private/internal IP ranges (default: True)",
        ),
    ] = True

    # Test credentials for E2E OAuth flow testing (debug-only)
    plex_test_token: str | None = None
    plex_test_email: str | None = None


def load_settings() -> Settings:
    """Load and validate settings from environment variables.

    Uses walrus operator for cleaner required value handling.
    Raises ConfigurationError if required values are missing.
    """
    from .core.exceptions import ConfigurationError

    # Check required values first (fail fast)
    if (secret_key := os.environ.get("SECRET_KEY")) is None:
        raise ConfigurationError(
            "SECRET_KEY environment variable is required",
            "MISSING_CONFIG",
            field="SECRET_KEY",
        )

    # Build settings dict for validation via msgspec.convert
    settings_dict = {
        "database_url": os.environ.get(
            "DATABASE_URL", "sqlite+aiosqlite:///./zondarr.db"
        ),
        "host": os.environ.get("HOST", "0.0.0.0"),  # noqa: S104
        "port": int(os.environ.get("PORT", "8000")),
        "debug": os.environ.get("DEBUG", "").lower() in ("true", "1", "yes"),
        "skip_auth": (
            os.environ.get("DEV_SKIP_AUTH", "").lower() in ("true", "1", "yes")
            and os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")
        ),
        "cors_origins": [
            origin.strip()
            for origin in os.environ.get("CORS_ORIGINS", "").split(",")
            if origin.strip()
        ],
        "secret_key": secret_key,
        "secure_cookies": os.environ.get("SECURE_COOKIES", "").lower()
        in ("true", "1", "yes"),
        "csrf_origin": os.environ.get("CSRF_ORIGIN") or None,
        "expiration_check_interval_seconds": int(
            os.environ.get("EXPIRATION_CHECK_INTERVAL_SECONDS", "3600")
        ),
        "sync_interval_seconds": int(os.environ.get("SYNC_INTERVAL_SECONDS", "900")),
        "bootstrap_token": os.environ.get("BOOTSTRAP_TOKEN") or None,
        "bootstrap_token_file": os.environ.get("BOOTSTRAP_TOKEN_FILE") or None,
        "sync_per_server_timeout_seconds": int(
            os.environ.get("SYNC_PER_SERVER_TIMEOUT_SECONDS", "300")
        ),
        "sync_max_retries": int(os.environ.get("SYNC_MAX_RETRIES", "2")),
        "sync_backoff_base_seconds": float(
            os.environ.get("SYNC_BACKOFF_BASE_SECONDS", "2.0")
        ),
        "sync_circuit_failure_threshold": int(
            os.environ.get("SYNC_CIRCUIT_FAILURE_THRESHOLD", "3")
        ),
        "sync_circuit_recovery_seconds": int(
            os.environ.get("SYNC_CIRCUIT_RECOVERY_SECONDS", "300")
        ),
        "plex_api_timeout_seconds": int(
            os.environ.get("PLEX_API_TIMEOUT_SECONDS", "30")
        ),
        "allow_private_networks": os.environ.get("ALLOW_PRIVATE_NETWORKS", "").lower()
        not in ("false", "0", "no"),
        "plex_test_token": os.environ.get("PLEX_TEST_TOKEN") or None,
        "plex_test_email": os.environ.get("PLEX_TEST_EMAIL") or None,
    }

    # msgspec.convert validates constraints
    settings = msgspec.convert(settings_dict, Settings)

    return settings
