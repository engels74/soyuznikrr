"""Plex media server client.

Provides the PlexClient class that implements the MediaClient protocol
for communicating with Plex media servers.

Uses python-plexapi (PlexAPI v4.18+) for server communication.
PlexAPI is synchronous, so operations use asyncio.to_thread() to avoid
blocking the event loop.

Uses Python 3.14 features:
- Deferred annotations (no forward reference quotes needed)
- Self type for proper return type in context manager
"""

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING, Self, final

import structlog

if TYPE_CHECKING:
    from plexapi.myplex import MyPlexAccount
    from plexapi.server import PlexServer

from zondarr.core.exceptions import ExternalServiceError
from zondarr.media.exceptions import MediaClientError
from zondarr.media.types import Capability, ExternalUser, LibraryInfo, ServerInfo

log: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]


# Error code constants for Plex API errors
# These map Plex-specific error patterns to standardized error codes
@final
class PlexErrorCode:
    """Error codes for Plex API operations.

    These codes provide standardized error identification across
    all PlexClient operations, enabling consistent error handling
    and logging throughout the application.
    """

    # User-related errors
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"
    USERNAME_TAKEN = "USERNAME_TAKEN"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    EMAIL_REQUIRED = "EMAIL_REQUIRED"

    # Connection errors
    CONNECTION_ERROR = "CONNECTION_ERROR"
    INVALID_TOKEN = "INVALID_TOKEN"  # noqa: S105
    SERVER_UNREACHABLE = "SERVER_UNREACHABLE"
    TIMEOUT = "TIMEOUT"

    # Client state errors
    CLIENT_NOT_INITIALIZED = "CLIENT_NOT_INITIALIZED"

    # API errors
    API_ERROR = "API_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    PERMISSION_DENIED = "PERMISSION_DENIED"

    # Library errors
    LIBRARY_NOT_FOUND = "LIBRARY_NOT_FOUND"


def _map_plex_error_to_code(error: Exception) -> str:
    """Map a Plex API exception to a standardized error code.

    Analyzes the exception message to determine the appropriate
    error code for consistent error handling.

    Args:
        error: The exception raised by the Plex API.

    Returns:
        A standardized error code string.
    """
    error_str = str(error).lower()

    # User-related errors
    if "already" in error_str and ("shared" in error_str or "friend" in error_str):
        return PlexErrorCode.USER_ALREADY_EXISTS
    if "taken" in error_str or ("exists" in error_str and "user" in error_str):
        return PlexErrorCode.USERNAME_TAKEN
    if "not found" in error_str or "does not exist" in error_str:
        return PlexErrorCode.USER_NOT_FOUND

    # Connection errors
    if "unauthorized" in error_str or "401" in error_str:
        return PlexErrorCode.INVALID_TOKEN
    if "timeout" in error_str or "timed out" in error_str:
        return PlexErrorCode.TIMEOUT
    if (
        "connection" in error_str
        or "unreachable" in error_str
        or "refused" in error_str
    ):
        return PlexErrorCode.CONNECTION_ERROR

    # Rate limiting
    if "rate" in error_str and "limit" in error_str:
        return PlexErrorCode.RATE_LIMITED

    # Permission errors
    if "permission" in error_str or "forbidden" in error_str or "403" in error_str:
        return PlexErrorCode.PERMISSION_DENIED

    # Default to generic API error
    return PlexErrorCode.API_ERROR


def _is_external_service_error(error: Exception) -> bool:
    """Determine if an error is an external service error.

    External service errors are connection failures, timeouts, and
    server-side API errors that indicate the Plex server is unavailable
    or malfunctioning.

    Args:
        error: The exception to check.

    Returns:
        True if the error is an external service error, False otherwise.
    """
    error_code = _map_plex_error_to_code(error)
    return error_code in {
        PlexErrorCode.CONNECTION_ERROR,
        PlexErrorCode.TIMEOUT,
        PlexErrorCode.SERVER_UNREACHABLE,
        PlexErrorCode.RATE_LIMITED,
        PlexErrorCode.API_ERROR,
        PlexErrorCode.INVALID_TOKEN,
    }


def _create_media_client_error(
    message: str,
    *,
    operation: str,
    server_url: str,
    cause: str,
    error_code: str | None = None,
    original_error: Exception | None = None,
) -> MediaClientError:
    """Create a MediaClientError with consistent structure.

    Ensures all MediaClientError instances have the required fields:
    operation, server_url, and cause.

    Args:
        message: Human-readable error description.
        operation: The operation that failed (e.g., "create_user").
        server_url: The Plex server URL.
        cause: Description of what caused the failure.
        error_code: Optional specific error code.
        original_error: Optional original exception for error code mapping.

    Returns:
        A properly structured MediaClientError.
    """
    # Determine error code from original error if not provided
    if error_code is None and original_error is not None:
        error_code = _map_plex_error_to_code(original_error)

    return MediaClientError(
        message,
        operation=operation,
        server_url=server_url,
        cause=cause,
        error_code=error_code,
    )


