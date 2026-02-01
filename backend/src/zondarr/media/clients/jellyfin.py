"""Jellyfin media server client.

Provides the JellyfinClient class that implements the MediaClient protocol
for communicating with Jellyfin media servers.

Uses jellyfin-sdk (webysther/jellyfin-sdk-python) - a modern Python 3.13+ SDK
with high-level abstractions, method chaining, and JSONPath support.

Uses Python 3.14 features:
- Deferred annotations (no forward reference quotes needed)
- Self type for proper return type in context manager
"""

from collections.abc import Sequence
from typing import Self

import jellyfin

from zondarr.media.exceptions import MediaClientError
from zondarr.media.types import Capability, ExternalUser, LibraryInfo


class JellyfinClient:
    """Jellyfin media server client.

    Implements the MediaClient protocol for Jellyfin servers.
    Uses jellyfin-sdk for server communication.

    Attributes:
        url: The Jellyfin server URL.
        api_key: The API key for authentication.
    """

    url: str
    api_key: str
    _api: jellyfin.Api | None

    def __init__(self, *, url: str, api_key: str) -> None:
        """Initialize a JellyfinClient.

        Args:
            url: The Jellyfin server URL (keyword-only).
            api_key: The API key for authentication (keyword-only).
        """
        self.url = url
        self.api_key = api_key
        self._api = None

    @classmethod
    def capabilities(cls) -> set[Capability]:
        """Return the set of capabilities this client supports.

        Jellyfin supports all standard capabilities including
        download permission management.

        Returns:
            A set of Capability enum values indicating supported features.
        """
        return {
            Capability.CREATE_USER,
            Capability.DELETE_USER,
            Capability.ENABLE_DISABLE_USER,
            Capability.LIBRARY_ACCESS,
            Capability.DOWNLOAD_PERMISSION,
        }

    async def __aenter__(self) -> Self:
        """Enter async context, establishing connection.

        Initializes the jellyfin-sdk API client with the configured
        URL and API key.

        Returns:
            Self for use in async with statements.
        """
        self._api = jellyfin.api(self.url, self.api_key)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context, cleaning up resources.

        Releases the jellyfin-sdk API instance.

        Args:
            exc_type: The exception type if an exception was raised, None otherwise.
            exc_val: The exception instance if an exception was raised, None otherwise.
            exc_tb: The traceback if an exception was raised, None otherwise.
        """
        self._api = None

    async def test_connection(self) -> bool:
        """Test connectivity to the Jellyfin server.

        Verifies that the server is reachable and the API key is valid
        by querying the server system info via jellyfin-sdk.

        Returns:
            True if the connection is successful and authenticated,
            False otherwise. Never raises exceptions for connection failures.
        """
        if self._api is None:
            return False

        try:
            # Query server system info to verify connectivity and authentication
            # jellyfin-sdk lacks type stubs, so system.info returns Any
            info: object = self._api.system.info  # pyright: ignore[reportAny]
            return info is not None
        except Exception:
            # Handle all connection errors gracefully - return False, don't raise
            return False

    async def get_libraries(self) -> Sequence[LibraryInfo]:
        """Retrieve all libraries (virtual folders) from the Jellyfin server.

        Fetches the list of content libraries (movies, TV shows, music, etc.)
        available on the server via jellyfin-sdk's library.virtual_folders.

        Maps Jellyfin CollectionType values to library_type:
        - movies, tvshows, music, books, photos, homevideos, musicvideos, boxsets
        - Unknown or missing types default to "unknown"

        Returns:
            A sequence of LibraryInfo objects describing each library.

        Raises:
            MediaClientError: If library retrieval fails due to connection
                or API errors.
        """
        if self._api is None:
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="get_libraries",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
            )

        try:
            # jellyfin-sdk lacks type stubs, so virtual_folders returns Any
            folders = self._api.library.virtual_folders  # pyright: ignore[reportAny]

            if folders is None:
                return []

            # Map Jellyfin virtual folders to LibraryInfo structs
            libraries: list[LibraryInfo] = []
            for folder in folders:  # pyright: ignore[reportAny]
                # Extract fields from the folder object
                # jellyfin-sdk uses attribute access for JSON fields
                external_id: str = str(
                    folder.ItemId  # pyright: ignore[reportAny]
                    if hasattr(folder, "ItemId")  # pyright: ignore[reportAny]
                    else folder.item_id  # pyright: ignore[reportAny]
                )
                name: str = str(
                    folder.Name  # pyright: ignore[reportAny]
                    if hasattr(folder, "Name")  # pyright: ignore[reportAny]
                    else folder.name  # pyright: ignore[reportAny]
                )

                # CollectionType may be None for mixed/unknown libraries
                collection_type: str | None = None
                if hasattr(folder, "CollectionType"):  # pyright: ignore[reportAny]
                    collection_type = folder.CollectionType  # pyright: ignore[reportAny]
                elif hasattr(folder, "collection_type"):  # pyright: ignore[reportAny]
                    collection_type = folder.collection_type  # pyright: ignore[reportAny]

                library_type: str = (
                    str(collection_type) if collection_type else "unknown"
                )

                libraries.append(
                    LibraryInfo(
                        external_id=external_id,
                        name=name,
                        library_type=library_type,
                    )
                )

            return libraries

        except Exception as exc:
            raise MediaClientError(
                f"Failed to retrieve libraries from Jellyfin server: {exc}",
                operation="get_libraries",
                server_url=self.url,
                cause=str(exc),
            ) from exc

    async def create_user(
        self,
        _username: str,
        _password: str,
        /,
        *,
        _email: str | None = None,
    ) -> ExternalUser:
        """Create a new user on the Jellyfin server.

        Creates a user account with the specified credentials.

        Args:
            _username: The username for the new account (positional-only).
            _password: The password for the new account (positional-only).
            _email: Optional email address for the user (keyword-only).

        Returns:
            An ExternalUser object with the created user's details.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("Jellyfin client implementation in Phase 2")

    async def delete_user(self, _external_user_id: str, /) -> bool:
        """Delete a user from the Jellyfin server.

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
        raise NotImplementedError("Jellyfin client implementation in Phase 2")

    async def set_user_enabled(
        self,
        _external_user_id: str,
        /,
        *,
        _enabled: bool,
    ) -> bool:
        """Enable or disable a user on the Jellyfin server.

        Changes the enabled status of a user account.

        Args:
            _external_user_id: The user's unique identifier on the server
                (positional-only).
            _enabled: Whether the user should be enabled (keyword-only).

        Returns:
            True if the status was successfully changed, False if the user
            was not found.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("Jellyfin client implementation in Phase 2")

    async def set_library_access(
        self,
        _external_user_id: str,
        _library_ids: Sequence[str],
        /,
    ) -> bool:
        """Set which libraries a user can access on the Jellyfin server.

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
        raise NotImplementedError("Jellyfin client implementation in Phase 2")
