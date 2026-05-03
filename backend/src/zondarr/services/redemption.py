"""RedemptionService for invitation redemption orchestration.

Provides the complete redemption flow for invitation codes:
1. Validate the invitation
2. Create users on each target media server
3. Create local Identity and User records
4. Increment the invitation use count
5. Apply library restrictions and permissions (background, non-blocking)

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

import asyncio
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.exc import IntegrityError

from zondarr.core.exceptions import (
    ExternalServiceError,
    RedemptionError,
    RepositoryError,
)
from zondarr.core.retry import RetryPolicy
from zondarr.core.wizard_token import verify_wizard_completion
from zondarr.media.exceptions import MediaClientError
from zondarr.media.protocol import MediaClient
from zondarr.media.provider import JoinFlowType
from zondarr.media.registry import registry
from zondarr.media.types import ExternalUser
from zondarr.models.identity import Identity, User
from zondarr.models.media_server import MediaServer
from zondarr.services.invitation import InvitationService, InvitationValidationFailure
from zondarr.services.user import UserService

log = structlog.get_logger()  # pyright: ignore[reportAny]  # structlog lacks stubs

# Strong references to fire-and-forget background tasks so they are
# not garbage-collected before completion.
_background_tasks: set[asyncio.Task[None]] = set()

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
    3. Create local Identity and User records
    4. Increment invitation use count
    5. Apply library restrictions and permissions (background task)

    If any step fails, rolls back all changes to ensure atomicity.
    Library sharing and permission application run in fire-and-forget
    background tasks to prevent worker exhaustion from slow Plex API calls.

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
        oauth_provider: str | None = None,
        pre_wizard_token: str | None = None,
        secret_key: str | None = None,
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

        When the invitation has a ``pre_wizard_id`` configured,
        ``pre_wizard_token`` must contain a valid signed wizard completion
        token matching that wizard. Without it, redemption is rejected.

        Args:
            code: The invitation code to redeem (positional-only).
            username: Username for the new accounts (keyword-only).
            password: Password for the new accounts (keyword-only).
            email: Optional email address (keyword-only).
            auth_token: Optional auth token for OAuth flows (keyword-only).
            oauth_provider: Provider that issued ``auth_token`` (e.g.
                ``"plex"``). Required when ``auth_token`` is supplied so the
                redemption can verify the OAuth session matches the
                invitation's OAuth-requiring target server (keyword-only).
            pre_wizard_token: Signed wizard completion token (keyword-only).
            secret_key: App secret key for verifying wizard tokens (keyword-only).

        Returns:
            Tuple of (Identity, list of Users created).

        Raises:
            RedemptionError: If invitation is invalid or redemption fails.
            RepositoryError: If database operations fail.
        """
        # Step 1: Atomically reserve one use
        reserved, failure = await self.invitation_service.reserve(code)
        if not reserved:
            raise RedemptionError(
                self._failure_message(failure),
                redemption_error_code=self._failure_error_code(failure),
            )

        # Step 2: Fetch the invitation for target_servers / libraries
        invitation = await self.invitation_service.get_by_code(code)

        # Step 2.5: Verify pre-wizard completion if required
        if invitation.pre_wizard_id is not None:
            if (
                pre_wizard_token is None
                or secret_key is None
                or not verify_wizard_completion(
                    pre_wizard_token,
                    invitation.pre_wizard_id,
                    secret_key,
                )
            ):
                raise RedemptionError(
                    "Pre-wizard completion is required before redeeming this invitation",
                    redemption_error_code="WIZARD_REQUIRED",
                )

        # Step 2.75: Validate OAuth requirements for each target server.
        # - If the server uses an OAUTH_LINK join flow, an auth_token is
        #   required (OAUTH_REQUIRED).
        # - If a token was supplied, the originating provider must match the
        #   server type (OAUTH_PROVIDER_MISMATCH). This mirrors the guard in
        #   ``api/auth.py`` for admin-login / link-provider and prevents a
        #   redemption token issued for one provider from being silently
        #   accepted against an invitation targeting another.
        for server in invitation.target_servers:
            provider = registry.get_provider(server.server_type)
            join_flow = provider.join_flow
            requires_oauth = (
                join_flow is not None and join_flow.flow_type == JoinFlowType.OAUTH_LINK
            )
            if not requires_oauth:
                continue
            if auth_token is None:
                raise RedemptionError(
                    "OAuth authentication is required for this invitation",
                    redemption_error_code="OAUTH_REQUIRED",
                )
            if oauth_provider is not None and oauth_provider != server.server_type:
                raise RedemptionError(
                    "Redemption token provider does not match invitation target",
                    redemption_error_code="OAUTH_PROVIDER_MISMATCH",
                    failed_server=server.name,
                )

        # Step 2.8: Check username uniqueness across target servers
        for server in invitation.target_servers:
            existing = (
                await self.user_service.user_repository.get_by_username_and_server(
                    username, server.id
                )
            )
            if existing is not None:
                raise RedemptionError(
                    f"Username '{username}' is already taken on server '{server.name}'",
                    redemption_error_code="USERNAME_TAKEN",
                    failed_server=server.name,
                )

        # Step 3: Create users on each target server
        created_external_users: list[tuple[MediaServer, ExternalUser]] = []
        # Plain data for rollback — avoids accessing expired SQLAlchemy objects
        rollback_data: list[tuple[str, str, str, str, str]] = []
        # Collect data for background library sharing / permission tasks
        deferred_tasks: list[tuple[MediaServer, ExternalUser, list[str] | None]] = []

        try:
            for server in invitation.target_servers:
                # Compute per-server library IDs before user creation
                # so they can be applied at share/invite time (not just after)
                server_library_ids: list[str] | None = None
                if invitation.allowed_libraries:
                    ids = [
                        lib.external_id
                        for lib in invitation.allowed_libraries
                        if lib.media_server_id == server.id
                    ]
                    if ids:
                        server_library_ids = ids

                (
                    external_user,
                    resolved_url,
                    resolved_api_key,
                ) = await self._create_user_with_retry(
                    server=server,
                    username=username,
                    password=password,
                    email=email,
                    auth_token=auth_token,
                    library_ids=server_library_ids,
                )

                created_external_users.append((server, external_user))
                # Use resolved credentials from the client (decrypted /
                # env-overridden) so rollback never sees encrypted keys.
                rollback_data.append(
                    (
                        server.server_type,
                        resolved_url,
                        resolved_api_key,
                        server.name,
                        external_user.external_user_id,
                    )
                )

                log.info(  # pyright: ignore[reportAny]
                    "Created user on media server",
                    server_name=server.name,
                    server_type=server.server_type,
                    username=username,
                    external_user_id=external_user.external_user_id,
                )

                # Defer library sharing and permissions to background
                deferred_tasks.append((server, external_user, server_library_ids))

            # Step 4: Calculate expiration from duration_days
            expires_at: datetime | None = None
            if invitation.duration_days is not None:
                expires_at = datetime.now(UTC) + timedelta(
                    days=invitation.duration_days
                )

            # Step 4.5: Clean up stale local users (e.g. sync-imported duplicates
            # or users from a previous invitation cycle)
            cleaned = await self.user_service.cleanup_stale_local_users(
                created_external_users,
                current_invitation_id=invitation.id,
            )
            if cleaned > 0:
                log.info(  # pyright: ignore[reportAny]
                    "Cleaned stale local users before creating new records",
                    cleaned_count=cleaned,
                )

            # Step 5: Create local Identity and User records
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
                created_count=len(rollback_data),
            )
            await self._rollback_users(rollback_data)

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
        except RepositoryError as e:
            log.warning(  # pyright: ignore[reportAny]
                "Repository error during redemption, rolling back",
                error=str(e),
                created_count=len(rollback_data),
            )
            await self._rollback_users(rollback_data)
            if isinstance(e.original, IntegrityError):
                error_msg, error_code = self._classify_integrity_error(e.original)
                raise RedemptionError(
                    error_msg,
                    redemption_error_code=error_code,
                ) from e
            raise RedemptionError(
                f"Redemption failed: {e}",
                redemption_error_code="SERVER_ERROR",
            ) from e
        except Exception as e:
            log.error(  # pyright: ignore[reportAny]
                "Unexpected error during redemption, rolling back",
                error=str(e),
                created_count=len(rollback_data),
            )
            await self._rollback_users(rollback_data)
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

        # Step 6: Fire-and-forget background tasks for library sharing
        # and permission application. These are non-critical — the user
        # already has basic access from create_user(). Failures are logged
        # but do not affect the redemption result.
        for server, external_user, library_ids in deferred_tasks:
            task = asyncio.create_task(
                self._apply_library_and_permissions(server, external_user, library_ids),
                name=f"library-sharing-{server.name}-{external_user.external_user_id}",
            )
            # prevent GC of the fire-and-forget task
            task.add_done_callback(_background_tasks.discard)
            _background_tasks.add(task)

        return identity, users

    @staticmethod
    async def _create_user_with_retry(
        *,
        server: MediaServer,
        username: str,
        password: str,
        email: str | None,
        auth_token: str | None,
        library_ids: list[str] | None,
    ) -> tuple[ExternalUser, str, str]:
        """Create a user on a media server with retry for connection errors.

        Only the **connection phase** (``__aenter__`` / ``connect()``) is
        retried with exponential backoff.  Once the connection is
        established, ``create_user`` is called exactly once without retry.

        This prevents orphan accounts: if ``create_user`` succeeds on the
        server but the response is lost (e.g. timeout), retrying would
        create a second account or surface a misleading ``USERNAME_TAKEN``
        error while the original account has no ``external_user_id`` for
        rollback.

        Args:
            server: The target media server.
            username: Username for the new account.
            password: Password for the new account.
            email: Optional email address.
            auth_token: Optional auth token for OAuth flows.
            library_ids: Library IDs to pass to create_user.

        Returns:
            Tuple of (ExternalUser, resolved_url, resolved_api_key).
            The resolved URL and API key come from the client (decrypted /
            env-overridden) and are safe for use in rollback.

        Raises:
            MediaClientError: If ``create_user`` fails.
            ExternalServiceError: If all connection retries are exhausted.
        """

        def _is_connection_error(exc: Exception, /) -> bool:
            """Only retry pre-connection errors (DNS, TCP, TLS).

            ``MediaClientError`` is never retried here because it can only
            originate from ``create_user`` — by that point the server may
            have already processed the request.
            """
            return isinstance(
                exc, (ExternalServiceError, TimeoutError, ConnectionError, OSError)
            )

        retry_policy = RetryPolicy(max_retries=5, backoff_base=1.0, max_delay=30.0)

        def _on_retry(attempt: int, delay: float, exc: Exception) -> None:
            log.warning(  # pyright: ignore[reportAny]
                "Retrying connection to media server",
                server_name=server.name,
                server_type=server.server_type,
                attempt=attempt + 1,
                delay=round(delay, 3),
                error=str(exc),
            )

        # Phase 1: Establish connection with retries for transient failures.
        # A fresh client is created per attempt.
        async def _connect() -> tuple[MediaClient, str, str]:
            client = registry.create_client_for_server(server)
            resolved_url = client.url
            resolved_api_key = client.api_key
            _ = await client.__aenter__()
            return client, resolved_url, resolved_api_key

        client, resolved_url, resolved_api_key = await retry_policy.execute(
            _connect,
            is_retryable=_is_connection_error,
            on_retry=_on_retry,
        )

        # Phase 2: Create user exactly once — no retry.
        # If this fails ambiguously (e.g. timeout after server-side
        # create), the error propagates and rollback handles cleanup
        # for any previously created users on other servers.
        try:
            external_user = await client.create_user(
                username,
                password,
                email=email,
                auth_token=auth_token,
                library_ids=library_ids,
            )
        except BaseException:
            try:
                await client.__aexit__(*sys.exc_info())
            except Exception:
                log.warning(  # pyright: ignore[reportAny]
                    "Client teardown failed after create_user error",
                    server_name=server.name,
                    server_type=server.server_type,
                    username=username,
                )
            raise
        else:
            try:
                await client.__aexit__(None, None, None)
            except Exception:
                log.warning(  # pyright: ignore[reportAny]
                    "Client teardown failed after successful user creation",
                    server_name=server.name,
                    server_type=server.server_type,
                    username=username,
                    external_user_id=external_user.external_user_id,
                )

        return external_user, resolved_url, resolved_api_key

    async def _apply_library_and_permissions(
        self,
        server: MediaServer,
        external_user: ExternalUser,
        library_ids: list[str] | None,
    ) -> None:
        """Apply library access and permissions in the background.

        Creates a fresh client connection and applies library restrictions
        and default permissions. This runs as a fire-and-forget task after
        the redemption response has been sent.

        Errors are logged but never raised — this is best-effort work.
        The user already has basic access from create_user().

        Args:
            server: The target media server.
            external_user: The created external user.
            library_ids: Library IDs to restrict access to, or None for all.
        """
        try:
            client = registry.create_client_for_server(server)
            async with client:
                # Apply library restrictions
                # For "friend" users, sections were already applied at
                # invite time via inviteFriend(sections=...).
                if library_ids and external_user.user_type != "friend":
                    _ = await client.set_library_access(
                        external_user.external_user_id,
                        library_ids,
                    )
                    log.info(  # pyright: ignore[reportAny]
                        "background_library_access_applied",
                        server_name=server.name,
                        library_count=len(library_ids),
                        external_user_id=external_user.external_user_id,
                    )
                elif library_ids and external_user.user_type == "friend":
                    log.info(  # pyright: ignore[reportAny]
                        "background_library_access_skipped_friend",
                        server_name=server.name,
                        library_count=len(library_ids),
                    )

                # Apply default permissions
                permissions = dict(DEFAULT_PERMISSIONS)
                _ = await client.update_permissions(
                    external_user.external_user_id,
                    permissions=permissions,
                )
                log.info(  # pyright: ignore[reportAny]
                    "background_permissions_applied",
                    server_name=server.name,
                    permissions=permissions,
                    external_user_id=external_user.external_user_id,
                )
        except Exception as e:
            log.error(  # pyright: ignore[reportAny]
                "background_library_sharing_failed",
                server_name=server.name,
                external_user_id=external_user.external_user_id,
                error=str(e),
                error_type=type(e).__name__,
            )

    async def _rollback_users(
        self,
        rollback_data: list[tuple[str, str, str, str, str]],
    ) -> None:
        """Delete users created during a failed redemption.

        Best-effort cleanup: logs but does not raise on individual failures.
        This ensures we attempt to clean up all created users even if some
        deletions fail.

        Args:
            rollback_data: List of (server_type, url, api_key, server_name,
                external_user_id) tuples — plain data safe to use after
                SQLAlchemy session rollback.
        """
        for server_type, url, api_key, server_name, external_user_id in rollback_data:
            try:
                client = registry.create_client(
                    server_type, url=url, api_key=api_key, apply_settings=True
                )
                async with client:
                    deleted = await client.delete_user(external_user_id)
                    if deleted:
                        log.info(  # pyright: ignore[reportAny]
                            "Rolled back user creation",
                            server_name=server_name,
                            external_user_id=external_user_id,
                        )
                    else:
                        log.warning(  # pyright: ignore[reportAny]
                            "User not found during rollback",
                            server_name=server_name,
                            external_user_id=external_user_id,
                        )
            except Exception as e:
                # Log but don't raise - best effort cleanup
                log.error(  # pyright: ignore[reportAny]
                    "Failed to rollback user creation",
                    server_name=server_name,
                    external_user_id=external_user_id,
                    error=str(e),
                )

    @staticmethod
    def _classify_integrity_error(exc: IntegrityError) -> tuple[str, str]:
        """Classify an IntegrityError by inspecting the constraint name.

        Disambiguates between different unique constraint violations on the
        User model so the correct error code is returned to the client.

        Args:
            exc: The SQLAlchemy IntegrityError to classify.

        Returns:
            A (message, error_code) tuple.
        """
        detail = str(exc).lower()
        if "uq_users_username_server" in detail:
            return (
                "Username is already taken on this media server",
                "USERNAME_TAKEN",
            )
        if "uq_users_external_user_server" in detail:
            return (
                "This account is already linked to this media server",
                "ACCOUNT_ALREADY_LINKED",
            )
        return (
            "This account is already linked to this media server",
            "ACCOUNT_ALREADY_LINKED",
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

    def _failure_error_code(self, failure: InvitationValidationFailure | None) -> str:
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
