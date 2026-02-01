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
        username: str,
        password: str,
        /,
        *,
        email: str | None = None,
    ) -> ExternalUser:
        """Create a new user on the Jellyfin server and set their password.

        Creates a user account via jellyfin-sdk users.create, then sets
        the initial password via users.update_password.

        Args:
            username: The username for the new account (positional-only).
            password: The password for the new account (positional-only).
            email: Optional email address for the user (keyword-only).

        Returns:
            An ExternalUser object with the created user's details including
            external_user_id (Jellyfin user Id), username (Name), and email.

        Raises:
            MediaClientError: If the client is not initialized (use async context manager).
            MediaClientError: If the username already exists (error_code="USERNAME_TAKEN").
            MediaClientError: If user creation fails for other reasons.
        """
        if self._api is None:
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="create_user",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
            )

        try:
            # Step 1: Create user via jellyfin-sdk users.create
            # jellyfin-sdk lacks type stubs, so returns Any
            user = self._api.users.create(name=username)  # pyright: ignore[reportAny]

            # Extract user ID - jellyfin-sdk may use Id or id attribute
            user_id: str
            if hasattr(user, "Id"):  # pyright: ignore[reportAny]
                user_id = str(user.Id)  # pyright: ignore[reportAny]
            elif hasattr(user, "id"):  # pyright: ignore[reportAny]
                user_id = str(user.id)  # pyright: ignore[reportAny]
            else:
                raise MediaClientError(
                    "Failed to extract user ID from Jellyfin response",
                    operation="create_user",
                    server_url=self.url,
                    cause="User object has no Id or id attribute",
                )

            # Extract username - jellyfin-sdk may use Name or name attribute
            created_username: str
            if hasattr(user, "Name"):  # pyright: ignore[reportAny]
                created_username = str(user.Name)  # pyright: ignore[reportAny]
            elif hasattr(user, "name"):  # pyright: ignore[reportAny]
                created_username = str(user.name)  # pyright: ignore[reportAny]
            else:
                created_username = username

            # Step 2: Set password via users.update_password
            self._api.users.update_password(  # pyright: ignore[reportAny]
                user_id, new_password=password
            )

            return ExternalUser(
                external_user_id=user_id,
                username=created_username,
                email=email,
            )

        except MediaClientError:
            # Re-raise our own errors
            raise
        except Exception as exc:
            error_msg = str(exc).lower()
            # Check for username already exists error
            if "already exists" in error_msg or "duplicate" in error_msg:
                raise MediaClientError(
                    f"Username '{username}' already exists on Jellyfin server",
                    operation="create_user",
                    server_url=self.url,
                    cause=f"Username taken: {exc}",
                    error_code="USERNAME_TAKEN",
                ) from exc

            raise MediaClientError(
                f"Failed to create user on Jellyfin server: {exc}",
                operation="create_user",
                server_url=self.url,
                cause=str(exc),
            ) from exc

    async def delete_user(self, external_user_id: str, /) -> bool:
        """Delete a user from the Jellyfin server.

        Removes the user account identified by the external user ID via
        jellyfin-sdk users.delete.

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).

        Returns:
            True if the user was successfully deleted, False if the user
            was not found on the server.

        Raises:
            MediaClientError: If the client is not initialized (use async context manager).
            MediaClientError: If deletion fails for reasons other than user not found.
        """
        if self._api is None:
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="delete_user",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
            )

        try:
            # Delete user via jellyfin-sdk users.delete
            self._api.users.delete(external_user_id)  # pyright: ignore[reportAny]
            return True
        except Exception as exc:
            error_msg = str(exc).lower()
            # Check for user not found error - return False per Requirements 4.3
            if "not found" in error_msg or "404" in error_msg:
                return False

            # Re-raise other errors as MediaClientError per Requirements 4.4
            raise MediaClientError(
                f"Failed to delete user from Jellyfin server: {exc}",
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
        """Enable or disable a user on the Jellyfin server.

        Retrieves the current user and their policy via jellyfin-sdk,
        then updates the IsDisabled flag based on the enabled parameter.

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).
            enabled: Whether the user should be enabled (keyword-only).
                True sets IsDisabled=False, False sets IsDisabled=True.

        Returns:
            True if the status was successfully changed, False if the user
            was not found on the server.

        Raises:
            MediaClientError: If the client is not initialized (use async context manager).
            MediaClientError: If the status change fails for reasons other than user not found.
        """
        if self._api is None:
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="set_user_enabled",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
            )

        try:
            # Step 1: Get current user via jellyfin-sdk users.get
            # jellyfin-sdk lacks type stubs, so returns Any
            user = self._api.users.get(external_user_id)  # pyright: ignore[reportAny]

            if user is None:
                return False

            # Step 2: Get current policy from user
            # jellyfin-sdk may use Policy or policy attribute
            # Using Any type since jellyfin-sdk lacks type stubs
            policy = None
            if hasattr(user, "Policy"):  # pyright: ignore[reportAny]
                policy = user.Policy  # pyright: ignore[reportAny]
            elif hasattr(user, "policy"):  # pyright: ignore[reportAny]
                policy = user.policy  # pyright: ignore[reportAny]

            if policy is None:
                raise MediaClientError(
                    "Failed to retrieve user policy from Jellyfin response",
                    operation="set_user_enabled",
                    server_url=self.url,
                    cause="User object has no Policy or policy attribute",
                )

            # Step 3: Update IsDisabled flag based on enabled parameter
            # enabled=True means IsDisabled=False, enabled=False means IsDisabled=True
            if hasattr(policy, "IsDisabled"):  # pyright: ignore[reportAny]
                policy.IsDisabled = not enabled
            elif hasattr(policy, "is_disabled"):  # pyright: ignore[reportAny]
                policy.is_disabled = not enabled
            else:
                raise MediaClientError(
                    "Failed to update IsDisabled flag in user policy",
                    operation="set_user_enabled",
                    server_url=self.url,
                    cause="Policy object has no IsDisabled or is_disabled attribute",
                )

            # Step 4: Update user policy via jellyfin-sdk
            self._api.users.update_policy(  # pyright: ignore[reportAny]
                external_user_id, policy
            )

            return True

        except MediaClientError:
            # Re-raise our own errors
            raise
        except Exception as exc:
            error_msg = str(exc).lower()
            # Check for user not found error - return False per Requirements 5.5
            if "not found" in error_msg or "404" in error_msg:
                return False

            # Re-raise other errors as MediaClientError per Requirements 5.6
            raise MediaClientError(
                f"Failed to update user enabled status on Jellyfin server: {exc}",
                operation="set_user_enabled",
                server_url=self.url,
                cause=str(exc),
            ) from exc

    async def set_library_access(
        self,
        external_user_id: str,
        library_ids: Sequence[str],
        /,
    ) -> bool:
        """Set which libraries a user can access on the Jellyfin server.

        Retrieves the current user and their policy via jellyfin-sdk,
        then updates EnableAllFolders to False and EnabledFolders to
        the specified library IDs.

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).
            library_ids: Sequence of library external IDs to grant access to
                (positional-only). An empty sequence grants access to no libraries.

        Returns:
            True if library access was successfully updated, False if the user
            was not found on the server.

        Raises:
            MediaClientError: If the client is not initialized (use async context manager).
            MediaClientError: If the library access update fails for reasons other
                than user not found.
        """
        if self._api is None:
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="set_library_access",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
            )

        try:
            # Step 1: Get current user via jellyfin-sdk users.get
            # jellyfin-sdk lacks type stubs, so returns Any
            user = self._api.users.get(external_user_id)  # pyright: ignore[reportAny]

            if user is None:
                return False

            # Step 2: Get current policy from user
            # jellyfin-sdk may use Policy or policy attribute
            policy = None
            if hasattr(user, "Policy"):  # pyright: ignore[reportAny]
                policy = user.Policy  # pyright: ignore[reportAny]
            elif hasattr(user, "policy"):  # pyright: ignore[reportAny]
                policy = user.policy  # pyright: ignore[reportAny]

            if policy is None:
                raise MediaClientError(
                    "Failed to retrieve user policy from Jellyfin response",
                    operation="set_library_access",
                    server_url=self.url,
                    cause="User object has no Policy or policy attribute",
                )

            # Step 3: Set EnableAllFolders=False per Requirements 6.2, 6.3
            # This restricts the user to only the specified libraries
            if hasattr(policy, "EnableAllFolders"):  # pyright: ignore[reportAny]
                policy.EnableAllFolders = False
            elif hasattr(policy, "enable_all_folders"):  # pyright: ignore[reportAny]
                policy.enable_all_folders = False
            else:
                raise MediaClientError(
                    "Failed to update EnableAllFolders flag in user policy",
                    operation="set_library_access",
                    server_url=self.url,
                    cause="Policy object has no EnableAllFolders or enable_all_folders attribute",
                )

            # Step 4: Set EnabledFolders to the library IDs per Requirements 6.2, 6.3
            # Convert Sequence to list for the API
            library_id_list = list(library_ids)
            if hasattr(policy, "EnabledFolders"):  # pyright: ignore[reportAny]
                policy.EnabledFolders = library_id_list
            elif hasattr(policy, "enabled_folders"):  # pyright: ignore[reportAny]
                policy.enabled_folders = library_id_list
            else:
                raise MediaClientError(
                    "Failed to update EnabledFolders in user policy",
                    operation="set_library_access",
                    server_url=self.url,
                    cause="Policy object has no EnabledFolders or enabled_folders attribute",
                )

            # Step 5: Update user policy via jellyfin-sdk
            self._api.users.update_policy(  # pyright: ignore[reportAny]
                external_user_id, policy
            )

            return True

        except MediaClientError:
            # Re-raise our own errors
            raise
        except Exception as exc:
            error_msg = str(exc).lower()
            # Check for user not found error - return False per Requirements 6.5
            if "not found" in error_msg or "404" in error_msg:
                return False

            # Re-raise other errors as MediaClientError per Requirements 6.6
            raise MediaClientError(
                f"Failed to set library access on Jellyfin server: {exc}",
                operation="set_library_access",
                server_url=self.url,
                cause=str(exc),
            ) from exc
