"""RedemptionService for invitation redemption orchestration.

Provides the complete redemption flow for invitation codes:
1. Validate the invitation
2. Create users on each target media server
3. Apply library restrictions and permissions
4. Create local Identity and User records
5. Increment the invitation use count

Implements rollback on failure to ensure atomicity.

Implements Property 15: Redemption Creates Users on All Target Servers -
successful redemption creates exactly N User records for N target servers.

Implements Property 16: Redemption Increments Use Count -
successful redemption increments the invitation use_count by 1.

Implements Property 17: Duration Days Sets Expiration -
if duration_days is set, creates Identity and Users with calculated expires_at.

Implements Property 18: Rollback on Failure -
if redemption fails after creating users on some servers, all created users
are deleted and no local records are created.

Implements Property 13: Redemption Rollback on Failure (Plex) -
if redemption fails after creating users on some servers including Plex,
all created users are deleted via delete_user and no local records are created.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

import structlog

from zondarr.core.exceptions import RedemptionError
from zondarr.media.exceptions import MediaClientError
from zondarr.media.registry import registry
from zondarr.media.types import ExternalUser
from zondarr.models.identity import Identity, User
from zondarr.models.media_server import MediaServer
from zondarr.services.invitation import InvitationService, InvitationValidationFailure
from zondarr.services.user import UserService

log = structlog.get_logger()  # pyright: ignore[reportAny]  # structlog lacks stubs


# Default permissions applied to newly created users
DEFAULT_PERMISSIONS: Mapping[str, bool] = {
    "can_stream": True,
    "can_download": False,
    "can_transcode": True,
    "can_sync": False,
}


class RedemptionService:
    """Orchestrates invitation redemption with rollback support.

    Handles the complete redemption flow:
    1. Validate invitation
    2. Create users on each target server
    3. Apply library restrictions and permissions
    4. Create local Identity and User records
    5. Increment invitation use count

    If any step fails, rolls back all changes to ensure atomicity.

    Attributes:
        invitation_service: The InvitationService for invitation operations.
        user_service: The UserService for user/identity operations.
    """

    invitation_service: InvitationService
    user_service: UserService

    def __init__(
        self,
        invitation_service: InvitationService,
        user_service: UserService,
        /,
    ) -> None:
        """Initialize the RedemptionService.

        Args:
            invitation_service: The InvitationService for invitation operations
                (positional-only).
            user_service: The UserService for user/identity operations
                (positional-only).
        """
        self.invitation_service = invitation_service
        self.user_service = user_service

    async def redeem(
        self,
        code: str,
        /,
        *,
        username: str,
        password: str,
        email: str | None = None,
        auth_token: str | None = None,
    ) -> tuple[Identity, Sequence[User]]:
        """Redeem an invitation code and create user accounts.

        Uses a **reserve-first** strategy: atomically increments
        ``use_count`` via a single SQL UPDATE *before* any other work.
        If any subsequent step fails, the raised ``RedemptionError``
        propagates to the DI layer, which rolls back the entire
        database transaction (including the use_count increment).

        External user cleanup (HTTP calls to media servers) is performed
        explicitly before re-raising because those side-effects are
        outside the DB transaction.

        Implements Requirements 14.3-14.8, 15.1, 15.2.

        Args:
            code: The invitation code to redeem (positional-only).
            username: Username for the new accounts (keyword-only).
            password: Password for the new accounts (keyword-only).
            email: Optional email address (keyword-only).
            auth_token: Optional auth token for OAuth flows (keyword-only).

        Returns:
            Tuple of (Identity, list of Users created).

        Raises:
            RedemptionError: If invitation is invalid or redemption fails.
            RepositoryError: If database operations fail.
        """
        # Step 1: Atomically reserve one use (Requirement 14.3 / 14.8)
        reserved, failure = await self.invitation_service.reserve(code)
        if not reserved:
            raise RedemptionError(
                self._failure_message(failure),
                redemption_error_code=self._failure_error_code(failure),
            )

        # Step 2: Fetch the invitation for target_servers / libraries
        invitation = await self.invitation_service.get_by_code(code)

        # Step 3: Create users on each target server (Requirement 14.4)
        created_external_users: list[tuple[MediaServer, ExternalUser]] = []

        try:
            for server in invitation.target_servers:
                client = registry.create_client_for_server(server)

                async with client:
                    external_user = await client.create_user(
                        username,
                        password,
                        email=email,
                        auth_token=auth_token,
                    )
                    created_external_users.append((server, external_user))

                    log.info(  # pyright: ignore[reportAny]
                        "Created user on media server",
                        server_name=server.name,
                        server_type=server.server_type,
                        username=username,
                        external_user_id=external_user.external_user_id,
                    )

                    # Step 4: Apply library restrictions (Requirement 14.5)
                    if invitation.allowed_libraries:
                        library_ids = [
                            lib.external_id
                            for lib in invitation.allowed_libraries
                            if lib.media_server_id == server.id
                        ]
                        if library_ids:
                            _ = await client.set_library_access(
                                external_user.external_user_id,
                                library_ids,
                            )
                            log.info(  # pyright: ignore[reportAny]
                                "Applied library restrictions",
                                server_name=server.name,
                                library_count=len(library_ids),
                            )

                    # Step 5: Apply permissions (Requirement 14.6)
                    permissions = dict(DEFAULT_PERMISSIONS)
                    _ = await client.update_permissions(
                        external_user.external_user_id,
                        permissions=permissions,
                    )
                    log.info(  # pyright: ignore[reportAny]
                        "Applied permissions",
                        server_name=server.name,
                        permissions=permissions,
                    )

            # Step 6: Calculate expiration from duration_days (Requirement 14.9)
            expires_at: datetime | None = None
            if invitation.duration_days is not None:
                expires_at = datetime.now(UTC) + timedelta(
                    days=invitation.duration_days
                )

            # Step 6.5: Clean up stale local users (e.g. sync-imported duplicates)
            cleaned = await self.user_service.cleanup_stale_local_users(
                created_external_users
            )
            if cleaned > 0:
                log.info(  # pyright: ignore[reportAny]
                    "Cleaned stale local users before creating new records",
                    cleaned_count=cleaned,
                )

            # Step 7: Create local Identity and User records (Requirement 14.7)
            identity, users = await self.user_service.create_identity_with_users(
                display_name=username,
                email=email,
                expires_at=expires_at,
                external_users=created_external_users,
                invitation_id=invitation.id,
            )

        except MediaClientError as e:
            # Roll back external users (HTTP calls, outside DB transaction)
            log.warning(  # pyright: ignore[reportAny]
                "Redemption failed, rolling back created users",
                error=str(e),
                created_count=len(created_external_users),
            )
            await self._rollback_users(created_external_users)

            error_code = (
                "USERNAME_TAKEN"
                if e.media_error_code and "USERNAME_TAKEN" in e.media_error_code.upper()
                else "SERVER_ERROR"
            )
            raise RedemptionError(
                str(e),
                redemption_error_code=error_code,
                failed_server=e.server_url or "media server",
            ) from e
        except RedemptionError:
            # Already a RedemptionError (e.g. from reservation) — just re-raise
            raise
        except Exception as e:
            log.error(  # pyright: ignore[reportAny]
                "Unexpected error during redemption, rolling back",
                error=str(e),
                created_count=len(created_external_users),
            )
            await self._rollback_users(created_external_users)
            raise RedemptionError(
                f"Redemption failed: {e}",
                redemption_error_code="SERVER_ERROR",
            ) from e

        log.info(  # pyright: ignore[reportAny]
            "Redemption completed successfully",
            code=code,
            identity_id=str(identity.id),
            servers_count=len(created_external_users),
        )

        return identity, users

    async def _rollback_users(
        self,
        created_users: list[tuple[MediaServer, ExternalUser]],
    ) -> None:
        """Delete users created during a failed redemption.

        Best-effort cleanup: logs but does not raise on individual failures.
        This ensures we attempt to clean up all created users even if some
        deletions fail.

        Implements Requirement 15.2: If a user is created on server A but
        fails on server B, delete the user from server A.

        Args:
            created_users: List of (MediaServer, ExternalUser) tuples to delete.
        """
        for server, external_user in created_users:
            try:
                client = registry.create_client_for_server(server)
                async with client:
                    deleted = await client.delete_user(external_user.external_user_id)
                    if deleted:
                        log.info(  # pyright: ignore[reportAny]
                            "Rolled back user creation",
                            server_name=server.name,
                            external_user_id=external_user.external_user_id,
                        )
                    else:
                        log.warning(  # pyright: ignore[reportAny]
                            "User not found during rollback",
                            server_name=server.name,
                            external_user_id=external_user.external_user_id,
                        )
            except Exception as e:
                # Log but don't raise - best effort cleanup
                log.error(  # pyright: ignore[reportAny]
                    "Failed to rollback user creation",
                    server_name=server.name,
                    external_user_id=external_user.external_user_id,
                    error=str(e),
                )

    def _failure_message(self, failure: InvitationValidationFailure | None) -> str:
        """Convert failure enum to user-friendly message.

        Args:
            failure: The validation failure reason.

        Returns:
            A human-readable error message.
        """
        messages: dict[InvitationValidationFailure | None, str] = {
            InvitationValidationFailure.NOT_FOUND: "Invitation code not found",
            InvitationValidationFailure.DISABLED: "This invitation has been disabled",
            InvitationValidationFailure.EXPIRED: "This invitation has expired",
            InvitationValidationFailure.MAX_USES_REACHED: (
                "This invitation has reached its usage limit"
            ),
            None: "Invalid invitation",
        }
        return messages.get(failure, "Invalid invitation")

    def _failure_error_code(
        self, failure: InvitationValidationFailure | None
    ) -> str:
        """Convert failure enum to machine-readable error code.

        Args:
            failure: The validation failure reason.

        Returns:
            A machine-readable error code string.
        """
        codes: dict[InvitationValidationFailure | None, str] = {
            InvitationValidationFailure.NOT_FOUND: "INVITATION_NOT_FOUND",
            InvitationValidationFailure.DISABLED: "INVITATION_DISABLED",
            InvitationValidationFailure.EXPIRED: "INVITATION_EXPIRED",
            InvitationValidationFailure.MAX_USES_REACHED: "MAX_USES_REACHED",
            None: "INVALID_INVITATION",
        }
        return codes.get(failure, "INVALID_INVITATION")
