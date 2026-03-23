"""Authentication API controller.

Provides endpoints for admin authentication:
- GET /api/auth/methods — Available auth methods + setup_required flag
- POST /api/auth/setup — Create first admin account
- POST /api/auth/login — Local username/password login
- POST /api/auth/login/{method} — External provider login
- POST /api/auth/refresh — Exchange refresh token for new access token
- POST /api/auth/logout — Revoke tokens and clear cookies
- GET /api/auth/me — Current admin info (requires auth)
"""

import hmac
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from litestar import Controller, Request, Response, get, patch, post
from litestar.datastructures import Cookie, State
from litestar.security.jwt import Token
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.config import Settings
from zondarr.core.auth import AdminUser
from zondarr.core.exceptions import AuthenticationError
from zondarr.repositories.admin import AdminAccountRepository, RefreshTokenRepository
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.auth import REFRESH_TOKEN_EXPIRY_DAYS, AuthService
from zondarr.services.oauth_session import OAuthSessionStore
from zondarr.services.settings import SettingsService

from .schemas import (
    AdminEmailUpdate,
    AdminMeResponse,
    AdminPasswordChange,
    AdminProfileResponse,
    AdminSetupRequest,
    AuthFieldInfo,
    AuthMethodsResponse,
    AuthSuccessResponse,
    ExternalLoginRequest,
    LinkProviderRequest,
    LinkProviderResponse,
    LoginRequest,
    LoginResponse,
    OnboardingStatusResponse,
    PasswordChangeResponse,
    ProviderAuthInfo,
)
from .totp import create_challenge_token

# Access token lifetime
ACCESS_TOKEN_MINUTES = 15


