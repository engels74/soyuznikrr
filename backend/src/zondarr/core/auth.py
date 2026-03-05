"""JWT cookie authentication infrastructure.

Provides:
- AdminUser: Lightweight struct stored in request.user after JWT validation
- retrieve_user_handler: Verifies admin exists and is enabled
- create_jwt_auth: Factory for configured JWTCookieAuth instance
"""

from typing import Any, override
from uuid import UUID

import msgspec
import structlog
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.middleware.authentication import (
    AbstractAuthenticationMiddleware,
    AuthenticationResult,
)
from litestar.security.jwt import JWTCookieAuth, Token
from litestar.security.jwt.middleware import JWTCookieAuthenticationMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from zondarr.config import Settings
from zondarr.repositories.admin import AdminAccountRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]

# Paths excluded from JWT auth (always excluded)
# Note: /api/auth/me requires auth, so we list specific public sub-paths
# rather than excluding the entire /api/auth/ prefix.
_AUTH_EXCLUDE_PATHS_BASE = [
    "/api/auth/methods",
    "/api/auth/setup",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/auth/totp/verify",
    "/api/auth/totp/backup-code",
    "/api/v1/join/",
    "/api/health",
    "/health",
]

# Doc paths — only excluded in debug mode
_AUTH_EXCLUDE_PATHS_DOCS = [
    "/docs",
    "/swagger",
    "/scalar",
    "/schema",
]


class AdminUser(msgspec.Struct):
    """Lightweight admin user data stored in request.user after JWT validation.

    Attributes:
        id: Admin account UUID.
        username: Admin username.
        email: Optional admin email.
        auth_method: How this admin authenticated.
    """

    id: UUID
    username: str
    email: str | None = None
    auth_method: str = "local"


DEV_ADMIN = AdminUser(
    id=UUID("00000000-0000-0000-0000-000000000000"),
    username="dev-admin",
    auth_method="dev-skip",
)


class DevSkipAuthMiddleware(AbstractAuthenticationMiddleware):
    """Dev-only middleware that bypasses auth and injects a mock admin user."""

    @override
    async def authenticate_request(
        self,
        connection: ASGIConnection[Any, Any, Any, Any],  # pyright: ignore[reportExplicitAny]
    ) -> AuthenticationResult:
        return AuthenticationResult(user=DEV_ADMIN, auth=None)


async def retrieve_user_handler(
    token: Token,
    connection: ASGIConnection[Any, Any, Any, Any],  # pyright: ignore[reportExplicitAny]
) -> AdminUser | None:
    """Retrieve and verify admin user from JWT token.

    Called by JWTCookieAuth on every authenticated request.
    Queries the database to verify the admin still exists and is enabled.

    Args:
        token: The decoded JWT token.
        connection: The ASGI connection.

    Returns:
        AdminUser if valid, None if the admin doesn't exist or is disabled.
    """
    # Reject challenge tokens — they must not be accepted as access tokens
    if token.extras.get("purpose") == "totp_challenge":
        return None

    try:
        admin_id = UUID(token.sub)
    except ValueError, TypeError:
        return None

    try:
        session_factory: async_sessionmaker[AsyncSession] = (  # pyright: ignore[reportAny]
            connection.app.state.session_factory
        )
        async with session_factory() as session:
            repo = AdminAccountRepository(session)
            admin = await repo.get_by_id(admin_id)

            if admin is None or not admin.enabled:
                return None

            return AdminUser(
                id=admin.id,
                username=admin.username,
                email=admin.email,
                auth_method=admin.auth_method,
            )
    except Exception:
        logger.exception("Failed to retrieve admin user from token")
        return None


class FixedJWTCookieMiddleware(JWTCookieAuthenticationMiddleware):
    """Fixed JWT cookie middleware that correctly parses cookie tokens.

    Litestar's default JWTCookieAuthenticationMiddleware uses
    ``auth_header.partition(" ")[-1]`` to strip the "Bearer " prefix,
    but cookie values don't have that prefix — ``partition`` returns
    ``(token, "", "")`` and ``[-1]`` yields an empty string.

    This subclass handles both cases correctly.
    """

    @override
    async def authenticate_request(
        self,
        connection: ASGIConnection[Any, Any, Any, Any],  # pyright: ignore[reportExplicitAny]
    ) -> AuthenticationResult:
        """Extract JWT from header or cookie and authenticate."""
        auth_header = connection.headers.get(self.auth_header)
        encoded_token: str | None = None

        if auth_header:
            # Authorization header: strip "Bearer " prefix
            encoded_token = auth_header.partition(" ")[-1] or auth_header
        else:
            # Cookie: value is the raw JWT, no prefix
            encoded_token = connection.cookies.get(self.auth_cookie_key)

        if not encoded_token:
            raise NotAuthorizedException(
                "No JWT token found in request header or cookies"
            )
        return await self.authenticate_token(
            encoded_token=encoded_token, connection=connection
        )


def create_jwt_auth(settings: Settings) -> JWTCookieAuth[AdminUser]:
    """Create a configured JWTCookieAuth instance.

    Uses FixedJWTCookieMiddleware to work around a Litestar bug where
    cookie token values are not parsed correctly.

    Doc paths (/docs, /swagger, /scalar, /schema) are only excluded from
    auth when debug mode is enabled.

    Args:
        settings: Application settings containing secret_key.

    Returns:
        Configured JWTCookieAuth instance.
    """
    exclude = list(_AUTH_EXCLUDE_PATHS_BASE)
    if settings.debug:
        exclude.extend(_AUTH_EXCLUDE_PATHS_DOCS)

    return JWTCookieAuth[AdminUser](
        retrieve_user_handler=retrieve_user_handler,
        token_secret=settings.secret_key,
        key="zondarr_access_token",
        exclude=exclude,
        authentication_middleware_class=FixedJWTCookieMiddleware,
    )
