"""Authentication service for admin account management.

Orchestrates admin account creation, credential verification,
external auth (via provider registry), and refresh token lifecycle.
"""

import asyncio
import hashlib
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog

from zondarr.core.exceptions import AuthenticationError
from zondarr.media.registry import registry
from zondarr.models.admin import AdminAccount, RefreshToken
from zondarr.repositories.admin import AdminAccountRepository, RefreshTokenRepository
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.onboarding import OnboardingService, OnboardingStep
from zondarr.services.password import hash_password, needs_rehash, verify_password

if TYPE_CHECKING:
    from zondarr.config import Settings
    from zondarr.media.provider import AdminAuthDescriptor

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]

# Refresh token defaults
REFRESH_TOKEN_EXPIRY_DAYS = 7
REFRESH_TOKEN_BYTES = 32

# Serializes concurrent setup attempts within a single process
_setup_lock = asyncio.Lock()


def _hash_token(token: str) -> str:
    """SHA-256 hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    """Service for authentication operations.

    Attributes:
        admin_repo: Repository for admin accounts.
        token_repo: Repository for refresh tokens.
        app_setting_repo: Repository for app-level key/value settings.
    """

    admin_repo: AdminAccountRepository
    token_repo: RefreshTokenRepository
    app_setting_repo: AppSettingRepository
    onboarding_service: OnboardingService

    def __init__(
        self,
        admin_repo: AdminAccountRepository,
        token_repo: RefreshTokenRepository,
        app_setting_repo: AppSettingRepository,
    ) -> None:
        self.admin_repo = admin_repo
        self.token_repo = token_repo
        self.app_setting_repo = app_setting_repo
        self.onboarding_service = OnboardingService(admin_repo, app_setting_repo)

    async def setup_required(self) -> bool:
        """Check if initial admin setup is needed.

        Returns:
            True if no admin accounts exist.
        """
        count = await self.admin_repo.count()
        return count == 0

    async def get_onboarding_status(self) -> tuple[bool, OnboardingStep]:
        """Get onboarding requirement and current step."""
        return await self.onboarding_service.get_status()

    async def get_setup_and_onboarding_status(
        self,
    ) -> tuple[bool, bool, OnboardingStep]:
        """Get setup and onboarding status in one call.

        Returns:
            A tuple of (setup_required, onboarding_required, onboarding_step).
        """
        onboarding_required, onboarding_step = await self.get_onboarding_status()
        return onboarding_step == "account", onboarding_required, onboarding_step

    async def initialize_onboarding(self) -> None:
        """Initialize onboarding state right after first admin setup."""
        await self.onboarding_service.initialize_after_admin_setup()

    async def advance_onboarding(self) -> tuple[bool, OnboardingStep]:
        """Advance onboarding by one skip step and return updated status."""
        onboarding_step = await self.onboarding_service.advance_skip_step()
        return onboarding_step != "complete", onboarding_step

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
            auth_method="local",
            enabled=True,
        )
        return await self.admin_repo.create(admin)

    async def setup_admin(
        self,
        username: str,
        password: str,
        *,
        email: str | None = None,
    ) -> AdminAccount:
        """Atomically create the first admin account.

        Defence layers:
        1. asyncio.Lock serializes attempts within a single worker process
           (avoids wasted Argon2 hashing).
        2. INSERT ... WHERE NOT EXISTS prevents the insert when an admin
           already exists (single-statement check-and-insert).
        3. UNIQUE(username) + IntegrityError handling in the repository
           catches PostgreSQL races under READ COMMITTED isolation across
           multiple workers.

        Args:
            username: Admin username.
            password: Plaintext password (will be hashed).
            email: Optional email address.

        Returns:
            The created AdminAccount.

        Raises:
            AuthenticationError: If an admin already exists.
        """
        async with _setup_lock:
            pw_hash = hash_password(password)
            admin = await self.admin_repo.create_first_admin(
                username=username,
                password_hash=pw_hash,
                email=email,
                auth_method="local",
            )
            if admin is None:
                raise AuthenticationError(
                    "Setup already completed", "SETUP_NOT_REQUIRED"
                )
            logger.info(
                "admin_setup_completed",
                admin_id=str(admin.id),
                username=admin.username,
            )
            return admin

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

    async def authenticate_external(
        self,
        method: str,
        credentials: Mapping[str, str],
        *,
        settings: Settings,
    ) -> AdminAccount:
        """Authenticate via an external provider.

        Delegates to the registered AdminAuthProvider for the given method.

        Args:
            method: The auth method name (e.g., "plex", "jellyfin").
            credentials: Provider-specific credential dict.
            settings: Application settings.

        Returns:
            The authenticated or auto-created AdminAccount.

        Raises:
            AuthenticationError: If the method is unknown or authentication fails.
        """
        provider = registry.get_admin_auth_provider(method)
        if provider is None:
            raise AuthenticationError(
                f"Unknown authentication method: {method}",
                "UNKNOWN_AUTH_METHOD",
            )

        if not provider.is_configured(settings):
            raise AuthenticationError(
                f"Authentication method not configured: {method}",
                "AUTH_METHOD_NOT_CONFIGURED",
            )

        return await provider.authenticate(
            credentials,
            settings=settings,
            admin_repo=self.admin_repo,
        )

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

    async def get_available_auth_methods(
        self,
        *,
        settings: Settings,
    ) -> list[str]:
        """Get available authentication methods.

        Always includes 'local'. Adds external methods for each configured
        provider that supports admin auth.

        Args:
            settings: Application settings for checking provider configuration.

        Returns:
            List of available auth method strings.
        """
        methods: list[str] = ["local"]

        for desc in registry.get_admin_auth_descriptors():
            provider = registry.get_admin_auth_provider(desc.method_name)
            if provider is not None and provider.is_configured(settings):
                methods.append(desc.method_name)

        return methods

    async def get_auth_methods_with_providers(
        self,
        *,
        settings: Settings,
    ) -> tuple[list[str], list[AdminAuthDescriptor]]:
        """Get available auth methods and their provider descriptors.

        Combines method availability checking with descriptor filtering
        so the controller doesn't need to re-query the registry.

        Args:
            settings: Application settings for checking provider configuration.

        Returns:
            A tuple of (method names, filtered admin auth descriptors).
        """
        methods = await self.get_available_auth_methods(settings=settings)
        descriptors = [
            desc
            for desc in registry.get_admin_auth_descriptors()
            if desc.method_name in methods
        ]
        return methods, descriptors
