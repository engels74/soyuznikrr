"""Authentication service for admin account management.

Orchestrates admin account creation, credential verification,
external auth (Plex/Jellyfin), and refresh token lifecycle.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import structlog

from zondarr.core.exceptions import AuthenticationError
from zondarr.models.admin import AdminAccount, AuthMethod, RefreshToken
from zondarr.repositories.admin import AdminAccountRepository, RefreshTokenRepository
from zondarr.services.password import hash_password, needs_rehash, verify_password

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]

# Refresh token defaults
REFRESH_TOKEN_EXPIRY_DAYS = 7
REFRESH_TOKEN_BYTES = 32


def _hash_token(token: str) -> str:
    """SHA-256 hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    """Service for authentication operations.

    Attributes:
        admin_repo: Repository for admin accounts.
        token_repo: Repository for refresh tokens.
    """

    admin_repo: AdminAccountRepository
    token_repo: RefreshTokenRepository

    def __init__(
        self,
        admin_repo: AdminAccountRepository,
        token_repo: RefreshTokenRepository,
    ) -> None:
        self.admin_repo = admin_repo
        self.token_repo = token_repo

    async def setup_required(self) -> bool:
        """Check if initial admin setup is needed.

        Returns:
            True if no admin accounts exist.
        """
        count = await self.admin_repo.count()
        return count == 0

    async def create_admin(
        self,
        username: str,
        password: str,
        *,
        email: str | None = None,
    ) -> AdminAccount:
        """Create a new local admin account.

        Args:
            username: Admin username.
            password: Plaintext password (will be hashed).
            email: Optional email address.

        Returns:
            The created AdminAccount.

        Raises:
            AuthenticationError: If username is already taken.
        """
        existing = await self.admin_repo.get_by_username(username)
        if existing is not None:
            raise AuthenticationError("Username already taken", "USERNAME_TAKEN")

        admin = AdminAccount(
            username=username,
            password_hash=hash_password(password),
            email=email,
            auth_method=AuthMethod.LOCAL,
            enabled=True,
        )
        return await self.admin_repo.create(admin)

    async def authenticate_local(self, username: str, password: str) -> AdminAccount:
        """Authenticate with username and password.

        Args:
            username: Admin username.
            password: Plaintext password.

        Returns:
            The authenticated AdminAccount.

        Raises:
            AuthenticationError: If credentials are invalid or account is disabled.
        """
        admin = await self.admin_repo.get_by_username(username)
        if admin is None or admin.password_hash is None:
            raise AuthenticationError("Invalid credentials", "INVALID_CREDENTIALS")

        if not admin.enabled:
            raise AuthenticationError("Account is disabled", "ACCOUNT_DISABLED")

        if not verify_password(admin.password_hash, password):
            raise AuthenticationError("Invalid credentials", "INVALID_CREDENTIALS")

        # Rehash if needed (updated Argon2 parameters)
        if needs_rehash(admin.password_hash):
            admin.password_hash = hash_password(password)

        admin.last_login_at = datetime.now(UTC)
        return admin

    async def authenticate_plex(
        self,
        auth_token: str,
        *,
        configured_plex_token: str | None = None,
    ) -> AdminAccount:
        """Authenticate via Plex OAuth token.

        Verifies the token is valid and the account matches the configured
        Plex server owner. Auto-creates an AdminAccount for verified owners.

        Args:
            auth_token: Plex auth token from OAuth flow.
            configured_plex_token: The configured Plex server token (PLEX_TOKEN).
                Required to verify server ownership.

        Returns:
            The authenticated AdminAccount.

        Raises:
            AuthenticationError: If Plex is not configured, verification fails,
                or the account is not the server owner.
        """
        from plexapi.myplex import MyPlexAccount

        if not configured_plex_token:
            raise AuthenticationError(
                "Plex authentication is not configured", "PLEX_NOT_CONFIGURED"
            )

        try:
            account = MyPlexAccount(token=auth_token)
            _raw_email: object = account.email  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            _raw_username: object = account.username  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            plex_email = str(_raw_email)  # pyright: ignore[reportUnknownArgumentType]
            plex_username = str(_raw_username) if _raw_username else plex_email  # pyright: ignore[reportUnknownArgumentType]
        except Exception as exc:
            raise AuthenticationError(
                "Failed to verify Plex account", "PLEX_AUTH_FAILED"
            ) from exc

        # Verify the authenticating user is the configured Plex server owner
        try:
            owner_account = MyPlexAccount(token=configured_plex_token)
            _raw_owner_email: object = owner_account.email  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            owner_email = str(_raw_owner_email)  # pyright: ignore[reportUnknownArgumentType]
        except Exception as exc:
            raise AuthenticationError(
                "Failed to verify Plex server owner", "PLEX_AUTH_FAILED"
            ) from exc

        if plex_email.lower() != owner_email.lower():
            raise AuthenticationError(
                "Account is not the Plex server owner", "NOT_SERVER_OWNER"
            )

        # Check for existing account with this external ID
        admin = await self.admin_repo.get_by_external_id(plex_email, AuthMethod.PLEX)

        if admin is not None:
            if not admin.enabled:
                raise AuthenticationError("Account is disabled", "ACCOUNT_DISABLED")
            admin.last_login_at = datetime.now(UTC)
            return admin

        # Auto-create admin account for verified Plex server owner
        admin = AdminAccount(
            username=plex_username.lower().replace(" ", "_")[:32],
            email=plex_email,
            auth_method=AuthMethod.PLEX,
            external_id=plex_email,
            enabled=True,
            last_login_at=datetime.now(UTC),
        )
        return await self.admin_repo.create(admin)

    async def authenticate_jellyfin(
        self,
        server_url: str,
        username: str,
        password: str,
    ) -> AdminAccount:
        """Authenticate via Jellyfin credentials.

        Verifies the user is a Jellyfin administrator.
        Auto-creates an AdminAccount if verified admin.

        Args:
            server_url: Jellyfin server URL.
            username: Jellyfin username.
            password: Jellyfin password.

        Returns:
            The authenticated AdminAccount.

        Raises:
            AuthenticationError: If verification fails.
        """
        import httpx

        # Authenticate with Jellyfin server
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{server_url.rstrip('/')}/Users/AuthenticateByName",
                    json={"Username": username, "Pw": password},
                    headers={
                        "X-Emby-Authorization": (
                            'MediaBrowser Client="Zondarr", '
                            'Device="Server", '
                            'DeviceId="zondarr-auth", '
                            'Version="1.0"'
                        ),
                    },
                    timeout=10.0,
                )
                if response.status_code != 200:
                    raise AuthenticationError(
                        "Invalid Jellyfin credentials",
                        "INVALID_CREDENTIALS",
                    )

                data = response.json()  # pyright: ignore[reportAny]
                user_data: dict[str, object] = data.get("User", {})  # pyright: ignore[reportAny]
                policy: dict[str, object] = user_data.get("Policy", {})  # pyright: ignore[reportAssignmentType]
                is_admin: bool = policy.get("IsAdministrator", False)  # pyright: ignore[reportAssignmentType]
                jellyfin_user_id: str = str(user_data.get("Id", ""))

        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError(
                "Failed to connect to Jellyfin server",
                "JELLYFIN_AUTH_FAILED",
            ) from exc

        if not is_admin:
            raise AuthenticationError(
                "User is not a Jellyfin administrator",
                "NOT_ADMIN",
            )

        # Check for existing account with this external ID
        admin = await self.admin_repo.get_by_external_id(
            jellyfin_user_id, AuthMethod.JELLYFIN
        )

        if admin is not None:
            if not admin.enabled:
                raise AuthenticationError("Account is disabled", "ACCOUNT_DISABLED")
            admin.last_login_at = datetime.now(UTC)
            return admin

        # Auto-create admin account for Jellyfin admin
        admin = AdminAccount(
            username=username.lower().replace(" ", "_")[:32],
            auth_method=AuthMethod.JELLYFIN,
            external_id=jellyfin_user_id,
            enabled=True,
            last_login_at=datetime.now(UTC),
        )
        return await self.admin_repo.create(admin)

    async def create_refresh_token(
        self,
        admin: AdminAccount,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> str:
        """Create a new refresh token for an admin.

        Args:
            admin: The admin account.
            user_agent: Client user-agent for audit.
            ip_address: Client IP for audit.

        Returns:
            The raw refresh token string (only returned once).
        """
        raw_token = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
        token_hash = _hash_token(raw_token)

        refresh_token = RefreshToken(
            admin_account_id=admin.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        _ = await self.token_repo.create(refresh_token)

        return raw_token

    async def validate_refresh_token(self, raw_token: str) -> AdminAccount:
        """Validate a refresh token and return the associated admin.

        Args:
            raw_token: The raw refresh token string.

        Returns:
            The associated AdminAccount.

        Raises:
            AuthenticationError: If the token is invalid, expired, or revoked.
        """
        token_hash = _hash_token(raw_token)
        refresh_token = await self.token_repo.get_by_token_hash(token_hash)

        if refresh_token is None:
            raise AuthenticationError("Invalid refresh token", "INVALID_TOKEN")

        if refresh_token.revoked:
            raise AuthenticationError("Token has been revoked", "TOKEN_REVOKED")

        if refresh_token.expires_at < datetime.now(UTC):
            raise AuthenticationError("Token has expired", "TOKEN_EXPIRED")

        admin = await self.admin_repo.get_by_id(refresh_token.admin_account_id)
        if admin is None or not admin.enabled:
            raise AuthenticationError(
                "Account not found or disabled", "ACCOUNT_DISABLED"
            )

        return admin

    async def revoke_refresh_token(self, raw_token: str) -> None:
        """Revoke a specific refresh token.

        Args:
            raw_token: The raw refresh token string.
        """
        token_hash = _hash_token(raw_token)
        refresh_token = await self.token_repo.get_by_token_hash(token_hash)
        if refresh_token is not None:
            refresh_token.revoked = True

    async def revoke_all_tokens(self, admin: AdminAccount) -> None:
        """Revoke all refresh tokens for an admin.

        Args:
            admin: The admin account.
        """
        _ = await self.token_repo.revoke_all_for_admin(admin.id)

    async def get_available_auth_methods(self) -> list[str]:
        """Get available authentication methods.

        Always includes 'local'. Adds 'plex'/'jellyfin' if servers
        are configured (env vars or DB records).

        Returns:
            List of available auth method strings.
        """
        methods: list[str] = ["local"]

        # Check for Plex/Jellyfin config via env vars
        # (Media server DB records would need a separate query,
        # but env vars are the primary config mechanism)
        import os

        if os.environ.get("PLEX_URL") or os.environ.get("PLEX_TOKEN"):
            methods.append("plex")

        if os.environ.get("JELLYFIN_URL") or os.environ.get("JELLYFIN_API_KEY"):
            methods.append("jellyfin")

        return methods
