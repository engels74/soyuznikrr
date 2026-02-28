"""TOTP two-factor authentication API controller.

Provides endpoints for TOTP verification during login:
- POST /api/auth/totp/verify — Verify TOTP code with challenge token
- POST /api/auth/totp/backup-code — Verify backup code with challenge token

Provides authenticated endpoints for TOTP management:
- POST /api/auth/totp/setup — Initiate TOTP setup
- POST /api/auth/totp/confirm-setup — Confirm TOTP setup with code
- POST /api/auth/totp/disable — Disable TOTP (requires password)
- POST /api/auth/totp/regenerate-backup-codes — Regenerate backup codes
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from litestar import Controller, Request, Response, post
from litestar.datastructures import Cookie, State
from litestar.security.jwt import Token
from litestar.status_codes import HTTP_200_OK
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.config import Settings
from zondarr.core.auth import AdminUser
from zondarr.core.exceptions import AuthenticationError
from zondarr.models.admin import AdminAccount
from zondarr.repositories.admin import AdminAccountRepository, RefreshTokenRepository
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.auth import AuthService
from zondarr.services.password import verify_password
from zondarr.services.totp import TOTPService

from .schemas import (
    AuthTokenResponse,
    TOTPBackupCodeRequest,
    TOTPBackupCodesResponse,
    TOTPConfirmSetupRequest,
    TOTPConfirmSetupResponse,
    TOTPDisableRequest,
    TOTPRegenerateBackupCodesRequest,
    TOTPSetupResponse,
    TOTPVerifyRequest,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]

# Challenge token lifetime
CHALLENGE_TOKEN_MINUTES = 5


def create_challenge_token(admin_id: str, secret_key: str) -> str:
    """Create a short-lived JWT challenge token for TOTP verification.

    Args:
        admin_id: The admin account UUID as a string.
        secret_key: Application secret key for signing.

    Returns:
        Encoded JWT string with purpose="totp_challenge".
    """
    token = Token(
        sub=admin_id,
        exp=datetime.now(UTC) + timedelta(minutes=CHALLENGE_TOKEN_MINUTES),
        iss="zondarr",
        extras={"purpose": "totp_challenge"},
    )
    return token.encode(secret=secret_key, algorithm="HS256")


def validate_challenge_token(encoded_token: str, secret_key: str) -> UUID:
    """Validate a TOTP challenge token and return the admin ID.

    Args:
        encoded_token: The encoded JWT challenge token.
        secret_key: Application secret key for verification.

    Returns:
        The admin account UUID.

    Raises:
        AuthenticationError: If the token is invalid, expired, or not a challenge token.
    """
    try:
        token = Token.decode(
            encoded_token=encoded_token,
            secret=secret_key,
            algorithm="HS256",
        )
    except Exception:
        raise AuthenticationError(
            "Invalid challenge token", "INVALID_CHALLENGE_TOKEN"
        ) from None

    # Verify purpose claim
    if token.extras.get("purpose") != "totp_challenge":
        raise AuthenticationError(
            "Invalid challenge token purpose", "INVALID_CHALLENGE_TOKEN"
        )

    # Check expiration
    if token.exp and token.exp < datetime.now(UTC):
        raise AuthenticationError(
            "Challenge token has expired", "CHALLENGE_TOKEN_EXPIRED"
        )

    try:
        return UUID(token.sub)
    except ValueError, TypeError:
        raise AuthenticationError(
            "Invalid challenge token subject", "INVALID_CHALLENGE_TOKEN"
        ) from None


# Access token lifetime (matches AuthController)
ACCESS_TOKEN_MINUTES = 15


class TOTPController(Controller):
    """Controller for TOTP verification endpoints during login."""

    path: str = "/api/auth/totp"
    tags: Sequence[str] | None = ["Authentication"]

    def _create_auth_service(self, session: AsyncSession) -> AuthService:
        return AuthService(
            admin_repo=AdminAccountRepository(session),
            token_repo=RefreshTokenRepository(session),
            app_setting_repo=AppSettingRepository(session),
        )

    async def _resolve_secure_cookies(
        self, session: AsyncSession, settings: Settings
    ) -> bool:
        """Resolve the effective secure_cookies value."""
        import os

        from zondarr.repositories.app_setting import AppSettingRepository
        from zondarr.services.settings import SettingsService

        if os.environ.get("SECURE_COOKIES") is not None:
            return settings.secure_cookies
        service = SettingsService(AppSettingRepository(session))
        value, _ = await service.get_secure_cookies()
        return value

    def _create_access_token(
        self, admin_id: str, secret_key: str, *, secure: bool = False
    ) -> tuple[str, Cookie]:
        """Create JWT access token and cookie."""
        token = Token(
            sub=admin_id,
            exp=datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_MINUTES),
            iss="zondarr",
        )
        encoded = token.encode(secret=secret_key, algorithm="HS256")
        cookie = Cookie(
            key="zondarr_access_token",
            value=encoded,
            httponly=True,
            secure=secure,
            samesite="lax",
            max_age=ACCESS_TOKEN_MINUTES * 60,
            path="/",
        )
        return encoded, cookie

    @post(
        "/verify",
        status_code=HTTP_200_OK,
        summary="Verify TOTP code during login",
        exclude_from_auth=True,
    )
    async def verify_totp(
        self,
        data: TOTPVerifyRequest,
        session: AsyncSession,
        settings: Settings,
    ) -> Response[AuthTokenResponse]:
        """Verify a TOTP code using the challenge token from login."""
        secret_key = settings.secret_key

        # Validate challenge token
        admin_id = validate_challenge_token(data.challenge_token, secret_key)

        # Load admin
        admin_repo = AdminAccountRepository(session)
        admin = await admin_repo.get_by_id(admin_id)
        if admin is None or not admin.enabled:
            raise AuthenticationError(
                "Account not found or disabled", "ACCOUNT_DISABLED"
            )

        # Check rate limit
        totp_service = TOTPService(secret_key=secret_key)
        totp_service.check_rate_limit(admin)

        # Verify TOTP code
        if not totp_service.verify_code(admin, data.code):
            totp_service.record_failed_attempt(admin)
            await session.commit()
            raise AuthenticationError("Invalid TOTP code", "INVALID_TOTP_CODE")

        # Success — reset failed attempts and issue tokens
        totp_service.reset_failed_attempts(admin)
        admin.last_login_at = datetime.now(UTC)

        auth_service = self._create_auth_service(session)
        secure = await self._resolve_secure_cookies(session, settings)
        _, access_cookie = self._create_access_token(
            str(admin.id), secret_key, secure=secure
        )
        refresh_token = await auth_service.create_refresh_token(admin)

        return Response(
            AuthTokenResponse(refresh_token=refresh_token),
            status_code=HTTP_200_OK,
            cookies=[access_cookie],
        )

    @post(
        "/backup-code",
        status_code=HTTP_200_OK,
        summary="Verify backup code during login",
        exclude_from_auth=True,
    )
    async def verify_backup_code(
        self,
        data: TOTPBackupCodeRequest,
        session: AsyncSession,
        settings: Settings,
    ) -> Response[AuthTokenResponse]:
        """Verify a backup code using the challenge token from login."""
        secret_key = settings.secret_key

        # Validate challenge token
        admin_id = validate_challenge_token(data.challenge_token, secret_key)

        # Load admin
        admin_repo = AdminAccountRepository(session)
        admin = await admin_repo.get_by_id(admin_id)
        if admin is None or not admin.enabled:
            raise AuthenticationError(
                "Account not found or disabled", "ACCOUNT_DISABLED"
            )

        # Check rate limit
        totp_service = TOTPService(secret_key=secret_key)
        totp_service.check_rate_limit(admin)

        # Verify backup code
        if not totp_service.verify_backup_code(admin, data.code):
            totp_service.record_failed_attempt(admin)
            await session.commit()
            raise AuthenticationError("Invalid backup code", "INVALID_BACKUP_CODE")

        # Success — reset failed attempts and issue tokens
        totp_service.reset_failed_attempts(admin)
        admin.last_login_at = datetime.now(UTC)

        auth_service = self._create_auth_service(session)
        secure = await self._resolve_secure_cookies(session, settings)
        _, access_cookie = self._create_access_token(
            str(admin.id), secret_key, secure=secure
        )
        refresh_token = await auth_service.create_refresh_token(admin)

        return Response(
            AuthTokenResponse(refresh_token=refresh_token),
            status_code=HTTP_200_OK,
            cookies=[access_cookie],
        )

    # =========================================================================
    # Authenticated TOTP management endpoints
    # =========================================================================

    async def _get_admin_account(
        self, request: Request[AdminUser, Token, State], session: AsyncSession
    ) -> AdminAccount:
        """Load the full AdminAccount for the authenticated user."""
        user: AdminUser = request.user
        admin_repo = AdminAccountRepository(session)
        admin = await admin_repo.get_by_id(user.id)
        if admin is None or not admin.enabled:
            raise AuthenticationError(
                "Account not found or disabled", "ACCOUNT_DISABLED"
            )
        return admin

    @post(
        "/setup",
        status_code=HTTP_200_OK,
        summary="Initiate TOTP setup",
    )
    async def setup_totp(
        self,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
        settings: Settings,
    ) -> TOTPSetupResponse:
        """Generate TOTP secret, provisioning URI, QR code, and backup codes."""
        admin = await self._get_admin_account(request, session)
        totp_service = TOTPService(secret_key=settings.secret_key)
        uri, qr_svg, backup_codes = totp_service.generate_setup(admin)

        return TOTPSetupResponse(
            provisioning_uri=uri,
            qr_code_svg=qr_svg,
            backup_codes=backup_codes,
        )

    @post(
        "/confirm-setup",
        status_code=HTTP_200_OK,
        summary="Confirm TOTP setup with authenticator code",
    )
    async def confirm_totp_setup(
        self,
        data: TOTPConfirmSetupRequest,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
        settings: Settings,
    ) -> TOTPConfirmSetupResponse:
        """Verify a TOTP code to confirm setup and enable 2FA."""
        admin = await self._get_admin_account(request, session)
        totp_service = TOTPService(secret_key=settings.secret_key)

        if not totp_service.confirm_setup(admin, data.code):
            raise AuthenticationError("Invalid TOTP code", "INVALID_TOTP_CODE")

        # Backup codes were generated during setup and are already stored.
        # Regenerate fresh ones so the user can see the plaintext codes.
        backup_codes = totp_service.regenerate_backup_codes(admin)

        return TOTPConfirmSetupResponse(backup_codes=backup_codes)

    @post(
        "/disable",
        status_code=HTTP_200_OK,
        summary="Disable TOTP two-factor authentication",
    )
    async def disable_totp(
        self,
        data: TOTPDisableRequest,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
        settings: Settings,
    ) -> dict[str, bool]:
        """Disable TOTP after verifying the admin's password."""
        admin = await self._get_admin_account(request, session)

        # Verify password
        if admin.password_hash is None or not verify_password(
            admin.password_hash, data.password
        ):
            raise AuthenticationError("Invalid password", "INVALID_PASSWORD")

        # Verify TOTP code
        totp_service = TOTPService(secret_key=settings.secret_key)
        if not totp_service.verify_code(admin, data.code):
            raise AuthenticationError("Invalid TOTP code", "INVALID_TOTP_CODE")

        totp_service.disable(admin)

        return {"success": True}

    @post(
        "/regenerate-backup-codes",
        status_code=HTTP_200_OK,
        summary="Regenerate TOTP backup codes",
    )
    async def regenerate_backup_codes(
        self,
        data: TOTPRegenerateBackupCodesRequest,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
        settings: Settings,
    ) -> TOTPBackupCodesResponse:
        """Generate new backup codes after verifying a TOTP code."""
        admin = await self._get_admin_account(request, session)
        totp_service = TOTPService(secret_key=settings.secret_key)

        # Verify the TOTP code first
        if not totp_service.verify_code(admin, data.code):
            raise AuthenticationError("Invalid TOTP code", "INVALID_TOTP_CODE")

        codes = totp_service.regenerate_backup_codes(admin)
        return TOTPBackupCodesResponse(backup_codes=codes)
