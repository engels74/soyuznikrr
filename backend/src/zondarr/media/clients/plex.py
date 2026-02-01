"""Plex media server client.

Provides the PlexClient class that implements the MediaClient protocol
for communicating with Plex media servers.

Uses python-plexapi (PlexAPI v4.18+) for server communication.
PlexAPI is synchronous, so operations use asyncio.to_thread() to avoid
blocking the event loop.

This is a stub implementation for the foundation phase. Full implementation
will be added in Phase 3.

Uses Python 3.14 features:
- Deferred annotations (no forward reference quotes needed)
- Self type for proper return type in context manager
"""

from collections.abc import Sequence
from typing import Self

from zondarr.media.types import Capability, ExternalUser, LibraryInfo


class PlexClient:
    """Plex media server client.

    Implements the MediaClient protocol for Plex servers.
    Uses python-plexapi for server communication.

    PlexAPI is synchronous, so all operations use asyncio.to_thread()
    to run without blocking the event loop.

    This is a stub implementation for the foundation phase.
    Full implementation will be added in Phase 3.

    Attributes:
        url: The Plex server URL.
        api_key: The API key (X-Plex-Token) for authentication.
    """

    url: str
    api_key: str
    _server: object | None

    def __init__(self, *, url: str, api_key: str) -> None:
        """Initialize a PlexClient.

        Args:
            url: The Plex server URL (keyword-only).
            api_key: The API key (X-Plex-Token) for authentication (keyword-only).
        """
        self.url = url
        self.api_key = api_key
        self._server = None  # PlexServer instance (Phase 3)

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

        Initializes the PlexServer connection using asyncio.to_thread()
        since python-plexapi is synchronous.

        Returns:
            Self for use in async with statements.
        """
        # Phase 3: Initialize PlexServer connection
        # from plexapi.server import PlexServer
        # import asyncio
        # self._server = await asyncio.to_thread(
        #     PlexServer, self.url, self.api_key
        # )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context, cleaning up resources.

        Closes any open connections and releases resources.

        Args:
            exc_type: The exception type if an exception was raised, None otherwise.
            exc_val: The exception instance if an exception was raised, None otherwise.
            exc_tb: The traceback if an exception was raised, None otherwise.
        """
        # Phase 3: Cleanup PlexServer resources
        self._server = None

    async def test_connection(self) -> bool:
        """Test connectivity to the Plex server.

        Verifies that the server is reachable and the API key is valid.

        Returns:
            True if the connection is successful and authenticated,
            False otherwise.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("Plex client implementation in Phase 3")

    async def get_libraries(self) -> Sequence[LibraryInfo]:
        """Retrieve all libraries from the Plex server.

        Fetches the list of content libraries (movies, TV shows, music, etc.)
        available on the server.

        Returns:
            A sequence of LibraryInfo objects describing each library.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("Plex client implementation in Phase 3")

    async def create_user(
        self,
        _username: str,
        _password: str,
        /,
        *,
        _email: str | None = None,
    ) -> ExternalUser:
        """Create a new user on the Plex server.

        Creates a user account with the specified credentials.
        Note: Plex user management works through Plex.tv accounts,
        so this creates a managed user or invites an existing Plex user.

        Args:
            _username: The username for the new account (positional-only).
            _password: The password for the new account (positional-only).
            _email: Optional email address for the user (keyword-only).

        Returns:
            An ExternalUser object with the created user's details.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("Plex client implementation in Phase 3")

    async def delete_user(self, _external_user_id: str, /) -> bool:
        """Delete a user from the Plex server.

        Removes the user account identified by the external user ID.

        Args:
            _external_user_id: The user's unique identifier on the server
                (positional-only).

        Returns:
            True if the user was successfully deleted, False if the user
            was not found.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("Plex client implementation in Phase 3")

    async def set_user_enabled(
        self,
        _external_user_id: str,
        /,
        *,
        _enabled: bool,
    ) -> bool:
        """Enable or disable a user on the Plex server.

        Note: Plex does not directly support enable/disable functionality.
        This method is included for protocol compliance but may have
        limited functionality in the full implementation.

        Args:
            _external_user_id: The user's unique identifier on the server
                (positional-only).
            _enabled: Whether the user should be enabled (keyword-only).

        Returns:
            True if the status was successfully changed, False if the user
            was not found or operation not supported.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("Plex client implementation in Phase 3")

    async def set_library_access(
        self,
        _external_user_id: str,
        _library_ids: Sequence[str],
        /,
    ) -> bool:
        """Set which libraries a user can access on the Plex server.

        Configures the user's library permissions.

        Args:
            _external_user_id: The user's unique identifier on the server
                (positional-only).
            _library_ids: Sequence of library external IDs to grant access to
                (positional-only).

        Returns:
            True if permissions were successfully updated, False if the user
            was not found.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("Plex client implementation in Phase 3")