class AuthController(Controller):
    """Controller for authentication endpoints."""

    path: str = "/api/auth"
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
        """Resolve the effective secure_cookies value.

        If the SECURE_COOKIES env var is set, use the Settings value (which
        came from the env var). Otherwise, check the database.
        """
        import os

        if os.environ.get("SECURE_COOKIES") is not None:
            return settings.secure_cookies
        service = SettingsService(AppSettingRepository(session))
        value, _ = await service.get_secure_cookies()
        return value

    def _create_refresh_cookie(self, raw_token: str, *, secure: bool = False) -> Cookie:
        """Create HTTP-only cookie for the refresh token."""
        return Cookie(
            key="zondarr_refresh_token",
            value=raw_token,
            httponly=True,
            secure=secure,
            samesite="lax",
            max_age=REFRESH_TOKEN_EXPIRY_DAYS * 86400,
            path="/",
        )

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

    @get(
        "/methods",
        status_code=HTTP_200_OK,
        summary="Get available authentication methods",
        exclude_from_auth=True,
    )
    async def get_methods(
        self, session: AsyncSession, settings: Settings
    ) -> AuthMethodsResponse:
        """Return available auth methods and whether setup is required."""
        service = self._create_auth_service(session)
        methods, descriptors = await service.get_auth_methods_with_providers(
            settings=settings
        )
        (
            setup,
            onboarding_required,
            onboarding_step,
        ) = await service.get_setup_and_onboarding_status()

        # Map provider descriptors to response schema
        provider_auth = [
            ProviderAuthInfo(
                method_name=desc.method_name,
                display_name=desc.display_name,
                flow_type=desc.flow_type,
                fields=[
                    AuthFieldInfo(
                        name=f.name,
                        label=f.label,
                        field_type=f.field_type,
                        placeholder=f.placeholder,
                        required=f.required,
                    )
                    for f in desc.fields
                ],
            )
            for desc in descriptors
        ]

        return AuthMethodsResponse(
            methods=methods,
            setup_required=setup,
            onboarding_required=onboarding_required,
            onboarding_step=onboarding_step,
            provider_auth=provider_auth,
        )

    @post(
        "/setup",
        status_code=HTTP_201_CREATED,
        summary="Create first admin account",
        exclude_from_auth=True,
    )
    async def setup(
        self,
        data: AdminSetupRequest,
        request: Request[None, None, State],
        session: AsyncSession,
        settings: Settings,
    ) -> Response[AuthSuccessResponse]:
        """Create the first admin account (only when no admins exist)."""
        # Validate bootstrap token (always required)
        expected_token: str | None = settings.bootstrap_token or getattr(
            request.app.state, "generated_bootstrap_token", None
        )
        if expected_token is None or not hmac.compare_digest(
            expected_token, data.bootstrap_token
        ):
            raise AuthenticationError(
                "Invalid or missing bootstrap token",
                "INVALID_BOOTSTRAP_TOKEN",
            )

        service = self._create_auth_service(session)
        admin = await service.setup_admin(
            data.username, data.password, email=data.email
        )
        await service.initialize_onboarding()

        # Issue tokens
        secret_key = settings.secret_key
        secure = await self._resolve_secure_cookies(session, settings)
        _, access_cookie = self._create_access_token(
            str(admin.id), secret_key, secure=secure
        )
        refresh_token = await service.create_refresh_token(admin)
        refresh_cookie = self._create_refresh_cookie(refresh_token, secure=secure)

        response = Response(
            AuthSuccessResponse(),
            status_code=HTTP_201_CREATED,
            cookies=[access_cookie, refresh_cookie],
        )
        return response

    @post(
        "/onboarding/advance",
        status_code=HTTP_200_OK,
        summary="Advance onboarding step",
    )
    async def advance_onboarding(
        self, session: AsyncSession
    ) -> OnboardingStatusResponse:
        """Advance onboarding by one step for explicit skip actions."""
        service = self._create_auth_service(session)
        onboarding_required, onboarding_step = await service.advance_onboarding()
        return OnboardingStatusResponse(
            onboarding_required=onboarding_required,
            onboarding_step=onboarding_step,
        )

    @post(
        "/login",
        status_code=HTTP_200_OK,
        summary="Login with username and password",
        exclude_from_auth=True,
    )
    async def login(
        self,
        data: LoginRequest,
        session: AsyncSession,
        settings: Settings,
    ) -> Response[LoginResponse]:
        """Authenticate with local username/password credentials.

        If the admin has TOTP enabled, returns totp_required=True with a
        challenge_token. The client must then call /api/auth/totp/verify
        or /api/auth/totp/backup-code to complete login.
        """
        service = self._create_auth_service(session)
        if await service.setup_required():
            raise AuthenticationError(
                "Initial setup must be completed first",
                "SETUP_REQUIRED",
            )
        admin = await service.authenticate_local(data.username, data.password)

        # Check if TOTP is required
        if admin.totp_enabled:
            nonce = secrets.token_hex(32)
            admin = await session.merge(admin)
            admin.totp_challenge_nonce = nonce
            await session.commit()
            challenge = create_challenge_token(
                str(admin.id), settings.secret_key, nonce
            )
            return Response(
                LoginResponse(totp_required=True, challenge_token=challenge),
                status_code=HTTP_200_OK,
            )

        # No TOTP — issue tokens normally
        secret_key = settings.secret_key
        secure = await self._resolve_secure_cookies(session, settings)
        _, access_cookie = self._create_access_token(
            str(admin.id), secret_key, secure=secure
        )
        refresh_token = await service.create_refresh_token(admin)
        refresh_cookie = self._create_refresh_cookie(refresh_token, secure=secure)

        return Response(
            LoginResponse(),
            status_code=HTTP_200_OK,
            cookies=[access_cookie, refresh_cookie],
        )

    @post(
        "/login/{method:str}",
        status_code=HTTP_200_OK,
        summary="Login with external provider",
        exclude_from_auth=True,
    )
    async def login_external(
        self,
        method: str,
        data: ExternalLoginRequest,
        session: AsyncSession,
        settings: Settings,
    ) -> Response[LoginResponse]:
        """Authenticate with an external provider.

        The credentials dict contents vary by provider; each registered
        provider declares its own required fields.

        If the admin has TOTP enabled, returns totp_required=True with a
        challenge_token. The client must then call /api/auth/totp/verify
        or /api/auth/totp/backup-code to complete login.
        """
        # Resolve redemption_token to auth_token server-side
        credentials = dict(data.credentials)
        if "redemption_token" in credentials:
            redemption_token = credentials.pop("redemption_token")
            store = OAuthSessionStore()
            result = await store.redeem(session, redemption_token)
            if result is not None:
                redeemed_provider, auth_token = result
                if redeemed_provider != method:
                    raise AuthenticationError(
                        "Redemption token provider mismatch",
                        "PROVIDER_MISMATCH",
                    )
                credentials["auth_token"] = auth_token
            else:
                raise AuthenticationError(
                    "Invalid or expired redemption token",
                    "INVALID_REDEMPTION_TOKEN",
                )

        service = self._create_auth_service(session)
        if await service.setup_required():
            raise AuthenticationError(
                "Initial setup must be completed first",
                "SETUP_REQUIRED",
            )
        admin = await service.authenticate_external(
            method,
            credentials,
            settings=settings,
        )

        # Check if TOTP is required
        if admin.totp_enabled:
            nonce = secrets.token_hex(32)
            admin = await session.merge(admin)
            admin.totp_challenge_nonce = nonce
            await session.commit()
            challenge = create_challenge_token(
                str(admin.id), settings.secret_key, nonce
            )
            return Response(
                LoginResponse(totp_required=True, challenge_token=challenge),
                status_code=HTTP_200_OK,
            )

        # No TOTP — issue tokens normally
        secret_key = settings.secret_key
        secure = await self._resolve_secure_cookies(session, settings)
        _, access_cookie = self._create_access_token(
            str(admin.id), secret_key, secure=secure
        )
        refresh_token = await service.create_refresh_token(admin)
        refresh_cookie = self._create_refresh_cookie(refresh_token, secure=secure)

        return Response(
            LoginResponse(),
            status_code=HTTP_200_OK,
            cookies=[access_cookie, refresh_cookie],
        )

    @post(
        "/refresh",
        status_code=HTTP_200_OK,
        summary="Refresh access token",
        exclude_from_auth=True,
    )
    async def refresh(
        self,
        request: Request[None, None, State],
        session: AsyncSession,
        settings: Settings,
    ) -> Response[AuthSuccessResponse]:
        """Exchange a refresh token for a new access token."""
        token = request.cookies.get("zondarr_refresh_token")
        if not token:
            raise AuthenticationError(
                "No refresh token provided", "MISSING_REFRESH_TOKEN"
            )

        service = self._create_auth_service(session)
        admin = await service.consume_refresh_token(token)

        secret_key = settings.secret_key
        secure = await self._resolve_secure_cookies(session, settings)
        _, access_cookie = self._create_access_token(
            str(admin.id), secret_key, secure=secure
        )
        new_refresh_token = await service.create_refresh_token(admin)
        refresh_cookie = self._create_refresh_cookie(new_refresh_token, secure=secure)

        return Response(
            AuthSuccessResponse(),
            status_code=HTTP_200_OK,
            cookies=[access_cookie, refresh_cookie],
        )

    @post(
        "/logout",
        status_code=HTTP_200_OK,
        summary="Logout and revoke tokens",
        exclude_from_auth=True,
    )
    async def logout(
        self,
        request: Request[None, None, State],
        session: AsyncSession,
        settings: Settings,
    ) -> Response[dict[str, bool]]:
        """Revoke tokens and clear cookies."""
        token = request.cookies.get("zondarr_refresh_token")
        if token:
            service = self._create_auth_service(session)
            await service.revoke_refresh_token(token)

        # Clear both cookies
        secure = await self._resolve_secure_cookies(session, settings)
        clear_access_cookie = Cookie(
            key="zondarr_access_token",
            value="",
            httponly=True,
            secure=secure,
            samesite="lax",
            max_age=0,
            path="/",
        )
        clear_refresh_cookie = Cookie(
            key="zondarr_refresh_token",
            value="",
            httponly=True,
            secure=secure,
            samesite="lax",
            max_age=0,
            path="/",
        )

        return Response(
            {"success": True},
            status_code=HTTP_200_OK,
            cookies=[clear_access_cookie, clear_refresh_cookie],
        )

    @get(
        "/me",
        status_code=HTTP_200_OK,
        summary="Get current admin info",
    )
    async def me(
        self,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
    ) -> AdminMeResponse:
        """Return current authenticated admin's info."""
        user: AdminUser = request.user
        service = self._create_auth_service(session)
        onboarding_required, onboarding_step = await service.get_onboarding_status()

        # Look up totp_enabled from the database
        admin_repo = AdminAccountRepository(session)
        admin = await admin_repo.get_by_id(user.id)
        totp_enabled = admin.totp_enabled if admin else False

        return AdminMeResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            auth_method=user.auth_method,
            totp_enabled=totp_enabled,
            onboarding_required=onboarding_required,
            onboarding_step=onboarding_step,
        )

    @patch(
        "/me",
        status_code=HTTP_200_OK,
        summary="Update admin profile",
    )
    async def update_profile(
        self,
        data: AdminEmailUpdate,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
    ) -> AdminProfileResponse:
        """Update the current admin's email."""
        user: AdminUser = request.user
        service = self._create_auth_service(session)
        admin = await service.update_email(user.id, data.email)
        return AdminProfileResponse(
            id=admin.id,
            username=admin.username,
            email=admin.email,
            auth_method=admin.auth_method,
        )

    @post(
        "/me/change-password",
        status_code=HTTP_200_OK,
        summary="Change admin password",
    )
    async def change_password(
        self,
        data: AdminPasswordChange,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
    ) -> PasswordChangeResponse:
        """Change the current admin's password."""
        user: AdminUser = request.user
        service = self._create_auth_service(session)
        _ = await service.change_password(
            user.id, data.current_password, data.new_password
        )
        return PasswordChangeResponse(
            success=True,
            message="Password changed successfully",
        )

    @post(
        "/me/link-provider",
        status_code=HTTP_200_OK,
        summary="Link external auth provider to current admin",
    )
    async def link_provider(
        self,
        data: LinkProviderRequest,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
        settings: Settings,
    ) -> LinkProviderResponse:
        """Link an external auth provider to the current admin account."""
        # Resolve redemption_token to auth_token server-side
        credentials = dict(data.credentials)
        if "redemption_token" in credentials:
            redemption_token = credentials.pop("redemption_token")
            store = OAuthSessionStore()
            result = await store.redeem(session, redemption_token)
            if result is not None:
                redeemed_provider, auth_token = result
                if redeemed_provider != data.method:
                    raise AuthenticationError(
                        "Redemption token provider mismatch",
                        "PROVIDER_MISMATCH",
                    )
                credentials["auth_token"] = auth_token
            else:
                raise AuthenticationError(
                    "Invalid or expired redemption token",
                    "INVALID_REDEMPTION_TOKEN",
                )

        user: AdminUser = request.user
        service = self._create_auth_service(session)
        admin = await service.link_external_provider(
            user.id,
            data.method,
            credentials,
            settings=settings,
        )
        return LinkProviderResponse(
            method=admin.auth_method,
            external_id=admin.external_id or "",
        )
