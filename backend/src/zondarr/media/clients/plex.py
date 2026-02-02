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
from typing import Self

import structlog
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

from zondarr.media.exceptions import MediaClientError
from zondarr.media.types import Capability, ExternalUser, LibraryInfo, PlexUserType

log: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]


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
        }

    async def __aenter__(self) -> Self:
        """Enter async context, establishing connection.

        Initializes the PlexServer and MyPlexAccount connections using
        asyncio.to_thread() since python-plexapi is synchronous.

        Returns:
            Self for use in async with statements.
        """

        def _connect() -> tuple[PlexServer, MyPlexAccount]:
            server = PlexServer(self.url, self.api_key)
            # plexapi lacks type stubs, myPlexAccount returns MyPlexAccount
            account: MyPlexAccount = server.myPlexAccount()  # pyright: ignore[reportUnknownVariableType]
            return server, account  # pyright: ignore[reportUnknownVariableType]

        log.info("plex_client_connecting", url=self.url)
        self._server, self._account = await asyncio.to_thread(_connect)
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

    async def get_libraries(self) -> Sequence[LibraryInfo]:
        """Retrieve all libraries (sections) from the Plex server.

        Fetches the list of content libraries (movies, TV shows, music, etc.)
        available on the server via python-plexapi's library.sections().

        Maps Plex section attributes to LibraryInfo:
        - key → external_id
        - title → name
        - type → library_type (movie, show, artist, photo, etc.)

        Returns:
            A sequence of LibraryInfo objects describing each library.

        Raises:
            MediaClientError: If the client is not initialized (use async context manager).
            MediaClientError: If library retrieval fails due to connection or API errors.
        """
        if self._server is None:
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="get_libraries",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
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
            raise MediaClientError(
                f"Failed to retrieve libraries from Plex server: {exc}",
                operation="get_libraries",
                server_url=self.url,
                cause=str(exc),
            ) from exc

    async def _create_friend(self, email: str) -> ExternalUser:
        """Create a Friend user via inviteFriend.

        Sends an invitation to an existing Plex.tv account. The user must
        have an existing Plex account or create one to accept the invitation.

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
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="create_friend",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
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
            )

        except MediaClientError:
            raise
        except Exception as exc:
            error_str = str(exc).lower()
            # Check for duplicate user error
            if "already" in error_str or "shared" in error_str:
                raise MediaClientError(
                    f"User with email {email} is already a Friend",
                    operation="create_friend",
                    server_url=self.url,
                    cause=str(exc),
                    error_code="USER_ALREADY_EXISTS",
                ) from exc

            raise MediaClientError(
                f"Failed to invite Friend: {exc}",
                operation="create_friend",
                server_url=self.url,
                cause=str(exc),
            ) from exc

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
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="create_home_user",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
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
            )

        except MediaClientError:
            raise
        except Exception as exc:
            error_str = str(exc).lower()
            # Check for duplicate username error
            if "taken" in error_str or "exists" in error_str or "already" in error_str:
                raise MediaClientError(
                    f"Username '{username}' is already taken",
                    operation="create_home_user",
                    server_url=self.url,
                    cause=str(exc),
                    error_code="USERNAME_TAKEN",
                ) from exc

            raise MediaClientError(
                f"Failed to create Home User: {exc}",
                operation="create_home_user",
                server_url=self.url,
                cause=str(exc),
            ) from exc

    async def create_user(
        self,
        username: str,
        password: str,
        /,
        *,
        email: str | None = None,
        plex_user_type: PlexUserType = PlexUserType.FRIEND,
    ) -> ExternalUser:
        """Create a new user on the Plex server.

        Creates a user account via Plex.tv. For Friends, sends an invitation
        to an existing Plex.tv account. For Home Users, creates a managed
        user within the Plex Home.

        Note: The password parameter is ignored for Plex since authentication
        is handled through Plex.tv accounts or managed Home Users.

        Args:
            username: The username for the new account (positional-only).
            password: Ignored for Plex (positional-only).
            email: Email address for Friend invitations (keyword-only).
            plex_user_type: Type of user to create - FRIEND or HOME (keyword-only).

        Returns:
            An ExternalUser object with the created user's details.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If user_type is FRIEND but no email is provided.
            MediaClientError: If the user already exists.
            MediaClientError: If user creation fails for other reasons.
        """
        _ = password  # Explicitly ignore password parameter

        if plex_user_type == PlexUserType.FRIEND:
            if email is None:
                raise MediaClientError(
                    "Email is required for Friend invitations",
                    operation="create_user",
                    server_url=self.url,
                    cause="plex_user_type is FRIEND but email was not provided",
                    error_code="EMAIL_REQUIRED",
                )
            return await self._create_friend(email)

        # plex_user_type == PlexUserType.HOME
        return await self._create_home_user(username)

    async def delete_user(self, external_user_id: str, /) -> bool:
        """Delete a user from the Plex server.

        Removes the user account identified by the external user ID.
        Attempts to find the user among Friends first, then Home Users,
        and uses the appropriate removal method.

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
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="delete_user",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
            )

        try:

            def _delete() -> bool:
                assert self._account is not None  # noqa: S101
                # plexapi lacks type stubs, users() returns list of MyPlexUser
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

                # Determine if this is a Home User or Friend
                # Home Users have home=True attribute
                is_home_user: bool = getattr(target_user, "home", False)  # pyright: ignore[reportUnknownArgumentType]

                if is_home_user:
                    # Remove Home User via removeHomeUser
                    self._account.removeHomeUser(target_user)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportUnusedCallResult]
                else:
                    # Remove Friend via removeFriend
                    self._account.removeFriend(target_user)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportUnusedCallResult]

                return True

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
            error_str = str(exc).lower()
            # Check for not found error
            if "not found" in error_str or "does not exist" in error_str:
                log.warning(
                    "plex_user_not_found",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                )
                return False

            raise MediaClientError(
                f"Failed to delete user: {exc}",
                operation="delete_user",
                server_url=self.url,
                cause=str(exc),
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
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="set_library_access",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
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
            error_str = str(exc).lower()
            # Check for not found error
            if "not found" in error_str or "does not exist" in error_str:
                log.warning(
                    "plex_user_not_found_for_library_access",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                )
                return False

            raise MediaClientError(
                f"Failed to set library access: {exc}",
                operation="set_library_access",
                server_url=self.url,
                cause=str(exc),
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
        Currently supports can_download → allowSync mapping.

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
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="update_permissions",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
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
                # can_download → allowSync
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
                    permissions=permissions,
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
            error_str = str(exc).lower()
            # Check for not found error
            if "not found" in error_str or "does not exist" in error_str:
                log.warning(
                    "plex_user_not_found_for_permissions",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                )
                return False

            raise MediaClientError(
                f"Failed to update permissions: {exc}",
                operation="update_permissions",
                server_url=self.url,
                cause=str(exc),
            ) from exc

    async def list_users(self) -> Sequence[ExternalUser]:
        """List all users with access to the Plex server.

        Retrieves all Friends and Home Users from the Plex account
        and maps them to ExternalUser structs.

        Returns:
            A sequence of ExternalUser objects with external_user_id,
            username, and email (if available).

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If user listing fails due to connection or API errors.
        """
        if self._account is None:
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="list_users",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
            )

        try:

            def _list_users() -> list[ExternalUser]:
                assert self._account is not None  # noqa: S101

                # Get all users (Friends and Home Users)
                users = self._account.users()  # pyright: ignore[reportUnknownVariableType]

                result: list[ExternalUser] = []
                for user in users:  # pyright: ignore[reportUnknownVariableType]
                    user_id: str = str(getattr(user, "id", ""))  # pyright: ignore[reportUnknownArgumentType]
                    username: str = getattr(user, "username", "") or ""  # pyright: ignore[reportUnknownArgumentType]
                    email: str | None = getattr(user, "email", None)  # pyright: ignore[reportUnknownArgumentType]

                    if user_id:
                        result.append(
                            ExternalUser(
                                external_user_id=user_id,
                                username=username,
                                email=email,
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
            raise MediaClientError(
                f"Failed to list users: {exc}",
                operation="list_users",
                server_url=self.url,
                cause=str(exc),
            ) from exc
