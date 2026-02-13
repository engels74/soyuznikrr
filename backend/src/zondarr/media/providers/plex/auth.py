"""Plex admin authentication provider.

Handles Plex OAuth token verification for admin login.
Extracted from services/auth.py to be provider-self-contained.
"""

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from plexapi.exceptions import PlexApiException
from requests.exceptions import RequestException

from zondarr.core.exceptions import AuthenticationError
from zondarr.models.admin import AdminAccount

if TYPE_CHECKING:
    from zondarr.config import Settings
    from zondarr.repositories.admin import AdminAccountRepository


class PlexAdminAuth:
    """Plex admin authentication via OAuth token verification.

    Verifies the token is valid and the account matches the configured
    Plex server owner. Auto-creates an AdminAccount for verified owners.

    Implements AdminAuthProvider protocol.
    """

    async def authenticate(
        self,
        credentials: Mapping[str, str],
        *,
        settings: Settings,
        admin_repo: AdminAccountRepository,
    ) -> AdminAccount:
        """Authenticate via Plex OAuth token.

        Args:
            credentials: Must contain "auth_token" key.
            settings: Application settings (needs provider_credentials).
            admin_repo: Admin account repository.

        Returns:
            The authenticated or auto-created AdminAccount.

        Raises:
            AuthenticationError: If Plex is not configured, verification fails,
                or the account is not the server owner.
        """
        from plexapi.myplex import MyPlexAccount

        auth_token = str(credentials.get("auth_token", ""))
        if not auth_token:
            raise AuthenticationError(
                "Plex auth token is required", "MISSING_AUTH_TOKEN"
            )

        # Get configured Plex token from provider credentials
        plex_creds = settings.provider_credentials.get("plex", {})
        configured_plex_token = plex_creds.get("api_key")

        if not configured_plex_token:
            raise AuthenticationError(
                "Plex authentication is not configured", "PLEX_NOT_CONFIGURED"
            )

        try:
            account = await asyncio.to_thread(MyPlexAccount, token=auth_token)
            _raw_email: object = account.email  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            _raw_username: object = account.username  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            plex_email = str(_raw_email)  # pyright: ignore[reportUnknownArgumentType]
            plex_username = str(_raw_username) if _raw_username else plex_email  # pyright: ignore[reportUnknownArgumentType]
        except PlexApiException as exc:
            raise AuthenticationError(
                "Failed to verify Plex account", "PLEX_AUTH_FAILED"
            ) from exc
        except RequestException as exc:
            raise AuthenticationError(
                "Failed to connect to Plex services", "PLEX_AUTH_FAILED"
            ) from exc

        # Verify the authenticating user is the configured Plex server owner
        try:
            owner_account = await asyncio.to_thread(
                MyPlexAccount, token=configured_plex_token
            )
            _raw_owner_email: object = owner_account.email  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            owner_email = str(_raw_owner_email)  # pyright: ignore[reportUnknownArgumentType]
        except PlexApiException as exc:
            raise AuthenticationError(
                "Failed to verify Plex server owner", "PLEX_AUTH_FAILED"
            ) from exc
        except RequestException as exc:
            raise AuthenticationError(
                "Failed to connect to Plex services", "PLEX_AUTH_FAILED"
            ) from exc

        if plex_email.lower() != owner_email.lower():
            raise AuthenticationError(
                "Account is not the Plex server owner", "NOT_SERVER_OWNER"
            )

        # Check for existing account with this external ID
        admin = await admin_repo.get_by_external_id(plex_email, "plex")

        if admin is not None:
            if not admin.enabled:
                raise AuthenticationError("Account is disabled", "ACCOUNT_DISABLED")
            admin.last_login_at = datetime.now(UTC)
            return admin

        # Auto-create admin account for verified Plex server owner
        admin = AdminAccount(
            username=plex_username.lower().replace(" ", "_")[:32],
            email=plex_email,
            auth_method="plex",
            external_id=plex_email,
            enabled=True,
            last_login_at=datetime.now(UTC),
        )
        return await admin_repo.create(admin)

    def is_configured(self, settings: Settings) -> bool:
        """Check if Plex auth is configured.

        Plex auth requires a configured PLEX_TOKEN.
        """
        plex_creds = settings.provider_credentials.get("plex", {})
        return bool(plex_creds.get("api_key"))
