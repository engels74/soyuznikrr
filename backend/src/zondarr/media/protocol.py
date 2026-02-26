"""MediaClient protocol definition.

Provides the Protocol-based abstraction for media server clients.
Uses Python's typing.Protocol for structural subtyping - implementations
do not need to inherit from this class, they just need to implement
the required methods.

The protocol defines:
- Connection lifecycle via async context manager
- Server connectivity testing
- Library retrieval
- User management (create, delete, enable/disable)
- Library access configuration
- Capability declaration

Uses Python 3.14 features:
- Deferred annotations (no forward reference quotes needed)
- Self type for proper return type in subclasses
- Positional-only and keyword-only parameters where appropriate
"""

from collections.abc import Sequence
from typing import Protocol, Self

from .types import Capability, ExternalUser, LibraryInfo, ServerInfo


class MediaClient(Protocol):
    """Protocol defining the interface for media server clients.

    Implementations must support async context manager for connection lifecycle.
    Uses Python 3.14 deferred annotations - no forward reference quotes needed.
    Uses Self type for proper return type in subclasses.

    All methods are async to support non-blocking I/O operations.
    For sync libraries (like python-plexapi), implementations should use
    asyncio.to_thread() to avoid blocking the event loop.

    Example usage:
        async with client as c:
            if await c.test_connection():
                libraries = await c.get_libraries()
                user = await c.create_user("john", "password123")
                await c.set_library_access(user.external_user_id, [lib.external_id for lib in libraries])
    """

    @classmethod
    def capabilities(cls) -> set[Capability]:
        """Return the set of capabilities this client supports.

        Used by the ClientRegistry to query what operations are available
        for a given server type before attempting them.

        Returns:
            A set of Capability enum values indicating supported features.
        """
        ...

    @classmethod
    def supported_permissions(cls) -> frozenset[str]:
        """Return the set of universal permission keys this client supports.

        Used to inform the frontend which permission toggles to display
        for a given server type, without hardcoding provider knowledge
        in the UI.

        Returns:
            A frozenset of universal permission key strings
            (e.g. "can_download", "can_stream").
        """
        ...

    async def __aenter__(self) -> Self:
        """Enter async context, establishing connection.

        Implementations should initialize any HTTP clients, authenticate
        with the media server, and prepare for subsequent operations.

        Returns:
            Self for use in async with statements.
        """
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context, cleaning up resources.

        Implementations should close HTTP clients, release connections,
        and perform any necessary cleanup.

        Args:
            exc_type: The exception type if an exception was raised, None otherwise.
            exc_val: The exception instance if an exception was raised, None otherwise.
            exc_tb: The traceback if an exception was raised, None otherwise.
        """
        ...

    async def test_connection(self) -> bool:
        """Test connectivity to the media server.

        Verifies that the server is reachable and the API key is valid.
        Should not raise exceptions for connection failures - instead
        returns False.

        Returns:
            True if the connection is successful and authenticated,
            False otherwise.
        """
        ...

    async def get_server_info(self) -> ServerInfo:
        """Return server name and version metadata.

        Requires an active connection (call within async context manager).

        Returns:
            A ServerInfo object with the server's name and version.
        """
        ...

    async def get_libraries(self) -> Sequence[LibraryInfo]:
        """Retrieve all libraries from the media server.

        Fetches the list of content libraries (movies, TV shows, music, etc.)
        available on the media server.

        Returns:
            A sequence of LibraryInfo objects describing each library.

        Raises:
            MediaClientError: If the operation fails due to server error.
        """
        ...

    async def create_user(
        self,
        username: str,
        password: str,
        /,
        *,
        email: str | None = None,
        auth_token: str | None = None,
    ) -> ExternalUser:
        """Create a new user on the media server.

        Creates a user account with the specified credentials. The username
        and password are positional-only to prevent accidental keyword usage
        that might expose credentials in logs.

        Args:
            username: The username for the new account (positional-only).
            password: The password for the new account (positional-only).
            email: Optional email address for the user (keyword-only).
            auth_token: Optional OAuth auth token from the user (keyword-only).
                Used by providers that support direct library sharing (e.g. Plex)
                to grant access without creating a friend relationship.

        Returns:
            An ExternalUser object with the created user's details.

        Raises:
            MediaClientError: If user creation fails (e.g., username taken).
        """
        ...

    async def delete_user(self, external_user_id: str, /) -> bool:
        """Delete a user from the media server.

        Removes the user account identified by the external user ID.
        The external_user_id is positional-only for consistency.

        Args:
            external_user_id: The user's unique identifier on the media server
                (positional-only).

        Returns:
            True if the user was successfully deleted, False if the user
            was not found.

        Raises:
            MediaClientError: If deletion fails due to server error.
        """
        ...

    async def set_user_enabled(
        self,
        external_user_id: str,
        /,
        *,
        enabled: bool,
    ) -> bool:
        """Enable or disable a user on the media server.

        Changes the enabled status of a user account. Disabled users
        cannot access the media server.

        Uses positional-only for external_user_id, keyword-only for enabled
        to make the intent clear at call sites.

        Args:
            external_user_id: The user's unique identifier on the media server
                (positional-only).
            enabled: Whether the user should be enabled (keyword-only).

        Returns:
            True if the status was successfully changed, False if the user
            was not found.

        Raises:
            MediaClientError: If the operation fails due to server error.
        """
        ...

    async def set_library_access(
        self,
        external_user_id: str,
        library_ids: Sequence[str],
        /,
    ) -> bool:
        """Set which libraries a user can access.

        Configures the user's library permissions. The user will only be
        able to access the specified libraries. Pass an empty sequence
        to revoke all library access.

        Both parameters are positional-only for consistency with other
        user management methods.

        Args:
            external_user_id: The user's unique identifier on the media server
                (positional-only).
            library_ids: Sequence of library external IDs to grant access to
                (positional-only).

        Returns:
            True if permissions were successfully updated, False if the user
            was not found.

        Raises:
            MediaClientError: If the operation fails due to server error.
        """
        ...

    async def update_permissions(
        self,
        external_user_id: str,
        /,
        *,
        permissions: dict[str, bool],
    ) -> bool:
        """Update user permissions by mapping universal permissions to server-specific settings.

        Maps universal permission names to server-specific policy fields.
        Only provided keys are updated; other permissions remain unchanged.

        Universal permission mapping:
        - can_download: Whether the user can download content
        - can_stream: Whether the user can stream/play content
        - can_sync: Whether the user can sync content for offline use
        - can_transcode: Whether the user can use transcoding

        Args:
            external_user_id: The user's unique identifier on the media server
                (positional-only).
            permissions: Dictionary mapping universal permission names to boolean
                values (keyword-only).

        Returns:
            True if permissions were successfully updated, False if the user
            was not found.

        Raises:
            MediaClientError: If the operation fails due to server error.
        """
        ...

    async def remove_shared_access(self, external_user_id: str, /) -> bool:
        """Remove shared library access for a user without removing the friend relationship.

        For Plex: removes shared server entries while keeping the friend connection.
        For providers that don't support this distinction, returns False.

        Args:
            external_user_id: The user's unique identifier on the media server
                (positional-only).

        Returns:
            True if shared access was found and removed, False if not applicable
            or no shared access existed.

        Raises:
            MediaClientError: If the operation fails due to server error.
        """
        ...

    async def list_users(self) -> Sequence[ExternalUser]:
        """List all users from the media server.

        Retrieves all user accounts from the server for synchronization
        purposes. Used by the SyncService to compare local records with
        the actual state of users on the media server.

        Returns:
            A sequence of ExternalUser objects with external_user_id,
            username, and optionally email for each user on the server.

        Raises:
            MediaClientError: If the operation fails due to server error.
        """
        ...
