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
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import jellyfin

from zondarr.core.exceptions import ExternalServiceError
from zondarr.media.exceptions import MediaClientError
from zondarr.media.types import Capability, ExternalUser, LibraryInfo, ServerInfo


def _is_external_service_error(error: Exception) -> bool:
    """Determine if an error is an external service error.

    External service errors are connection failures, timeouts, and
    server-side API errors that indicate the Jellyfin server is unavailable
    or malfunctioning.

    Args:
        error: The exception to check.

    Returns:
        True if the error is an external service error, False otherwise.
    """
    error_str = str(error).lower()

    # Connection errors
    if any(
        keyword in error_str
        for keyword in [
            "connection",
            "timeout",
            "timed out",
            "unreachable",
            "refused",
            "network",
            "socket",
            "dns",
            "resolve",
        ]
    ):
        return True

    # HTTP errors indicating server issues (5xx)
    if any(code in error_str for code in ["500", "502", "503", "504"]):
        return True

    # Authentication errors (server rejected credentials)
    if "401" in error_str or "unauthorized" in error_str:
        return True

    return False


def _create_external_service_error(
    message: str,
    *,
    server_url: str,
    original_error: Exception | None = None,
) -> ExternalServiceError:
    """Create an ExternalServiceError for Jellyfin server failures.

    Used when the Jellyfin server is unreachable, times out, or returns
    an API error indicating the service is unavailable.

    Args:
        message: Human-readable error description.
        server_url: The Jellyfin server URL (used as service_name).
        original_error: The original exception that caused this error.

    Returns:
        An ExternalServiceError with the server URL as service name.
    """
    return ExternalServiceError(
        f"Jellyfin ({server_url})",
        message,
        original=original_error,
    )


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

    @classmethod
    def supported_permissions(cls) -> frozenset[str]:
        return frozenset({"can_download", "can_stream", "can_sync", "can_transcode"})

    async def __aenter__(self) -> Self:
        """Enter async context, establishing connection.

        Initializes the jellyfin-sdk API client with the configured
        URL and API key.

        Returns:
            Self for use in async with statements.

        Raises:
            ExternalServiceError: If connection to the Jellyfin server fails.
        """
        try:
            import warnings

            warnings.filterwarnings(
                "ignore",
                message="Core Pydantic V1 functionality isn't compatible with Python 3.14",
                category=UserWarning,
            )
            import jellyfin

            self._api = jellyfin.api(self.url, self.api_key)
        except Exception as exc:
            raise _create_external_service_error(
                f"Failed to connect to Jellyfin server: {exc}",
                server_url=self.url,
                original_error=exc,
            ) from exc
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

    async def get_server_info(self) -> ServerInfo:
        """Return server name and version metadata.

        Accesses jellyfin-sdk's system.info to extract ServerName and Version.

        Returns:
            A ServerInfo object with the server's name and version.

        Raises:
            MediaClientError: If the client is not initialized.
        """
        if self._api is None:
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="get_server_info",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
            )

        try:
            info: object = self._api.system.info  # pyright: ignore[reportAny]

            # Extract ServerName (handle both camelCase and snake_case)
            server_name: str = "Unknown"
            if hasattr(info, "ServerName"):
                server_name = str(info.ServerName)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownArgumentType]
            elif hasattr(info, "server_name"):
                server_name = str(info.server_name)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownArgumentType]

            # Extract Version
            version: str | None = None
            if hasattr(info, "Version"):
                version = str(info.Version)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownArgumentType]
            elif hasattr(info, "version"):
                version = str(info.version)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownArgumentType]

            return ServerInfo(server_name=server_name, version=version)
        except Exception as exc:
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to get server info from Jellyfin: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
            raise MediaClientError(
                f"Failed to get server info from Jellyfin: {exc}",
                operation="get_server_info",
                server_url=self.url,
                cause=str(exc),
            ) from exc

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
            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to retrieve libraries from Jellyfin server: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
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
        auth_token: str | None = None,
    ) -> ExternalUser:
        """Create a new user on the Jellyfin server and set their password.

        Creates a user account via jellyfin-sdk users.create, then sets
        the initial password via users.update_password.

        Args:
            username: The username for the new account (positional-only).
            password: The password for the new account (positional-only).
            email: Optional email address for the user (keyword-only).
            auth_token: Ignored for Jellyfin (keyword-only).

        Returns:
            An ExternalUser object with the created user's details including
            external_user_id (Jellyfin user Id), username (Name), and email.

        Raises:
            MediaClientError: If the client is not initialized (use async context manager).
            MediaClientError: If the username already exists (error_code="USERNAME_TAKEN").
            MediaClientError: If user creation fails for other reasons.
        """
        _ = auth_token  # Not used for Jellyfin
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

            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to create user on Jellyfin server: {exc}",
                    server_url=self.url,
                    original_error=exc,
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

            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to delete user from Jellyfin server: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc

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

            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to update user enabled status on Jellyfin server: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc

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

            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to set library access on Jellyfin server: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc

            # Re-raise other errors as MediaClientError per Requirements 6.6
            raise MediaClientError(
                f"Failed to set library access on Jellyfin server: {exc}",
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
        """Update user permissions by mapping universal permissions to Jellyfin policy.

        Retrieves the current user and their policy via jellyfin-sdk,
        then maps universal permission names to Jellyfin-specific policy fields
        and updates the policy.

        Permission mapping (per Requirements 7.3-7.6):
        - can_download -> EnableContentDownloading
        - can_stream -> EnableMediaPlayback
        - can_sync -> EnableSyncTranscoding
        - can_transcode -> EnableAudioPlaybackTranscoding, EnableVideoPlaybackTranscoding

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).
            permissions: Dictionary mapping universal permission names to boolean
                values (keyword-only). Only provided keys are updated.

        Returns:
            True if permissions were successfully updated, False if the user
            was not found on the server.

        Raises:
            MediaClientError: If the client is not initialized (use async context manager).
            MediaClientError: If the permission update fails for reasons other
                than user not found.
        """
        if self._api is None:
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="update_permissions",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
            )

        try:
            # Step 1: Get current user via jellyfin-sdk users.get (Requirement 7.2)
            # jellyfin-sdk lacks type stubs, so returns Any
            user = self._api.users.get(external_user_id)  # pyright: ignore[reportAny]

            if user is None:
                return False

            # Step 2: Get current policy from user (Requirement 7.2)
            # jellyfin-sdk may use Policy or policy attribute
            policy = None
            if hasattr(user, "Policy"):  # pyright: ignore[reportAny]
                policy = user.Policy  # pyright: ignore[reportAny]
            elif hasattr(user, "policy"):  # pyright: ignore[reportAny]
                policy = user.policy  # pyright: ignore[reportAny]

            if policy is None:
                raise MediaClientError(
                    "Failed to retrieve user policy from Jellyfin response",
                    operation="update_permissions",
                    server_url=self.url,
                    cause="User object has no Policy or policy attribute",
                )

            # Step 3: Map universal permissions to Jellyfin policy fields
            # Only update fields that are provided in the permissions dict

            # can_download -> EnableContentDownloading (Requirement 7.3)
            if "can_download" in permissions:
                value = permissions["can_download"]
                if hasattr(policy, "EnableContentDownloading"):  # pyright: ignore[reportAny]
                    policy.EnableContentDownloading = value
                elif hasattr(policy, "enable_content_downloading"):  # pyright: ignore[reportAny]
                    policy.enable_content_downloading = value

            # can_stream -> EnableMediaPlayback (Requirement 7.4)
            if "can_stream" in permissions:
                value = permissions["can_stream"]
                if hasattr(policy, "EnableMediaPlayback"):  # pyright: ignore[reportAny]
                    policy.EnableMediaPlayback = value
                elif hasattr(policy, "enable_media_playback"):  # pyright: ignore[reportAny]
                    policy.enable_media_playback = value

            # can_sync -> EnableSyncTranscoding (Requirement 7.5)
            if "can_sync" in permissions:
                value = permissions["can_sync"]
                if hasattr(policy, "EnableSyncTranscoding"):  # pyright: ignore[reportAny]
                    policy.EnableSyncTranscoding = value
                elif hasattr(policy, "enable_sync_transcoding"):  # pyright: ignore[reportAny]
                    policy.enable_sync_transcoding = value

            # can_transcode -> EnableAudioPlaybackTranscoding, EnableVideoPlaybackTranscoding (Requirement 7.6)
            if "can_transcode" in permissions:
                value = permissions["can_transcode"]
                # Set EnableAudioPlaybackTranscoding
                if hasattr(policy, "EnableAudioPlaybackTranscoding"):  # pyright: ignore[reportAny]
                    policy.EnableAudioPlaybackTranscoding = value
                elif hasattr(policy, "enable_audio_playback_transcoding"):  # pyright: ignore[reportAny]
                    policy.enable_audio_playback_transcoding = value
                # Set EnableVideoPlaybackTranscoding
                if hasattr(policy, "EnableVideoPlaybackTranscoding"):  # pyright: ignore[reportAny]
                    policy.EnableVideoPlaybackTranscoding = value
                elif hasattr(policy, "enable_video_playback_transcoding"):  # pyright: ignore[reportAny]
                    policy.enable_video_playback_transcoding = value

            # Step 4: Update user policy via jellyfin-sdk (Requirement 7.7)
            self._api.users.update_policy(  # pyright: ignore[reportAny]
                external_user_id, policy
            )

            return True

        except MediaClientError:
            # Re-raise our own errors
            raise
        except Exception as exc:
            error_msg = str(exc).lower()
            # Check for user not found error - return False
            if "not found" in error_msg or "404" in error_msg:
                return False

            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to update permissions on Jellyfin server: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc

            # Re-raise other errors as MediaClientError (Requirement 7.8)
            raise MediaClientError(
                f"Failed to update permissions on Jellyfin server: {exc}",
                operation="update_permissions",
                server_url=self.url,
                cause=str(exc),
            ) from exc

    async def list_users(self) -> Sequence[ExternalUser]:
        """List all users from the Jellyfin server.

        Retrieves all user accounts from the server via jellyfin-sdk's
        users.all property and maps them to ExternalUser structs.

        Returns:
            A sequence of ExternalUser objects with external_user_id (Id),
            username (Name), and email (if available, typically None for
            Jellyfin users).

        Raises:
            MediaClientError: If the client is not initialized (use async context manager).
            MediaClientError: If user listing fails due to connection or API errors.
        """
        if self._api is None:
            raise MediaClientError(
                "Client not initialized - use async context manager",
                operation="list_users",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
            )

        try:
            # Retrieve all users via jellyfin-sdk users.all (Requirement 8.2)
            # jellyfin-sdk lacks type stubs, so returns Any
            users = self._api.users.all  # pyright: ignore[reportAny]

            if users is None:
                return []

            # Map Jellyfin users to ExternalUser structs (Requirement 8.3)
            external_users: list[ExternalUser] = []
            for user in users:  # pyright: ignore[reportAny]
                # Extract user ID - jellyfin-sdk may use Id or id attribute
                user_id: str
                if hasattr(user, "Id"):  # pyright: ignore[reportAny]
                    user_id = str(user.Id)  # pyright: ignore[reportAny]
                elif hasattr(user, "id"):  # pyright: ignore[reportAny]
                    user_id = str(user.id)  # pyright: ignore[reportAny]
                else:
                    # Skip users without valid ID
                    continue

                # Extract username - jellyfin-sdk may use Name or name attribute
                username: str
                if hasattr(user, "Name"):  # pyright: ignore[reportAny]
                    username = str(user.Name)  # pyright: ignore[reportAny]
                elif hasattr(user, "name"):  # pyright: ignore[reportAny]
                    username = str(user.name)  # pyright: ignore[reportAny]
                else:
                    # Skip users without valid username
                    continue

                # Jellyfin users typically don't have email addresses
                # The email field is included for protocol compatibility
                external_users.append(
                    ExternalUser(
                        external_user_id=user_id,
                        username=username,
                        email=None,
                    )
                )

            return external_users

        except Exception as exc:
            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to list users from Jellyfin server: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc

            # Re-raise as MediaClientError (Requirement 8.4)
            raise MediaClientError(
                f"Failed to list users from Jellyfin server: {exc}",
                operation="list_users",
                server_url=self.url,
                cause=str(exc),
            ) from exc
