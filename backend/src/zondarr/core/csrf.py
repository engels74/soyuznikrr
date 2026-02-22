"""Origin-based CSRF protection middleware.

Validates the Origin (or Referer) header on state-changing requests against
a configured trusted origin. Simpler than token-based CSRF for a Docker-
distributed app behind reverse proxies.

The middleware checks:
1. Settings.csrf_origin (env var — fast, no DB hit)
2. Database app_settings table with a 60-second TTL cache
3. If no origin configured, allows all requests with a one-time warning
"""

import time
from typing import final
from urllib.parse import urlparse

import msgspec
import structlog
from litestar.enums import ScopeType
from litestar.types import ASGIApp, Receive, Scope, Send
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from zondarr.config import Settings
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.settings import CSRF_ORIGIN_KEY

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]

# HTTP methods that don't change state
SAFE_METHODS = frozenset({b"GET", b"HEAD", b"OPTIONS"})

# Paths excluded from CSRF checks (public/auth endpoints)
CSRF_EXCLUDE_PATHS = frozenset(
    {
        "/api/auth/setup",
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/logout",
        "/api/auth/methods",
        "/api/health",
        "/health",
        "/docs",
        "/swagger",
        "/scalar",
        "/schema",
    }
)

# Prefixes excluded from CSRF checks
CSRF_EXCLUDE_PREFIXES = ("/api/v1/join/",)

# Cache TTL for DB-sourced CSRF origin (seconds)
_CACHE_TTL = 60


@final
class _CsrfOriginCache:
    """Simple TTL cache for the CSRF origin from the database."""

    __slots__ = ("_fetched_at", "_value")

    def __init__(self) -> None:
        self._value: str | None = None
        self._fetched_at: float = 0.0

    def get(self) -> tuple[str | None, bool]:
        """Get cached value if still valid.

        Returns:
            (value, is_valid) — is_valid is False if cache is stale.
        """
        if time.monotonic() - self._fetched_at < _CACHE_TTL:
            return self._value, True
        return self._value, False

    def set(self, value: str | None) -> None:
        self._value = value
        self._fetched_at = time.monotonic()


@final
class CSRFMiddleware:
    """Raw ASGI middleware for origin-based CSRF protection.

    Runs before Litestar's auth middleware to reject forged requests early.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._cache = _CsrfOriginCache()
        self._warned_no_origin = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != ScopeType.HTTP:
            await self.app(scope, receive, send)
            return

        await self._handle_http(scope, receive, send)

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle CSRF validation for HTTP requests."""
        method = str(scope.get("method", "GET"))  # pyright: ignore[reportUnknownMemberType]
        if method.encode() in SAFE_METHODS:
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))  # pyright: ignore[reportUnknownMemberType]
        if self._is_excluded_path(path):
            await self.app(scope, receive, send)
            return

        # Resolve trusted origin
        trusted_origin = await self._get_trusted_origin(scope)
        if trusted_origin is None:
            if not self._warned_no_origin:
                logger.warning("No CSRF origin configured — all origins allowed")
                self._warned_no_origin = True
            await self.app(scope, receive, send)
            return

        # Extract request origin
        request_origin = self._extract_origin(scope)
        if request_origin is None:
            await self._send_403(send, "Missing Origin/Referer header")
            return

        # Compare (case-insensitive, strip trailing slashes)
        if request_origin.lower().rstrip("/") != trusted_origin.lower().rstrip("/"):
            logger.warning(
                "CSRF origin mismatch",
                request_origin=request_origin,
                trusted_origin=trusted_origin,
                path=path,
                method=method,
            )
            await self._send_403(send, "Origin not allowed")
            return

        await self.app(scope, receive, send)

    def _is_excluded_path(self, path: str) -> bool:
        """Check if the path is excluded from CSRF checks."""
        if path in CSRF_EXCLUDE_PATHS:
            return True
        return any(path.startswith(prefix) for prefix in CSRF_EXCLUDE_PREFIXES)

    async def _get_trusted_origin(self, scope: Scope) -> str | None:
        """Resolve the trusted CSRF origin from settings or DB."""
        app = scope.get("app")  # pyright: ignore[reportUnknownMemberType]
        if app is None:  # pyright: ignore[reportUnnecessaryComparison]
            return None

        # Check env var first (fast path)
        settings: Settings | None = getattr(app.state, "settings", None)
        if settings is not None and settings.csrf_origin:
            return settings.csrf_origin

        # Check DB with cache
        cached_value, is_valid = self._cache.get()
        if is_valid:
            return cached_value

        # Fetch from DB
        session_factory: async_sessionmaker[AsyncSession] | None = getattr(
            app.state, "session_factory", None
        )
        if session_factory is None:
            return None

        try:
            async with session_factory() as session:
                repo = AppSettingRepository(session)
                setting = await repo.get_by_key(CSRF_ORIGIN_KEY)
                value = setting.value if setting is not None else None
                self._cache.set(value)
                return value
        except Exception:
            logger.exception("Failed to fetch CSRF origin from database")
            return cached_value  # Fall back to stale cache

    def _extract_origin(self, scope: Scope) -> str | None:
        """Extract origin from Origin header, falling back to Referer."""
        headers = scope.get("headers", [])  # pyright: ignore[reportUnknownMemberType]

        origin: str | None = None
        referer: str | None = None

        for name, value in headers:
            lower_name = name.lower()
            if lower_name == b"origin":
                origin = value.decode("latin-1")
            elif lower_name == b"referer":
                referer = value.decode("latin-1")

        if origin and origin.lower() != "null":
            return origin

        if referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.hostname:
                host = parsed.hostname
                # Restore brackets for IPv6 addresses
                if ":" in host:
                    host = f"[{host}]"
                port_suffix = (
                    f":{parsed.port}"
                    if parsed.port and parsed.port not in (80, 443)
                    else ""
                )
                return f"{parsed.scheme}://{host}{port_suffix}"

        return None

    async def _send_403(self, send: Send, detail: str) -> None:
        """Send a 403 Forbidden JSON response."""
        from datetime import UTC, datetime

        body = msgspec.json.encode(
            {
                "detail": detail,
                "error_code": "CSRF_ORIGIN_MISMATCH",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send(
            {  # pyright: ignore[reportArgumentType]
                "type": "http.response.body",
                "body": body,
            }
        )
