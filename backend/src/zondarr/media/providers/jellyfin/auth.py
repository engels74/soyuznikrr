"""Jellyfin admin authentication provider.

Handles Jellyfin credential verification for admin login.
Extracted from services/auth.py to be provider-self-contained.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from zondarr.core.exceptions import AuthenticationError
from zondarr.models.admin import AdminAccount

if TYPE_CHECKING:
    from zondarr.config import Settings
    from zondarr.repositories.admin import AdminAccountRepository


class JellyfinAdminAuth:
    """Jellyfin admin authentication via server credentials.

    Verifies the user is a Jellyfin administrator.
    Auto-creates an AdminAccount if verified admin.

    Implements AdminAuthProvider protocol.
    """

    async def authenticate(
        self,
        credentials: Mapping[str, str],
        *,
        settings: Settings,
        admin_repo: AdminAccountRepository,
    ) -> AdminAccount:
        """Authenticate via Jellyfin credentials.

        Args:
            credentials: Must contain "server_url", "username", "password" keys.
            settings: Application settings.
            admin_repo: Admin account repository.

        Returns:
            The authenticated or auto-created AdminAccount.

        Raises:
            AuthenticationError: If verification fails.
        """
        del settings  # required by AdminAuthProvider protocol

        import httpx

        server_url = str(credentials.get("server_url", ""))
        username = str(credentials.get("username", ""))
        password = str(credentials.get("password", ""))

        if not server_url or not username or not password:
            raise AuthenticationError(
                "Server URL, username, and password are required",
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

        # Check for existing account with this external ID
        admin = await admin_repo.get_by_external_id(jellyfin_user_id, "jellyfin")

        if admin is not None:
            if not admin.enabled:
                raise AuthenticationError("Account is disabled", "ACCOUNT_DISABLED")
            admin.last_login_at = datetime.now(UTC)
            return admin

        # Auto-create admin account for Jellyfin admin
        admin = AdminAccount(
            username=username.lower().replace(" ", "_")[:32],
            auth_method="jellyfin",
            external_id=jellyfin_user_id,
            enabled=True,
            last_login_at=datetime.now(UTC),
        )
        return await admin_repo.create(admin)

    def is_configured(self, settings: Settings) -> bool:
        """Check if Jellyfin auth is configured.

        Jellyfin auth requires a configured JELLYFIN_URL.
        """
        jf_creds = settings.provider_credentials.get("jellyfin", {})
        return bool(jf_creds.get("url"))