def _create_external_service_error(
    message: str,
    *,
    server_url: str,
    original_error: Exception | None = None,
) -> ExternalServiceError:
    """Create an ExternalServiceError for Plex server failures.

    Used when the Plex server is unreachable, times out, or returns
    an API error indicating the service is unavailable.

    Args:
        message: Human-readable error description.
        server_url: The Plex server URL (used as service_name).
        original_error: The original exception that caused this error.

    Returns:
        An ExternalServiceError with the server URL as service name.
    """
    return ExternalServiceError(
        f"Plex ({server_url})",
        message,
        original=original_error,
    )


class PlexClient:
    """Plex media server client.

    Implements the MediaClient protocol for Plex servers.
    Uses python-plexapi for server communication.

    PlexAPI is synchronous, so all operations use asyncio.to_thread()
    to run without blocking the event loop.

    Attributes:
        url: The Plex server URL.
        api_key: The API key (X-Plex-Token) for authentication.
    """

    url: str
    api_key: str
    _server: PlexServer | None
    _account: MyPlexAccount | None

    def __init__(self, *, url: str, api_key: str) -> None:
        """Initialize a PlexClient.

        Args:
            url: The Plex server URL (keyword-only).
            api_key: The API key (X-Plex-Token) for authentication (keyword-only).
        """
        self.url = url
        self.api_key = api_key
        self._server = None
        self._account = None

    @classmethod
    def capabilities(cls) -> set[Capability]:
        """Return the set of capabilities this client supports.

        Plex supports user creation, deletion, and library access
        configuration. Note that Plex does not support enable/disable
        user functionality directly.

        Returns:
            A set of Capability enum values indicating supported features.
        """
        return {
            Capability.CREATE_USER,
            Capability.DELETE_USER,
            Capability.LIBRARY_ACCESS,
            Capability.REMOVE_SHARED_ACCESS,
        }

    @classmethod
    def supported_permissions(cls) -> frozenset[str]:
        return frozenset({"can_download"})

    async def __aenter__(self) -> Self:
        """Enter async context, establishing connection.

        Initializes the PlexServer and MyPlexAccount connections using
        asyncio.to_thread() since python-plexapi is synchronous.

        Returns:
            Self for use in async with statements.

        Raises:
            ExternalServiceError: If connection to the Plex server fails.
        """

        from plexapi.server import PlexServer

        def _connect() -> tuple[PlexServer, MyPlexAccount]:
            server = PlexServer(self.url, self.api_key)
            # plexapi lacks type stubs, myPlexAccount returns MyPlexAccount
            account: MyPlexAccount = server.myPlexAccount()  # pyright: ignore[reportUnknownVariableType]
            return server, account  # pyright: ignore[reportUnknownVariableType]

        log.info("plex_client_connecting", url=self.url)
        try:
            self._server, self._account = await asyncio.to_thread(_connect)
        except Exception as exc:
            log.error(
                "plex_client_connection_failed",
                url=self.url,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise _create_external_service_error(
                f"Failed to connect to Plex server: {exc}",
                server_url=self.url,
                original_error=exc,
            ) from exc
        log.info("plex_client_connected", url=self.url)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context, cleaning up resources.

        Releases the PlexServer and MyPlexAccount instances.

        Args:
            exc_type: The exception type if an exception was raised, None otherwise.
            exc_val: The exception instance if an exception was raised, None otherwise.
            exc_tb: The traceback if an exception was raised, None otherwise.
        """
        log.info("plex_client_disconnecting", url=self.url)
        self._server = None
        self._account = None

    async def test_connection(self) -> bool:
        """Test connectivity to the Plex server.

        Verifies that the server is reachable and the API key is valid
        by querying server information via python-plexapi.

        Returns:
            True if the connection is successful and authenticated,
            False otherwise. Never raises exceptions for connection failures.
        """
        if self._server is None:
            return False

        try:

            def _query_server_info() -> str:
                # Access server friendlyName to verify connectivity
                # This requires a valid connection and token
                assert self._server is not None  # noqa: S101
                # plexapi lacks type stubs, friendlyName is str
                name: str = self._server.friendlyName  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                return name  # pyright: ignore[reportUnknownVariableType]

            server_name = await asyncio.to_thread(_query_server_info)
            log.info("plex_connection_test_success", url=self.url, server=server_name)
            return True
        except Exception as exc:
            log.warning("plex_connection_test_failed", url=self.url, error=str(exc))
            return False

    async def get_server_info(self) -> ServerInfo:
        """Return server name and version metadata.

        Accesses plexapi's friendlyName and version attributes.
        Uses asyncio.to_thread() since plexapi is synchronous.

        Returns:
            A ServerInfo object with the server's name and version.

        Raises:
            MediaClientError: If the client is not initialized.
        """
        if self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="get_server_info",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        def _get_info() -> ServerInfo:
            assert self._server is not None  # noqa: S101
            name: str = self._server.friendlyName  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            version: str = self._server.version  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            return ServerInfo(server_name=name, version=version)  # pyright: ignore[reportUnknownArgumentType]

        return await asyncio.to_thread(_get_info)

    async def get_libraries(self) -> Sequence[LibraryInfo]:
        """Retrieve all libraries (sections) from the Plex server.

        Fetches the list of content libraries (movies, TV shows, music, etc.)
        available on the server via python-plexapi's library.sections().

        Maps Plex section attributes to LibraryInfo:
        - key -> external_id
        - title -> name
        - type -> library_type (movie, show, artist, photo, etc.)

        Returns:
            A sequence of LibraryInfo objects describing each library.

        Raises:
            MediaClientError: If the client is not initialized (use async context manager).
            MediaClientError: If library retrieval fails due to connection or API errors.
        """
        if self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="get_libraries",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _get_sections() -> list[LibraryInfo]:
                assert self._server is not None  # noqa: S101
                # plexapi lacks type stubs, sections() returns list of LibrarySection
                sections = self._server.library.sections()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                return [
                    LibraryInfo(
                        external_id=str(section.key),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                        name=section.title,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                        library_type=section.type,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                    )
                    for section in sections  # pyright: ignore[reportUnknownVariableType]
                ]

            libraries = await asyncio.to_thread(_get_sections)
            log.info(
                "plex_libraries_retrieved",
                url=self.url,
                count=len(libraries),
            )
            return libraries

        except MediaClientError:
            raise
        except Exception as exc:
            log.error(
                "plex_get_libraries_failed",
                url=self.url,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to retrieve libraries from Plex server: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
            raise _create_media_client_error(
                f"Failed to retrieve libraries from Plex server: {exc}",
                operation="get_libraries",
                server_url=self.url,
                cause=str(exc),
                original_error=exc,
            ) from exc

    async def _share_library_direct(self, email: str, auth_token: str) -> ExternalUser:
        """Share server libraries directly using the user's Plex auth token.

        Uses the shared_servers API with the user's numeric Plex ID (obtained
        from their OAuth token) to grant library access directly. This avoids
        creating a friend relationship and requires no manual acceptance.

        Args:
            email: The email address of the Plex user.
            auth_token: The user's Plex OAuth auth token.

        Returns:
            An ExternalUser with the numeric Plex user ID and username.

        Raises:
            MediaClientError: If direct sharing fails.
            ExternalServiceError: If the Plex API is unreachable or returns a server error.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="share_library_direct",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:
            from plexapi.myplex import MyPlexAccount

            def _share_direct() -> ExternalUser:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101

                # Get the user's Plex account info from their auth token
                user_account: MyPlexAccount = MyPlexAccount(token=auth_token)
                plex_user_id: str = str(user_account.id)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                username: str = user_account.username or email  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                # Get the server's machine identifier
                machine_id: str = self._server.machineIdentifier  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                # Use the admin account's shared_servers API to grant access
                # This mirrors plexapi's updateFriend() when user has no existing access:
                # POST to shared_servers with invited_id (numeric Plex user ID)
                base_headers: dict[str, str] = self._account._headers()  # pyright: ignore[reportUnknownMemberType, reportAssignmentType, reportPrivateUsage, reportUnknownVariableType]
                headers: dict[str, str] = {
                    **base_headers,
                    "Content-Type": "application/json",
                }
                sharing_url = f"https://plex.tv/api/servers/{machine_id}/shared_servers"
                # Match plexapi's JSON body structure (nested dicts, not bracket-notation)
                # Empty library_section_ids list = share all libraries (same as plexapi default)
                params: dict[str, object] = {
                    "server_id": machine_id,
                    "shared_server": {
                        "library_section_ids": [],
                        "invited_id": int(plex_user_id),
                    },
                    "sharing_settings": {
                        "filterMovies": "",
                        "filterTelevision": "",
                        "filterMusic": "",
                    },
                }
                # Use the admin account's session to make the request (JSON body)
                resp = self._account._session.post(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportPrivateUsage]
                    sharing_url,
                    headers=headers,
                    json=params,
                    timeout=30,
                )
                _ = resp.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                return ExternalUser(
                    external_user_id=plex_user_id,
                    username=username,  # pyright: ignore[reportUnknownArgumentType]
                    email=email,
                    user_type="shared",
                )

            result = await asyncio.to_thread(_share_direct)

            log.info(
                "plex_library_shared_direct",
                url=self.url,
                email=email,
                user_id=result.external_user_id,
                username=result.username,
            )

            # Best-effort cleanup: cancel any stale pending invites for this user
            _ = await self._cancel_pending_invites_for_user(email)

            return result

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)
            log.error(
                "plex_direct_share_failed",
                url=self.url,
                email=email,
                error=str(exc),
                error_type=type(exc).__name__,
                error_code=error_code,
            )
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to share library directly: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
            raise _create_media_client_error(
                f"Failed to share library directly: {exc}",
                operation="share_library_direct",
                server_url=self.url,
                cause=str(exc),
                error_code=error_code,
            ) from exc

    async def _cancel_pending_invites_for_user(self, email: str) -> int:
        """Cancel any pending sent invites for a user on our server.

        Best-effort cleanup: uses the admin's account to find and cancel
        any pending invitations sent to the given email for this server.
        This prevents stale pending invites from lingering after direct
        library sharing has already granted access.

        Args:
            email: The email address to match against pending invites.

        Returns:
            The number of invites cancelled. Returns 0 on any error.
        """
        if self._account is None or self._server is None:
            return 0

        try:

            def _cancel_invites() -> int:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101

                machine_id: str = self._server.machineIdentifier  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                # Get pending invites sent by the admin
                pending = self._account.pendingInvites(  # pyright: ignore[reportUnknownVariableType]
                    includeSent=True,
                    includeReceived=False,
                )

                cancelled = 0
                for invite in pending:  # pyright: ignore[reportUnknownVariableType]
                    invite_email: str = getattr(invite, "email", "") or ""  # pyright: ignore[reportUnknownArgumentType]
                    if invite_email.lower() != email.lower():
                        continue

                    # Check if this invite is for our server
                    invite_servers: list[object] = getattr(invite, "servers", []) or []  # pyright: ignore[reportUnknownArgumentType]
                    for server_share in invite_servers:
                        share_machine_id: str = getattr(
                            server_share, "machineIdentifier", ""
                        )
                        if share_machine_id == machine_id:
                            _ = self._account.cancelInvite(invite)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
                            cancelled += 1
                            break

                return cancelled

            count = await asyncio.to_thread(_cancel_invites)

            if count > 0:
                log.info(
                    "plex_pending_invites_cancelled",
                    url=self.url,
                    email=email,
                    count=count,
                )

            return count

        except Exception as exc:
            log.warning(
                "plex_cancel_pending_invites_failed",
                url=self.url,
                email=email,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return 0

    async def _invite_friend(self, email: str) -> ExternalUser:
        """Invite a Friend user via inviteFriend (legacy fallback).

        Sends an invitation to an existing Plex.tv account. The user must
        have an existing Plex account or create one to accept the invitation.

        Note: This creates a pending friend invitation that requires manual
        acceptance. Prefer _share_library_direct when an auth_token is available.

        Args:
            email: The email address of the Plex.tv account to invite.

        Returns:
            An ExternalUser with the email as external_user_id and username.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If the user is already a Friend (USER_ALREADY_EXISTS).
            MediaClientError: If the invitation fails for other reasons.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="create_friend",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _invite() -> object:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101
                # plexapi lacks type stubs, inviteFriend returns MyPlexUser
                # We pass the server to share with the friend
                return self._account.inviteFriend(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                    user=email,
                    server=self._server,
                )

            user = await asyncio.to_thread(_invite)
            # plexapi MyPlexUser has id and username attributes
            user_id: str = str(getattr(user, "id", email))
            username: str = getattr(user, "username", None) or email

            log.info(
                "plex_friend_created",
                url=self.url,
                email=email,
                user_id=user_id,
            )

            return ExternalUser(
                external_user_id=user_id,
                username=username,
                email=email,
                user_type="friend",
            )

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)

            # Log the error with appropriate level
            if error_code == PlexErrorCode.USER_ALREADY_EXISTS:
                log.warning(
                    "plex_friend_already_exists",
                    url=self.url,
                    email=email,
                    error=str(exc),
                )
            else:
                log.error(
                    "plex_create_friend_failed",
                    url=self.url,
                    email=email,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    error_code=error_code,
                )

            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to invite Friend: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc

            raise _create_media_client_error(
                f"Failed to invite Friend: {exc}"
                if error_code != PlexErrorCode.USER_ALREADY_EXISTS
                else f"User with email {email} is already a Friend",
                operation="create_friend",
                server_url=self.url,
                cause=str(exc),
                error_code=error_code,
            ) from exc

    async def _create_friend(
        self, email: str, *, auth_token: str | None = None
    ) -> ExternalUser:
        """Create a Friend/shared user on the Plex server.

        If auth_token is provided, uses direct library sharing via the
        shared_servers API (no friend relationship, immediate access).
        Otherwise falls back to inviteFriend (creates pending invitation).

        Args:
            email: The email address of the Plex.tv account.
            auth_token: Optional OAuth auth token from the user.

        Returns:
            An ExternalUser with the user's details.

        Raises:
            MediaClientError: If user creation fails.
        """
        if auth_token:
            return await self._share_library_direct(email, auth_token)
        return await self._invite_friend(email)

    async def _create_home_user(self, username: str) -> ExternalUser:
        """Create a Home User via createHomeUser.

        Creates a managed user within the Plex Home. Home Users do not
        require an external Plex.tv account.

        Args:
            username: The username for the new Home User.

        Returns:
            An ExternalUser with the Plex user ID as external_user_id.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If the username is already taken (USERNAME_TAKEN).
            MediaClientError: If Home User creation fails for other reasons.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="create_home_user",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _create() -> object:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101
                # plexapi lacks type stubs, createHomeUser returns MyPlexUser
                return self._account.createHomeUser(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                    user=username,
                    server=self._server,
                )

            user = await asyncio.to_thread(_create)
            # plexapi MyPlexUser has id attribute
            user_id: str = str(getattr(user, "id", ""))

            log.info(
                "plex_home_user_created",
                url=self.url,
                username=username,
                user_id=user_id,
            )

            return ExternalUser(
                external_user_id=user_id,
                username=username,
                email=None,
                user_type="home",
            )

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)

            # Log the error with appropriate level
            if error_code == PlexErrorCode.USERNAME_TAKEN:
                log.warning(
                    "plex_home_user_username_taken",
                    url=self.url,
                    username=username,
                    error=str(exc),
                )
            else:
                log.error(
                    "plex_create_home_user_failed",
                    url=self.url,
                    username=username,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    error_code=error_code,
                )

            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to create Home User: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc

            raise _create_media_client_error(
                f"Failed to create Home User: {exc}"
                if error_code != PlexErrorCode.USERNAME_TAKEN
                else f"Username '{username}' is already taken",
                operation="create_home_user",
                server_url=self.url,
                cause=str(exc),
                error_code=error_code,
            ) from exc

    async def create_user(
        self,
        username: str,
        password: str,
        /,
        *,
        email: str | None = None,
        auth_token: str | None = None,
    ) -> ExternalUser:
        """Create a new user on the Plex server.

        Uses email presence to determine the user type:
        - If email is provided, creates a Friend/shared user via Plex.tv.
          If auth_token is also provided, uses direct library sharing
          (no friend relationship, immediate access).
        - If no email, creates a managed Home User within the Plex Home.

        Note: The password parameter is ignored for Plex since authentication
        is handled through Plex.tv accounts or managed Home Users.

        Args:
            username: The username for the new account (positional-only).
            password: Ignored for Plex (positional-only).
            email: Email address (keyword-only). If provided, creates a Friend
                or shared user; otherwise creates a Home User.
            auth_token: Optional OAuth auth token from the user (keyword-only).
                When provided with email, enables direct library sharing.

        Returns:
            An ExternalUser object with the created user's details.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If the user already exists.
            MediaClientError: If user creation fails for other reasons.
        """
        _ = password  # Explicitly ignore password parameter

        if email is not None:
            return await self._create_friend(email, auth_token=auth_token)

        # No email provided - create as Home User
        return await self._create_home_user(username)

    def _remove_shared_server_access_sync(self, external_user_id: str) -> bool:
        """Remove shared server access for a user (synchronous, call from thread).

        Queries the shared_servers API for the server's machine identifier,
        finds a shared server entry matching the user ID, and DELETEs it.

        Args:
            external_user_id: The user's numeric Plex user ID.

        Returns:
            True if a shared server entry was found and removed, False if not found.
        """
        assert self._account is not None  # noqa: S101
        assert self._server is not None  # noqa: S101

        machine_id: str = self._server.machineIdentifier  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        base_headers: dict[str, str] = self._account._headers()  # pyright: ignore[reportUnknownMemberType, reportAssignmentType, reportPrivateUsage, reportUnknownVariableType]
        headers: dict[str, str] = {
            **base_headers,
            "Accept": "application/json",
        }

        # GET shared servers for this machine
        sharing_url = f"https://plex.tv/api/servers/{machine_id}/shared_servers"
        resp = self._account._session.get(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportPrivateUsage]
            sharing_url,
            headers=headers,
            timeout=30,
        )
        _ = resp.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

        # Parse JSON to find matching userID
        # Friend-only users may return an empty body (no shared server entries)
        try:
            data: dict[str, object] = resp.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        except (ValueError, TypeError):
            # Empty or non-JSON response — no shared server entries exist
            return False
        shared_servers: list[dict[str, object]] = []

        # Response may be {"SharedServer": [...]} or similar structure
        if isinstance(data, dict):
            for key in ("SharedServer", "shared_servers"):
                val = data.get(key)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                if isinstance(val, list):
                    shared_servers = val  # pyright: ignore[reportUnknownVariableType]
                    break

        for entry in shared_servers:
            entry_user_id = str(entry.get("userID", ""))
            if entry_user_id == external_user_id:
                shared_server_id = entry.get("id", "")
                delete_url = f"https://plex.tv/api/servers/{machine_id}/shared_servers/{shared_server_id}"
                del_resp = self._account._session.delete(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportPrivateUsage]
                    delete_url,
                    headers=headers,
                    timeout=30,
                )
                _ = del_resp.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                return True

        return False

    async def delete_user(self, external_user_id: str, /) -> bool:
        """Delete a user from the Plex server.

        Removes the user account identified by the external user ID.
        Attempts to find the user among Friends/Home Users first, then
        checks shared_servers for direct-share users. Returns True if
        either path succeeds.

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).

        Returns:
            True if the user was successfully deleted, False if the user
            was not found.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If deletion fails for reasons other than user not found.
        """
        if self._account is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="delete_user",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _delete() -> bool:
                assert self._account is not None  # noqa: S101
                # plexapi lacks type stubs, users() returns list of MyPlexUser
                users = self._account.users()  # pyright: ignore[reportUnknownVariableType]

                # Path 1: Find the user among Friends/Home Users
                friend_deleted = False
                target_user: object | None = None
                for user in users:  # pyright: ignore[reportUnknownVariableType]
                    user_id: str = str(getattr(user, "id", ""))  # pyright: ignore[reportUnknownArgumentType]
                    if user_id == external_user_id:
                        target_user = user  # pyright: ignore[reportUnknownVariableType]
                        break

                if target_user is not None:
                    is_home_user: bool = getattr(target_user, "home", False)  # pyright: ignore[reportUnknownArgumentType]

                    if is_home_user:
                        self._account.removeHomeUser(target_user)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportUnusedCallResult]
                        friend_deleted = True
                    else:
                        # For friends: remove via v2 friends API
                        # NOTE: plexapi's removeFriend() uses /api/v2/sharings/
                        # which only removes library sharing, NOT the friend
                        # relationship. The correct endpoint is /api/v2/friends/.
                        friends_url = f"https://plex.tv/api/v2/friends/{external_user_id}"
                        base_headers: dict[str, str] = self._account._headers()  # pyright: ignore[reportUnknownMemberType, reportAssignmentType, reportPrivateUsage, reportUnknownVariableType]
                        del_resp = self._account._session.delete(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportPrivateUsage]
                            friends_url,
                            headers=base_headers,
                            timeout=30,
                        )
                        _ = del_resp.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                        log.info(
                            "plex_friend_removed_via_v2_friends_api",
                            url=self.url,
                            user_id=external_user_id,
                        )
                        friend_deleted = True

                        # Best-effort verification
                        try:
                            verify_users = self._account.users()  # pyright: ignore[reportUnknownVariableType]
                            still_present = any(
                                str(getattr(u, "id", "")) == external_user_id  # pyright: ignore[reportUnknownArgumentType]
                                for u in verify_users  # pyright: ignore[reportUnknownVariableType]
                            )
                            if still_present:
                                log.warning(
                                    "plex_friend_may_persist_in_api_cache",
                                    url=self.url,
                                    user_id=external_user_id,
                                )
                        except Exception as verify_exc:
                            log.warning(
                                "plex_post_remove_verification_failed",
                                url=self.url,
                                user_id=external_user_id,
                                error=str(verify_exc),
                            )

                # Path 2: Remove shared server access (only for users with server access)
                shared_deleted = False
                if self._server is not None:
                    # Only attempt shared server removal when the user has server access
                    has_shared_access = target_user is not None and bool(
                        getattr(target_user, "servers", None)  # pyright: ignore[reportUnknownArgumentType]
                    )
                    if has_shared_access or target_user is None:
                        try:
                            shared_deleted = self._remove_shared_server_access_sync(
                                external_user_id
                            )
                        except Exception as shared_exc:
                            if friend_deleted:
                                log.warning(
                                    "plex_shared_server_cleanup_failed",
                                    url=self.url,
                                    user_id=external_user_id,
                                    error=str(shared_exc),
                                )
                            else:
                                raise

                return friend_deleted or shared_deleted

            deleted = await asyncio.to_thread(_delete)

            if deleted:
                log.info(
                    "plex_user_deleted",
                    url=self.url,
                    user_id=external_user_id,
                )
            else:
                log.warning(
                    "plex_user_not_found",
                    url=self.url,
                    user_id=external_user_id,
                )

            return deleted

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)

            # Check for not found error - return False instead of raising
            if error_code == PlexErrorCode.USER_NOT_FOUND:
                log.warning(
                    "plex_user_not_found",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                )
                return False

            log.error(
                "plex_delete_user_failed",
                url=self.url,
                user_id=external_user_id,
                error=str(exc),
                error_type=type(exc).__name__,
                error_code=error_code,
            )
            # Any non-"not found" failure during deletion is an external
            # service error — the Plex API call itself failed.
            raise _create_external_service_error(
                f"Failed to delete user: {exc}",
                server_url=self.url,
                original_error=exc,
            ) from exc

    async def remove_shared_access(self, external_user_id: str, /) -> bool:
        """Remove shared library access without removing the friend relationship.

        Calls _remove_shared_server_access_sync to delete the shared server
        entry for this user. The friend relationship is left intact.

        Args:
            external_user_id: The user's numeric Plex user ID (positional-only).

        Returns:
            True if shared access was found and removed, False otherwise.

        Raises:
            MediaClientError: If the client is not initialized or operation fails.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="remove_shared_access",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:
            removed = await asyncio.to_thread(
                self._remove_shared_server_access_sync, external_user_id
            )
            if removed:
                log.info(
                    "plex_shared_access_removed",
                    url=self.url,
                    user_id=external_user_id,
                )
            else:
                log.info(
                    "plex_no_shared_access_found",
                    url=self.url,
                    user_id=external_user_id,
                )
            return removed
        except MediaClientError:
            raise
        except Exception as exc:
            raise _create_external_service_error(
                f"Failed to remove shared access: {exc}",
                server_url=self.url,
                original_error=exc,
            ) from exc

    async def set_user_enabled(
        self,
        external_user_id: str,
        /,
        *,
        enabled: bool,
    ) -> bool:
        """Enable or disable a user on the Plex server.

        Note: Plex does not support enable/disable functionality.
        This method always returns False and logs a warning.

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).
            enabled: Whether the user should be enabled (keyword-only).

        Returns:
            False always - Plex does not support this operation.
        """
        log.warning(
            "plex_set_user_enabled_unsupported",
            url=self.url,
            user_id=external_user_id,
            enabled=enabled,
            message="Plex does not support enable/disable user functionality",
        )
        return False

    async def set_library_access(
        self,
        external_user_id: str,
        library_ids: Sequence[str],
        /,
    ) -> bool:
        """Set which libraries a user can access on the Plex server.

        Configures the user's library permissions via updateFriend()
        for Friends or appropriate method for Home Users.

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).
            library_ids: Sequence of library section keys to grant access to
                (positional-only). An empty sequence revokes all access.

        Returns:
            True if permissions were successfully updated, False if the user
            was not found.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If the library access update fails for reasons
                other than user not found.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="set_library_access",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _set_access() -> bool:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101

                # Get all users to find the target
                users = self._account.users()  # pyright: ignore[reportUnknownVariableType]

                # Find the user by ID
                target_user: object | None = None
                for user in users:  # pyright: ignore[reportUnknownVariableType]
                    user_id: str = str(getattr(user, "id", ""))  # pyright: ignore[reportUnknownArgumentType]
                    if user_id == external_user_id:
                        target_user = user  # pyright: ignore[reportUnknownVariableType]
                        break

                if target_user is None:
                    return False

                # Get library sections to grant access to
                # Empty list means revoke all access
                sections: list[object] = []
                if library_ids:
                    for lib_id in library_ids:
                        try:
                            section = self._server.library.sectionByID(int(lib_id))  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                            sections.append(section)  # pyright: ignore[reportUnknownArgumentType]
                        except Exception:
                            # Skip invalid library IDs
                            log.warning(
                                "plex_invalid_library_id",
                                url=self.url,
                                library_id=lib_id,
                            )

                # Determine if this is a Home User or Friend
                is_home_user: bool = getattr(target_user, "home", False)  # pyright: ignore[reportUnknownArgumentType]

                if is_home_user:
                    # For Home Users, use updateFriend with sections
                    # Note: Plex API uses same method for both user types
                    self._account.updateFriend(  # pyright: ignore[reportUnknownMemberType, reportUnusedCallResult]
                        user=target_user,  # pyright: ignore[reportUnknownArgumentType]
                        server=self._server,
                        sections=sections,
                    )
                else:
                    # For Friends, use updateFriend with sections
                    self._account.updateFriend(  # pyright: ignore[reportUnknownMemberType, reportUnusedCallResult]
                        user=target_user,  # pyright: ignore[reportUnknownArgumentType]
                        server=self._server,
                        sections=sections,
                    )

                return True

            updated = await asyncio.to_thread(_set_access)

            if updated:
                log.info(
                    "plex_library_access_updated",
                    url=self.url,
                    user_id=external_user_id,
                    library_count=len(library_ids),
                )
            else:
                log.warning(
                    "plex_user_not_found_for_library_access",
                    url=self.url,
                    user_id=external_user_id,
                )

            return updated

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)

            # Check for not found error - return False instead of raising
            if error_code == PlexErrorCode.USER_NOT_FOUND:
                log.warning(
                    "plex_user_not_found_for_library_access",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                )
                return False

            log.error(
                "plex_set_library_access_failed",
                url=self.url,
                user_id=external_user_id,
                library_count=len(library_ids),
                error=str(exc),
                error_type=type(exc).__name__,
                error_code=error_code,
            )
            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to set library access: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
            raise _create_media_client_error(
                f"Failed to set library access: {exc}",
                operation="set_library_access",
                server_url=self.url,
                cause=str(exc),
                error_code=error_code,
            ) from exc

    async def update_permissions(
        self,
        external_user_id: str,
        /,
        *,
        permissions: dict[str, bool],
    ) -> bool:
        """Update user permissions on the Plex server.

        Maps universal permissions to Plex-specific settings where applicable.
        Currently supports can_download -> allowSync mapping.

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).
            permissions: Dictionary mapping universal permission names to boolean
                values (keyword-only). Only provided keys are updated.

        Returns:
            True if permissions were successfully updated, False if the user
            was not found.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If the permission update fails for reasons
                other than user not found.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="update_permissions",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _update_permissions() -> bool:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101

                # Get all users to find the target
                users = self._account.users()  # pyright: ignore[reportUnknownVariableType]

                # Find the user by ID
                target_user: object | None = None
                for user in users:  # pyright: ignore[reportUnknownVariableType]
                    user_id: str = str(getattr(user, "id", ""))  # pyright: ignore[reportUnknownArgumentType]
                    if user_id == external_user_id:
                        target_user = user  # pyright: ignore[reportUnknownVariableType]
                        break

                if target_user is None:
                    return False

                # Map universal permissions to Plex-specific settings
                # can_download -> allowSync
                allow_sync: bool | None = permissions.get("can_download")

                # Update the user's permissions via updateFriend
                # Note: Plex uses allowSync for download permission
                if allow_sync is not None:
                    self._account.updateFriend(  # pyright: ignore[reportUnknownMemberType, reportUnusedCallResult]
                        user=target_user,  # pyright: ignore[reportUnknownArgumentType]
                        server=self._server,
                        allowSync=allow_sync,
                    )

                return True

            updated = await asyncio.to_thread(_update_permissions)

            if updated:
                log.info(
                    "plex_permissions_updated",
                    url=self.url,
                    user_id=external_user_id,
                    permissions=list(permissions.keys()),
                )
            else:
                log.warning(
                    "plex_user_not_found_for_permissions",
                    url=self.url,
                    user_id=external_user_id,
                )

            return updated

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)

            # Check for not found error - return False instead of raising
            if error_code == PlexErrorCode.USER_NOT_FOUND:
                log.warning(
                    "plex_user_not_found_for_permissions",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                )
                return False

            log.error(
                "plex_update_permissions_failed",
                url=self.url,
                user_id=external_user_id,
                permissions=list(permissions.keys()),
                error=str(exc),
                error_type=type(exc).__name__,
                error_code=error_code,
            )
            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to update permissions: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
            raise _create_media_client_error(
                f"Failed to update permissions: {exc}",
                operation="update_permissions",
                server_url=self.url,
                cause=str(exc),
                error_code=error_code,
            ) from exc

    async def list_users(self) -> Sequence[ExternalUser]:
        """List all users with access to the Plex server.

        Retrieves all Friends and Home Users from the Plex account
        and maps them to ExternalUser structs.

        Returns:
            A sequence of ExternalUser objects with external_user_id,
            username, email (if available), and user_type (home, shared,
            or friend).

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If user listing fails due to connection or API errors.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="list_users",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _list_users() -> list[ExternalUser]:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101

                machine_id: str = self._server.machineIdentifier  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                # Get all users (Friends and Home Users)
                users = self._account.users()  # pyright: ignore[reportUnknownVariableType]

                result: list[ExternalUser] = []
                for user in users:  # pyright: ignore[reportUnknownVariableType]
                    user_id: str = str(getattr(user, "id", ""))  # pyright: ignore[reportUnknownArgumentType]
                    username: str = getattr(user, "username", "") or ""  # pyright: ignore[reportUnknownArgumentType]
                    email: str | None = getattr(user, "email", None)  # pyright: ignore[reportUnknownArgumentType]

                    if not user_id:
                        continue

                    # Classify user type based on home status and server shares
                    is_home: bool = getattr(user, "home", False)  # pyright: ignore[reportUnknownArgumentType]
                    if is_home:
                        user_type = "home"
                    else:
                        user_servers = getattr(user, "servers", []) or []  # pyright: ignore[reportUnknownArgumentType]
                        has_server_access = any(
                            getattr(s, "machineIdentifier", None) == machine_id  # pyright: ignore[reportUnknownArgumentType, reportAny]
                            for s in user_servers  # pyright: ignore[reportAny]
                        )
                        user_type = "shared" if has_server_access else "friend"

                    result.append(
                        ExternalUser(
                            external_user_id=user_id,
                            username=username,
                            email=email,
                            user_type=user_type,
                        )
                    )

                return result

            users = await asyncio.to_thread(_list_users)

            log.info(
                "plex_users_listed",
                url=self.url,
                count=len(users),
            )

            return users

        except MediaClientError:
            raise
        except Exception as exc:
            log.error(
                "plex_list_users_failed",
                url=self.url,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to list users: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
            raise _create_media_client_error(
                f"Failed to list users: {exc}",
                operation="list_users",
                server_url=self.url,
                cause=str(exc),
                original_error=exc,
            ) from exc
