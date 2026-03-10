"""Jellyfin admin authentication provider.

Handles Jellyfin credential verification for admin login.
Extracted from services/auth.py to be provider-self-contained.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from zondarr.core.exceptions import AuthenticationError

if TYPE_CHECKING:
    from zondarr.config import Settings
    from zondarr.models.admin import AdminAccount
    from zondarr.repositories.admin import AdminAccountRepository


class JellyfinAdminAuth:
    """Jellyfin admin authentication via server credentials.

    Verifies the user is a Jellyfin administrator.
    Looks up an existing linked AdminAccount.

    Implements AdminAuthProvider protocol.
    """

    async def verify(
        self,
        credentials: Mapping[str, str],
        *,
        settings: Settings,
    ) -> tuple[str, str, str | None]:
        """Verify Jellyfin credentials without creating accounts.

        Validates the username/password against the Jellyfin server
        and checks for administrator status.

        Args:
            credentials: Must contain "username", "password" keys.
            settings: Application settings (needs provider_credentials).

        Returns:
            A tuple of (external_id, display_name, email_or_none).
            For Jellyfin, external_id is the Jellyfin user ID; email is None.

        Raises:
            AuthenticationError: If verification fails or user is not admin.
        """
        import httpx

        # Use configured Jellyfin URL — never trust caller-provided URLs
        jf_creds = settings.provider_credentials.get("jellyfin", {})
        server_url = jf_creds.get("url", "")

        if not server_url:
            raise AuthenticationError(
                "Jellyfin authentication is not configured",
                "JELLYFIN_NOT_CONFIGURED",
            )

        username = str(credentials.get("username", ""))
        password = str(credentials.get("password", ""))

        if not username or not password:
            raise AuthenticationError(
                "Username and password are required",
                "MISSING_CREDENTIALS",
            )

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

        return jellyfin_user_id, username, None

    async def authenticate(
        self,
        credentials: Mapping[str, str],
        *,
        settings: Settings,
        admin_repo: AdminAccountRepository,
    ) -> AdminAccount:
        """Authenticate via Jellyfin credentials.

        Verifies credentials and looks up an existing linked account.

        Args:
            credentials: Must contain "username", "password" keys.
            settings: Application settings (needs provider_credentials).
            admin_repo: Admin account repository.

        Returns:
            The authenticated AdminAccount.

        Raises:
            AuthenticationError: If verification fails or no linked account exists.
        """
        external_id, _display_name, _email = await self.verify(
            credentials, settings=settings
        )

        # Check for existing account with this external ID
        admin = await admin_repo.get_by_external_id(external_id, "jellyfin")

        if admin is not None:
            if not admin.enabled:
                raise AuthenticationError("Account is disabled", "ACCOUNT_DISABLED")
            admin.last_login_at = datetime.now(UTC)
            return admin

        raise AuthenticationError(
            "Account not linked to Zondarr. Link your Jellyfin account in Settings.",
            "NO_LINKED_ACCOUNT",
        )

    def is_configured(self, settings: Settings) -> bool:
        """Check if Jellyfin auth is configured.

        Jellyfin auth requires a configured JELLYFIN_URL.
        """
        jf_creds = settings.provider_credentials.get("jellyfin", {})
        return bool(jf_creds.get("url"))
