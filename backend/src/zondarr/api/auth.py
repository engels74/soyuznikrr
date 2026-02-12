"""Authentication API controller.

Provides endpoints for admin authentication:
- GET /api/auth/methods — Available auth methods + setup_required flag
- POST /api/auth/setup — Create first admin account
- POST /api/auth/login — Local username/password login
- POST /api/auth/login/{method} — External provider login (plex, jellyfin, etc.)
- POST /api/auth/refresh — Exchange refresh token for new access token
- POST /api/auth/logout — Revoke tokens and clear cookies
- GET /api/auth/me — Current admin info (requires auth)
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from litestar import Controller, Request, Response, get, post
from litestar.datastructures import Cookie, State
from litestar.security.jwt import Token
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.config import Settings
from zondarr.core.auth import AdminUser
from zondarr.core.exceptions import AuthenticationError
from zondarr.media.registry import registry
from zondarr.repositories.admin import AdminAccountRepository, RefreshTokenRepository
from zondarr.services.auth import AuthService

from .schemas import (
    AdminMeResponse,
    AdminSetupRequest,
    AuthFieldInfo,
    AuthMethodsResponse,
    AuthTokenResponse,
    ExternalLoginRequest,
    LoginRequest,
    ProviderAuthInfo,
    RefreshRequest,
)

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
        self, session: AsyncSession, state: State
    ) -> AuthMethodsResponse:
        """Return available auth methods and whether setup is required."""
        service = self._create_auth_service(session)
        settings: Settings = state.settings  # pyright: ignore[reportAny]
        methods = await service.get_available_auth_methods(settings=settings)
        setup = await service.setup_required()

        # Build provider auth metadata from registry
        provider_auth: list[ProviderAuthInfo] = []
        for desc in registry.get_admin_auth_descriptors():
            if desc.method_name in methods:
                provider_auth.append(
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
                )

        return AuthMethodsResponse(
            methods=methods,
            setup_required=setup,
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
        session: AsyncSession,
        state: State,
    ) -> Response[AuthTokenResponse]:
        """Create the first admin account (only when no admins exist)."""
        service = self._create_auth_service(session)

        if not await service.setup_required():
            raise AuthenticationError("Setup already completed", "SETUP_NOT_REQUIRED")

        admin = await service.create_admin(
            data.username, data.password, email=data.email
        )

        # Issue tokens
        secret_key: str = state.settings.secret_key  # pyright: ignore[reportAny]
        secure: bool = state.settings.secure_cookies  # pyright: ignore[reportAny]
        _, access_cookie = self._create_access_token(
            str(admin.id), secret_key, secure=secure
        )
        refresh_token = await service.create_refresh_token(admin)

        response = Response(
            AuthTokenResponse(refresh_token=refresh_token),
            status_code=HTTP_201_CREATED,
            cookies=[access_cookie],
        )
        return response

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
        state: State,
    ) -> Response[AuthTokenResponse]:
        """Authenticate with local username/password credentials."""
        service = self._create_auth_service(session)
        admin = await service.authenticate_local(data.username, data.password)

        secret_key: str = state.settings.secret_key  # pyright: ignore[reportAny]
        secure: bool = state.settings.secure_cookies  # pyright: ignore[reportAny]
        _, access_cookie = self._create_access_token(
            str(admin.id), secret_key, secure=secure
        )
        refresh_token = await service.create_refresh_token(admin)

        return Response(
            AuthTokenResponse(refresh_token=refresh_token),
            status_code=HTTP_200_OK,
            cookies=[access_cookie],
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
        state: State,
    ) -> Response[AuthTokenResponse]:
        """Authenticate with an external provider (plex, jellyfin, etc.).

        The credentials dict contents vary by provider:
        - plex: {"auth_token": "..."}
        - jellyfin: {"server_url": "...", "username": "...", "password": "..."}
        """
        service = self._create_auth_service(session)
        settings: Settings = state.settings  # pyright: ignore[reportAny]
        admin = await service.authenticate_external(
            method,
            data.credentials,
            settings=settings,
        )

        secret_key: str = state.settings.secret_key  # pyright: ignore[reportAny]
        secure: bool = state.settings.secure_cookies  # pyright: ignore[reportAny]
        _, access_cookie = self._create_access_token(
            str(admin.id), secret_key, secure=secure
        )
        refresh_token = await service.create_refresh_token(admin)

        return Response(
            AuthTokenResponse(refresh_token=refresh_token),
            status_code=HTTP_200_OK,
            cookies=[access_cookie],
        )

    @post(
        "/refresh",
        status_code=HTTP_200_OK,
        summary="Refresh access token",
        exclude_from_auth=True,
    )
    async def refresh(
        self,
        data: RefreshRequest,
        session: AsyncSession,
        state: State,
    ) -> Response[AuthTokenResponse]:
        """Exchange a refresh token for a new access token."""
        service = self._create_auth_service(session)
        admin = await service.validate_refresh_token(data.refresh_token)

        # Revoke old refresh token and issue new ones (token rotation)
        await service.revoke_refresh_token(data.refresh_token)

        secret_key: str = state.settings.secret_key  # pyright: ignore[reportAny]
        secure: bool = state.settings.secure_cookies  # pyright: ignore[reportAny]
        _, access_cookie = self._create_access_token(
            str(admin.id), secret_key, secure=secure
        )
        new_refresh_token = await service.create_refresh_token(admin)

        return Response(
            AuthTokenResponse(refresh_token=new_refresh_token),
            status_code=HTTP_200_OK,
            cookies=[access_cookie],
        )

    @post(
        "/logout",
        status_code=HTTP_200_OK,
        summary="Logout and revoke tokens",
        exclude_from_auth=True,
    )
    async def logout(
        self,
        session: AsyncSession,
        state: State,
        data: RefreshRequest | None = None,
    ) -> Response[dict[str, bool]]:
        """Revoke tokens and clear cookies."""
        if data is not None:
            service = self._create_auth_service(session)
            await service.revoke_refresh_token(data.refresh_token)

        # Clear access token cookie
        secure: bool = state.settings.secure_cookies  # pyright: ignore[reportAny]
        clear_cookie = Cookie(
            key="zondarr_access_token",
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
            cookies=[clear_cookie],
        )

    @get(
        "/me",
        status_code=HTTP_200_OK,
        summary="Get current admin info",
    )
    async def me(self, request: Request[AdminUser, Token, State]) -> AdminMeResponse:
        """Return current authenticated admin's info."""
        user: AdminUser = request.user
        return AdminMeResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            auth_method=user.auth_method,
        )
