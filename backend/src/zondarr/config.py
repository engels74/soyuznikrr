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
        "expiration_check_interval_seconds": int(
            os.environ.get("EXPIRATION_CHECK_INTERVAL_SECONDS", "3600")
        ),
        "sync_interval_seconds": int(os.environ.get("SYNC_INTERVAL_SECONDS", "900")),
    }

    # msgspec.convert validates constraints
    settings = msgspec.convert(settings_dict, Settings)

    return settings
