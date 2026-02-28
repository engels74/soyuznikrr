"""Origin-based CSRF protection middleware.

Validates the Origin (or Referer) header on state-changing requests against
a configured trusted origin. Simpler than token-based CSRF for a Docker-
distributed app behind reverse proxies.

The middleware checks:
1. Settings.csrf_origin (env var — fast, no DB hit)
2. Database app_settings table with a 60-second TTL cache
3. If no origin configured: allows in debug mode, rejects in production
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

# Paths excluded from CSRF checks (public/auth endpoints — always excluded)
#
# TOTP endpoints (/api/auth/totp/setup, /api/auth/totp/confirm-setup):
# These are authenticated (JWT cookie) and state-mutating, but safe to exclude:
# - TOTP setup runs during onboarding step 2, before CSRF origin is configured
#   (step 3), so excluding them is required for the onboarding flow to work.
# - /setup returns the TOTP secret/QR code, but an attacker cannot read the
#   response cross-origin (blocked by same-origin policy, no CORS configured).
# - /confirm-setup requires a valid 6-digit TOTP code derived from the secret,
#   which the attacker cannot obtain without reading the /setup response.
_CSRF_EXCLUDE_PATHS_BASE = frozenset(
    {
        "/api/auth/setup",
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/logout",
        "/api/auth/methods",
        "/api/auth/onboarding/advance",
        "/api/auth/totp/setup",
        "/api/auth/totp/confirm-setup",
        "/api/health",
        "/health",
        "/api/v1/settings/csrf-origin",
        "/api/v1/settings/csrf-origin/test",
    }
)

# Doc paths — only excluded in debug mode
_CSRF_EXCLUDE_PATHS_DOCS = frozenset(
    {
        "/docs",
        "/swagger",
        "/scalar",
        "/schema",
    }
)

# Prefixes excluded from CSRF checks
CSRF_EXCLUDE_PREFIXES = ("/api/v1/join/", "/api/auth/login/")

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

        # Extract settings early (reused for path exclusion and deny-by-default)
        app = scope.get("app")  # pyright: ignore[reportUnknownMemberType]
        settings: Settings | None = (
            getattr(app.state, "settings", None) if app is not None else None  # pyright: ignore[reportUnnecessaryComparison]
        )
        is_debug = settings.debug if settings is not None else False

        path = str(scope.get("path", ""))  # pyright: ignore[reportUnknownMemberType]
        if self._is_excluded_path(path, debug=is_debug):
            await self.app(scope, receive, send)
            return

        # Server-side requests (SvelteKit API proxy, curl) don't send
        # Origin/Referer. Browsers ALWAYS send Origin on mutating requests,
        # so missing headers means this isn't a CSRF attack — allow through.
        headers = list(scope.get("headers", []))  # pyright: ignore[reportUnknownMemberType]
        has_origin_or_referer = any(
            name.lower() in (b"origin", b"referer") for name, _ in headers
        )
        if not has_origin_or_referer:
            await self.app(scope, receive, send)
            return

        # Browser request (has Origin/Referer) — resolve trusted origin
        trusted_origin = await self._get_trusted_origin(scope)
        if trusted_origin is None:
            if is_debug:
                # Dev mode: warn and allow through (preserves existing dev behavior)
                if not self._warned_no_origin:
                    logger.warning(
                        "No CSRF origin configured — all origins allowed (debug mode)"
                    )
                    self._warned_no_origin = True
                await self.app(scope, receive, send)
                return
            # Production: deny by default
            if not self._warned_no_origin:
                logger.error(
                    "No CSRF origin configured — rejecting all mutating requests (set CSRF_ORIGIN or configure via UI)"
                )
                self._warned_no_origin = True
            await self._send_403(
                send, "CSRF origin not configured", error_code="CSRF_NOT_CONFIGURED"
            )
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

    def _is_excluded_path(self, path: str, *, debug: bool = False) -> bool:
        """Check if the path is excluded from CSRF checks."""
        if path in _CSRF_EXCLUDE_PATHS_BASE:
            return True
        if debug and path in _CSRF_EXCLUDE_PATHS_DOCS:
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
                default_ports = {"http": 80, "https": 443}
                port_suffix = (
                    f":{parsed.port}"
                    if parsed.port and parsed.port != default_ports.get(parsed.scheme)
                    else ""
                )
                return f"{parsed.scheme}://{host}{port_suffix}"

        return None

    async def _send_403(
        self, send: Send, detail: str, *, error_code: str = "CSRF_ORIGIN_MISMATCH"
    ) -> None:
        """Send a 403 Forbidden JSON response."""
        from datetime import UTC, datetime

        body = msgspec.json.encode(
            {
                "detail": detail,
                "error_code": error_code,
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
