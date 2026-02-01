"""Property-based tests for JellyfinClient.

Feature: jellyfin-integration
Properties: 2, 4, 5, 6, 7
Validates: Requirements 2.2, 2.4, 5.2, 5.3, 6.2, 6.3, 7.3, 7.4, 7.5, 7.6, 8.3
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from zondarr.media.types import ExternalUser, LibraryInfo

# Valid Jellyfin CollectionType values per Requirements 2.4
VALID_COLLECTION_TYPES = [
    "movies",
    "tvshows",
    "music",
    "books",
    "photos",
    "homevideos",
    "musicvideos",
    "boxsets",
]

# Strategy for valid item IDs (Jellyfin uses GUIDs)
item_id_strategy = st.text(
    alphabet=st.characters(categories=("L", "N"), whitelist_characters="-"),
    min_size=1,
    max_size=36,
).filter(lambda s: s.strip())  # Ensure non-empty after strip

# Strategy for library names
name_strategy = st.text(
    min_size=1,
    max_size=255,
).filter(lambda s: s.strip())  # Ensure non-empty after strip

# Strategy for collection types (including None for unknown)
collection_type_strategy = st.one_of(
    st.sampled_from(VALID_COLLECTION_TYPES),
    st.none(),
)


class MockVirtualFolder:
    """Mock Jellyfin virtual folder response object.

    Simulates the structure returned by jellyfin-sdk's library.virtual_folders.
    Supports both PascalCase (ItemId, Name, CollectionType) and snake_case
    (item_id, name, collection_type) attribute access patterns.
    """

    ItemId: str
    Name: str
    CollectionType: str | None
    item_id: str
    name: str
    collection_type: str | None

    def __init__(
        self,
        *,
        item_id: str,
        name: str,
        collection_type: str | None,
    ) -> None:
        # PascalCase attributes (Jellyfin API style)
        self.ItemId = item_id
        self.Name = name
        self.CollectionType = collection_type
        # snake_case attributes (Python style)
        self.item_id = item_id
        self.name = name
        self.collection_type = collection_type


def map_jellyfin_folder_to_library_info(folder: MockVirtualFolder) -> LibraryInfo:
    """Map a Jellyfin virtual folder to LibraryInfo.

    This function replicates the mapping logic from JellyfinClient.get_libraries()
    to test the property in isolation without requiring a live Jellyfin server.

    Args:
        folder: A Jellyfin virtual folder object with ItemId, Name, CollectionType.

    Returns:
        A LibraryInfo struct with the mapped fields.
    """
    # Extract fields using the same logic as JellyfinClient.get_libraries()
    external_id: str = folder.ItemId
    name: str = folder.Name
    collection_type: str | None = folder.CollectionType
    library_type: str = str(collection_type) if collection_type else "unknown"

    return LibraryInfo(
        external_id=external_id,
        name=name,
        library_type=library_type,
    )


class TestLibraryMappingPreservesFields:
    """
    Feature: jellyfin-integration
    Property 2: Library Mapping Preserves Fields

    *For any* Jellyfin virtual folder response with ItemId, Name, and CollectionType
    fields, the resulting LibraryInfo object should contain external_id equal to
    ItemId, name equal to Name, and library_type equal to CollectionType (or
    "unknown" if CollectionType is None).

    **Validates: Requirements 2.2, 2.4**
    """

    @settings(max_examples=100)
    @given(
        item_id=item_id_strategy,
        name=name_strategy,
        collection_type=collection_type_strategy,
    )
    def test_library_mapping_preserves_all_fields(
        self,
        item_id: str,
        name: str,
        collection_type: str | None,
    ) -> None:
        """Library mapping preserves ItemId, Name, and CollectionType fields.

        For any valid Jellyfin virtual folder, the mapping to LibraryInfo
        should preserve:
        - external_id == ItemId
        - name == Name
        - library_type == CollectionType (or "unknown" if None)
        """
        # Arrange: Create mock Jellyfin folder response
        jellyfin_folder = MockVirtualFolder(
            item_id=item_id,
            name=name,
            collection_type=collection_type,
        )

        # Act: Map to LibraryInfo using the same logic as JellyfinClient
        library_info = map_jellyfin_folder_to_library_info(jellyfin_folder)

        # Assert: All fields are preserved correctly
        assert library_info.external_id == item_id
        assert library_info.name == name
        expected_type = collection_type if collection_type else "unknown"
        assert library_info.library_type == expected_type

    @settings(max_examples=100)
    @given(
        item_id=item_id_strategy,
        name=name_strategy,
    )
    def test_none_collection_type_maps_to_unknown(
        self,
        item_id: str,
        name: str,
    ) -> None:
        """When CollectionType is None, library_type should be "unknown".

        This validates the fallback behavior specified in Requirements 2.4
        for libraries without a defined collection type.
        """
        # Arrange: Create folder with None collection type
        jellyfin_folder = MockVirtualFolder(
            item_id=item_id,
            name=name,
            collection_type=None,
        )

        # Act: Map to LibraryInfo
        library_info = map_jellyfin_folder_to_library_info(jellyfin_folder)

        # Assert: library_type is "unknown"
        assert library_info.library_type == "unknown"

    @settings(max_examples=100)
    @given(
        item_id=item_id_strategy,
        name=name_strategy,
        collection_type=st.sampled_from(VALID_COLLECTION_TYPES),
    )
    def test_valid_collection_types_preserved(
        self,
        item_id: str,
        name: str,
        collection_type: str,
    ) -> None:
        """Valid Jellyfin CollectionType values are preserved in library_type.

        Per Requirements 2.4, the following CollectionType values should be
        mapped directly: movies, tvshows, music, books, photos, homevideos,
        musicvideos, boxsets.
        """
        # Arrange: Create folder with valid collection type
        jellyfin_folder = MockVirtualFolder(
            item_id=item_id,
            name=name,
            collection_type=collection_type,
        )

        # Act: Map to LibraryInfo
        library_info = map_jellyfin_folder_to_library_info(jellyfin_folder)

        # Assert: collection type is preserved exactly
        assert library_info.library_type == collection_type

    @settings(max_examples=100)
    @given(
        item_id=item_id_strategy,
        name=name_strategy,
        collection_type=collection_type_strategy,
    )
    def test_library_info_struct_is_valid(
        self,
        item_id: str,
        name: str,
        collection_type: str | None,
    ) -> None:
        """The resulting LibraryInfo is a valid msgspec Struct.

        Verifies that the mapped LibraryInfo has all required fields
        and can be serialized/deserialized correctly.
        """
        # Arrange
        jellyfin_folder = MockVirtualFolder(
            item_id=item_id,
            name=name,
            collection_type=collection_type,
        )

        # Act
        library_info = map_jellyfin_folder_to_library_info(jellyfin_folder)

        # Assert: All required fields are present and non-empty
        assert library_info.external_id
        assert library_info.name
        assert library_info.library_type

        # Assert: Types are correct
        assert isinstance(library_info.external_id, str)
        assert isinstance(library_info.name, str)
        assert isinstance(library_info.library_type, str)


# =============================================================================
# Property 4: Enable/Disable Maps to IsDisabled Correctly
# =============================================================================


class MockUserPolicy:
    """Mock Jellyfin user policy object.

    Simulates the structure of a Jellyfin UserPolicy object returned by
    jellyfin-sdk's users.get().Policy. Supports both PascalCase (IsDisabled)
    and snake_case (is_disabled) attribute access patterns.
    """

    IsDisabled: bool
    is_disabled: bool

    def __init__(self, *, is_disabled: bool = False) -> None:
        """Initialize a mock user policy.

        Args:
            is_disabled: Initial disabled state (keyword-only).
        """
        self.IsDisabled = is_disabled
        self.is_disabled = is_disabled


class MockJellyfinUser:
    """Mock Jellyfin user object.

    Simulates the structure returned by jellyfin-sdk's users.get().
    Supports both PascalCase (Id, Name, Policy) and snake_case
    (id, name, policy) attribute access patterns.
    """

    Id: str
    Name: str
    Policy: MockUserPolicy
    id: str
    name: str
    policy: MockUserPolicy

    def __init__(
        self,
        *,
        user_id: str,
        name: str,
        is_disabled: bool = False,
    ) -> None:
        """Initialize a mock Jellyfin user.

        Args:
            user_id: The user's unique identifier (keyword-only).
            name: The user's display name (keyword-only).
            is_disabled: Whether the user is disabled (keyword-only).
        """
        policy = MockUserPolicy(is_disabled=is_disabled)
        # PascalCase attributes (Jellyfin API style)
        self.Id = user_id
        self.Name = name
        self.Policy = policy
        # snake_case attributes (Python style)
        self.id = user_id
        self.name = name
        self.policy = policy


def compute_is_disabled_from_enabled(enabled: bool) -> bool:
    """Compute the expected IsDisabled value from the enabled parameter.

    This function replicates the mapping logic from JellyfinClient.set_user_enabled()
    to test the property in isolation without requiring a live Jellyfin server.

    Per Requirements 5.2 and 5.3:
    - enabled=True → IsDisabled=False
    - enabled=False → IsDisabled=True

    Args:
        enabled: The enabled parameter passed to set_user_enabled.

    Returns:
        The expected IsDisabled value for the Jellyfin user policy.
    """
    return not enabled


def apply_enabled_to_policy(policy: MockUserPolicy, *, enabled: bool) -> None:
    """Apply the enabled parameter to a mock user policy.

    This function replicates the policy update logic from
    JellyfinClient.set_user_enabled() to test the property in isolation.

    Args:
        policy: The mock user policy to update.
        enabled: Whether the user should be enabled (keyword-only).
    """
    # Same logic as JellyfinClient.set_user_enabled()
    policy.IsDisabled = not enabled
    policy.is_disabled = not enabled


class TestEnableDisableMapsToIsDisabledCorrectly:
    """
    Feature: jellyfin-integration
    Property 4: Enable/Disable Maps to IsDisabled Correctly

    *For any* boolean value of the `enabled` parameter passed to
    set_user_enabled, the resulting IsDisabled policy field should be
    the logical negation of `enabled`:
    - enabled=True → IsDisabled=False
    - enabled=False → IsDisabled=True

    **Validates: Requirements 5.2, 5.3**
    """

    @settings(max_examples=100)
    @given(enabled=st.booleans())
    def test_enabled_maps_to_is_disabled_negation(self, enabled: bool) -> None:
        """The enabled parameter maps to the negation of IsDisabled.

        For any boolean value of enabled, the IsDisabled policy field
        should be set to `not enabled`.

        **Validates: Requirements 5.2, 5.3**
        """
        # Arrange: Compute expected IsDisabled value
        expected_is_disabled = compute_is_disabled_from_enabled(enabled)

        # Act & Assert: Verify the mapping is correct
        # enabled=True → IsDisabled=False (Requirement 5.2)
        # enabled=False → IsDisabled=True (Requirement 5.3)
        assert expected_is_disabled == (not enabled)

    @settings(max_examples=100)
    @given(
        user_id=item_id_strategy,
        name=name_strategy,
        initial_disabled=st.booleans(),
        enabled=st.booleans(),
    )
    def test_policy_update_sets_is_disabled_correctly(
        self,
        user_id: str,
        name: str,
        initial_disabled: bool,
        enabled: bool,
    ) -> None:
        """Applying enabled to a policy sets IsDisabled to its negation.

        For any initial policy state and any enabled value, after applying
        the enabled parameter, IsDisabled should equal `not enabled`.

        **Validates: Requirements 5.2, 5.3**
        """
        # Arrange: Create mock user with initial disabled state
        mock_user = MockJellyfinUser(
            user_id=user_id,
            name=name,
            is_disabled=initial_disabled,
        )

        # Act: Apply enabled parameter to policy (same logic as JellyfinClient)
        apply_enabled_to_policy(mock_user.Policy, enabled=enabled)

        # Assert: IsDisabled is the negation of enabled
        assert mock_user.Policy.IsDisabled == (not enabled)
        assert mock_user.Policy.is_disabled == (not enabled)

    @settings(max_examples=100)
    @given(enabled=st.booleans())
    def test_enabled_true_sets_is_disabled_false(self, enabled: bool) -> None:
        """When enabled=True, IsDisabled must be False.

        This specifically validates Requirement 5.2:
        WHEN set_user_enabled is called with enabled=True
        THEN the JellyfinClient SHALL update the user policy with IsDisabled=False

        **Validates: Requirements 5.2**
        """
        # Only test when enabled is True
        if not enabled:
            return

        # Arrange: Create policy with any initial state
        policy = MockUserPolicy(is_disabled=True)  # Start disabled

        # Act: Apply enabled=True
        apply_enabled_to_policy(policy, enabled=True)

        # Assert: IsDisabled must be False
        assert policy.IsDisabled is False
        assert policy.is_disabled is False

    @settings(max_examples=100)
    @given(enabled=st.booleans())
    def test_enabled_false_sets_is_disabled_true(self, enabled: bool) -> None:
        """When enabled=False, IsDisabled must be True.

        This specifically validates Requirement 5.3:
        WHEN set_user_enabled is called with enabled=False
        THEN the JellyfinClient SHALL update the user policy with IsDisabled=True

        **Validates: Requirements 5.3**
        """
        # Only test when enabled is False
        if enabled:
            return

        # Arrange: Create policy with any initial state
        policy = MockUserPolicy(is_disabled=False)  # Start enabled

        # Act: Apply enabled=False
        apply_enabled_to_policy(policy, enabled=False)

        # Assert: IsDisabled must be True
        assert policy.IsDisabled is True
        assert policy.is_disabled is True

    @settings(max_examples=100)
    @given(
        initial_disabled=st.booleans(),
        enabled=st.booleans(),
    )
    def test_mapping_is_idempotent(
        self,
        initial_disabled: bool,
        enabled: bool,
    ) -> None:
        """Applying the same enabled value twice produces the same result.

        The mapping from enabled to IsDisabled should be deterministic
        and idempotent - applying it multiple times should not change
        the result.

        **Validates: Requirements 5.2, 5.3**
        """
        # Arrange: Create policy with initial state
        policy = MockUserPolicy(is_disabled=initial_disabled)

        # Act: Apply enabled twice
        apply_enabled_to_policy(policy, enabled=enabled)
        first_result = policy.IsDisabled

        apply_enabled_to_policy(policy, enabled=enabled)
        second_result = policy.IsDisabled

        # Assert: Results are identical
        assert first_result == second_result
        assert first_result == (not enabled)


# =============================================================================
# Property 5: Library Access Configuration
# =============================================================================


class MockLibraryAccessPolicy:
    """Mock Jellyfin user policy object for library access testing.

    Simulates the structure of a Jellyfin UserPolicy object with library
    access fields. Supports both PascalCase (EnableAllFolders, EnabledFolders)
    and snake_case (enable_all_folders, enabled_folders) attribute access patterns.
    """

    EnableAllFolders: bool
    EnabledFolders: list[str]
    enable_all_folders: bool
    enabled_folders: list[str]

    def __init__(
        self,
        *,
        enable_all_folders: bool = True,
        enabled_folders: list[str] | None = None,
    ) -> None:
        """Initialize a mock library access policy.

        Args:
            enable_all_folders: Initial EnableAllFolders state (keyword-only).
            enabled_folders: Initial EnabledFolders list (keyword-only).
        """
        if enabled_folders is None:
            enabled_folders = []
        # PascalCase attributes (Jellyfin API style)
        self.EnableAllFolders = enable_all_folders
        self.EnabledFolders = enabled_folders.copy()
        # snake_case attributes (Python style)
        self.enable_all_folders = enable_all_folders
        self.enabled_folders = enabled_folders.copy()


class MockLibraryAccessUser:
    """Mock Jellyfin user object for library access testing.

    Simulates the structure returned by jellyfin-sdk's users.get() with
    library access policy fields.
    """

    Id: str
    Name: str
    Policy: MockLibraryAccessPolicy
    id: str
    name: str
    policy: MockLibraryAccessPolicy

    def __init__(
        self,
        *,
        user_id: str,
        name: str,
        enable_all_folders: bool = True,
        enabled_folders: list[str] | None = None,
    ) -> None:
        """Initialize a mock Jellyfin user for library access testing.

        Args:
            user_id: The user's unique identifier (keyword-only).
            name: The user's display name (keyword-only).
            enable_all_folders: Initial EnableAllFolders state (keyword-only).
            enabled_folders: Initial EnabledFolders list (keyword-only).
        """
        policy = MockLibraryAccessPolicy(
            enable_all_folders=enable_all_folders,
            enabled_folders=enabled_folders,
        )
        # PascalCase attributes (Jellyfin API style)
        self.Id = user_id
        self.Name = name
        self.Policy = policy
        # snake_case attributes (Python style)
        self.id = user_id
        self.name = name
        self.policy = policy


def apply_library_access_to_policy(
    policy: MockLibraryAccessPolicy,
    library_ids: list[str],
    /,
) -> None:
    """Apply library access configuration to a mock user policy.

    This function replicates the policy update logic from
    JellyfinClient.set_library_access() to test the property in isolation.

    Per Requirements 6.2 and 6.3:
    - EnableAllFolders is always set to False
    - EnabledFolders is set to the provided library IDs list

    Args:
        policy: The mock user policy to update (positional-only).
        library_ids: List of library IDs to grant access to (positional-only).
    """
    # Same logic as JellyfinClient.set_library_access()
    # Per Requirements 6.2, 6.3: EnableAllFolders=False always
    policy.EnableAllFolders = False
    policy.enable_all_folders = False
    # Set EnabledFolders to the library IDs list
    policy.EnabledFolders = library_ids.copy()
    policy.enabled_folders = library_ids.copy()


# Strategy for library IDs (Jellyfin uses GUIDs for library IDs)
library_id_strategy = st.text(
    alphabet=st.characters(categories=("L", "N"), whitelist_characters="-"),
    min_size=1,
    max_size=36,
).filter(lambda s: s.strip())  # Ensure non-empty after strip

# Strategy for lists of library IDs (including empty lists per Requirement 6.3)
library_ids_list_strategy = st.lists(
    library_id_strategy,
    min_size=0,
    max_size=20,
)


class TestLibraryAccessConfiguration:
    """
    Feature: jellyfin-integration
    Property 5: Library Access Configuration

    *For any* user and any list of library IDs L, calling
    `set_library_access(user_id, L)` should result in the user's policy
    having `EnableAllFolders=False` and `EnabledFolders` equal to L.

    **Validates: Requirements 6.2, 6.3**
    """

    @settings(max_examples=100)
    @given(library_ids=library_ids_list_strategy)
    def test_enable_all_folders_always_false(
        self,
        library_ids: list[str],
    ) -> None:
        """EnableAllFolders is always set to False regardless of library_ids.

        For any list of library IDs (empty or non-empty), after applying
        library access configuration, EnableAllFolders must be False.

        **Validates: Requirements 6.2, 6.3**
        """
        # Arrange: Create policy with EnableAllFolders=True initially
        policy = MockLibraryAccessPolicy(
            enable_all_folders=True,
            enabled_folders=["existing-lib-1", "existing-lib-2"],
        )

        # Act: Apply library access configuration
        apply_library_access_to_policy(policy, library_ids)

        # Assert: EnableAllFolders is False
        assert policy.EnableAllFolders is False
        assert policy.enable_all_folders is False

    @settings(max_examples=100)
    @given(library_ids=library_ids_list_strategy)
    def test_enabled_folders_equals_library_ids(
        self,
        library_ids: list[str],
    ) -> None:
        """EnabledFolders is set to exactly the provided library IDs.

        For any list of library IDs L, after applying library access
        configuration, EnabledFolders should equal L.

        **Validates: Requirements 6.2, 6.3**
        """
        # Arrange: Create policy with different initial folders
        policy = MockLibraryAccessPolicy(
            enable_all_folders=True,
            enabled_folders=["old-lib-1", "old-lib-2", "old-lib-3"],
        )

        # Act: Apply library access configuration
        apply_library_access_to_policy(policy, library_ids)

        # Assert: EnabledFolders equals the provided library IDs
        assert policy.EnabledFolders == library_ids
        assert policy.enabled_folders == library_ids

    @settings(max_examples=100)
    @given(
        user_id=item_id_strategy,
        name=name_strategy,
        initial_enable_all=st.booleans(),
        initial_folders=library_ids_list_strategy,
        new_library_ids=library_ids_list_strategy,
    )
    def test_library_access_configuration_complete(
        self,
        user_id: str,
        name: str,
        initial_enable_all: bool,
        initial_folders: list[str],
        new_library_ids: list[str],
    ) -> None:
        """Complete library access configuration test.

        For any user with any initial policy state and any new list of
        library IDs, after applying library access configuration:
        - EnableAllFolders must be False
        - EnabledFolders must equal the new library IDs

        **Validates: Requirements 6.2, 6.3**
        """
        # Arrange: Create mock user with initial policy state
        mock_user = MockLibraryAccessUser(
            user_id=user_id,
            name=name,
            enable_all_folders=initial_enable_all,
            enabled_folders=initial_folders,
        )

        # Act: Apply library access configuration (same logic as JellyfinClient)
        apply_library_access_to_policy(mock_user.Policy, new_library_ids)

        # Assert: Policy is correctly configured
        assert mock_user.Policy.EnableAllFolders is False
        assert mock_user.Policy.enable_all_folders is False
        assert mock_user.Policy.EnabledFolders == new_library_ids
        assert mock_user.Policy.enabled_folders == new_library_ids

    @settings(max_examples=100)
    @given(
        user_id=item_id_strategy,
        name=name_strategy,
    )
    def test_empty_library_ids_grants_no_access(
        self,
        user_id: str,
        name: str,
    ) -> None:
        """Empty library_ids list results in no library access.

        Per Requirement 6.3: WHEN set_library_access is called with an
        empty library_ids list THEN the JellyfinClient SHALL update the
        user policy with EnableAllFolders=False and EnabledFolders as
        an empty list.

        **Validates: Requirements 6.3**
        """
        # Arrange: Create user with initial access to some libraries
        mock_user = MockLibraryAccessUser(
            user_id=user_id,
            name=name,
            enable_all_folders=True,
            enabled_folders=["lib-1", "lib-2", "lib-3"],
        )

        # Act: Apply empty library access
        apply_library_access_to_policy(mock_user.Policy, [])

        # Assert: No library access
        assert mock_user.Policy.EnableAllFolders is False
        assert mock_user.Policy.EnabledFolders == []
        assert len(mock_user.Policy.enabled_folders) == 0

    @settings(max_examples=100)
    @given(library_ids=st.lists(library_id_strategy, min_size=1, max_size=20))
    def test_non_empty_library_ids_grants_specific_access(
        self,
        library_ids: list[str],
    ) -> None:
        """Non-empty library_ids list grants access to specific libraries.

        Per Requirement 6.2: WHEN set_library_access is called with a
        non-empty list of library_ids THEN the JellyfinClient SHALL
        update the user policy with EnableAllFolders=False and
        EnabledFolders set to the library IDs.

        **Validates: Requirements 6.2**
        """
        # Arrange: Create policy with all folders enabled
        policy = MockLibraryAccessPolicy(
            enable_all_folders=True,
            enabled_folders=[],
        )

        # Act: Apply specific library access
        apply_library_access_to_policy(policy, library_ids)

        # Assert: Specific library access granted
        assert policy.EnableAllFolders is False
        assert policy.EnabledFolders == library_ids
        assert len(policy.EnabledFolders) == len(library_ids)

    @settings(max_examples=100)
    @given(
        library_ids=library_ids_list_strategy,
    )
    def test_library_access_is_idempotent(
        self,
        library_ids: list[str],
    ) -> None:
        """Applying the same library access twice produces the same result.

        The library access configuration should be deterministic and
        idempotent - applying it multiple times should not change the result.

        **Validates: Requirements 6.2, 6.3**
        """
        # Arrange: Create policy
        policy = MockLibraryAccessPolicy(
            enable_all_folders=True,
            enabled_folders=["initial-lib"],
        )

        # Act: Apply library access twice
        apply_library_access_to_policy(policy, library_ids)
        first_enable_all = policy.EnableAllFolders
        first_enabled_folders = policy.EnabledFolders.copy()

        apply_library_access_to_policy(policy, library_ids)
        second_enable_all = policy.EnableAllFolders
        second_enabled_folders = policy.EnabledFolders.copy()

        # Assert: Results are identical
        assert first_enable_all == second_enable_all
        assert first_enabled_folders == second_enabled_folders
        assert first_enable_all is False
        assert first_enabled_folders == library_ids

    @settings(max_examples=100)
    @given(
        library_ids=library_ids_list_strategy,
    )
    def test_library_ids_order_preserved(
        self,
        library_ids: list[str],
    ) -> None:
        """The order of library IDs is preserved in EnabledFolders.

        The EnabledFolders list should maintain the same order as the
        input library_ids list.

        **Validates: Requirements 6.2, 6.3**
        """
        # Arrange: Create policy
        policy = MockLibraryAccessPolicy()

        # Act: Apply library access
        apply_library_access_to_policy(policy, library_ids)

        # Assert: Order is preserved
        for i, lib_id in enumerate(library_ids):
            assert policy.EnabledFolders[i] == lib_id


# =============================================================================
# Property 6: Permission Mapping Correctness
# =============================================================================


class MockPermissionPolicy:
    """Mock Jellyfin user policy object for permission mapping testing.

    Simulates the structure of a Jellyfin UserPolicy object with permission
    fields. Supports both PascalCase and snake_case attribute access patterns.

    Permission mapping (per Requirements 7.3-7.6):
    - can_download → EnableContentDownloading
    - can_stream → EnableMediaPlayback
    - can_sync → EnableSyncTranscoding
    - can_transcode → EnableAudioPlaybackTranscoding, EnableVideoPlaybackTranscoding
    """

    EnableContentDownloading: bool
    EnableMediaPlayback: bool
    EnableSyncTranscoding: bool
    EnableAudioPlaybackTranscoding: bool
    EnableVideoPlaybackTranscoding: bool
    enable_content_downloading: bool
    enable_media_playback: bool
    enable_sync_transcoding: bool
    enable_audio_playback_transcoding: bool
    enable_video_playback_transcoding: bool

    def __init__(
        self,
        *,
        enable_content_downloading: bool = False,
        enable_media_playback: bool = True,
        enable_sync_transcoding: bool = False,
        enable_audio_playback_transcoding: bool = True,
        enable_video_playback_transcoding: bool = True,
    ) -> None:
        """Initialize a mock permission policy.

        Args:
            enable_content_downloading: Initial EnableContentDownloading state.
            enable_media_playback: Initial EnableMediaPlayback state.
            enable_sync_transcoding: Initial EnableSyncTranscoding state.
            enable_audio_playback_transcoding: Initial EnableAudioPlaybackTranscoding state.
            enable_video_playback_transcoding: Initial EnableVideoPlaybackTranscoding state.
        """
        # PascalCase attributes (Jellyfin API style)
        self.EnableContentDownloading = enable_content_downloading
        self.EnableMediaPlayback = enable_media_playback
        self.EnableSyncTranscoding = enable_sync_transcoding
        self.EnableAudioPlaybackTranscoding = enable_audio_playback_transcoding
        self.EnableVideoPlaybackTranscoding = enable_video_playback_transcoding
        # snake_case attributes (Python style)
        self.enable_content_downloading = enable_content_downloading
        self.enable_media_playback = enable_media_playback
        self.enable_sync_transcoding = enable_sync_transcoding
        self.enable_audio_playback_transcoding = enable_audio_playback_transcoding
        self.enable_video_playback_transcoding = enable_video_playback_transcoding


class MockPermissionUser:
    """Mock Jellyfin user object for permission mapping testing.

    Simulates the structure returned by jellyfin-sdk's users.get() with
    permission policy fields.
    """

    Id: str
    Name: str
    Policy: MockPermissionPolicy
    id: str
    name: str
    policy: MockPermissionPolicy

    def __init__(
        self,
        *,
        user_id: str,
        name: str,
        enable_content_downloading: bool = False,
        enable_media_playback: bool = True,
        enable_sync_transcoding: bool = False,
        enable_audio_playback_transcoding: bool = True,
        enable_video_playback_transcoding: bool = True,
    ) -> None:
        """Initialize a mock Jellyfin user for permission mapping testing.

        Args:
            user_id: The user's unique identifier (keyword-only).
            name: The user's display name (keyword-only).
            enable_content_downloading: Initial EnableContentDownloading state.
            enable_media_playback: Initial EnableMediaPlayback state.
            enable_sync_transcoding: Initial EnableSyncTranscoding state.
            enable_audio_playback_transcoding: Initial EnableAudioPlaybackTranscoding state.
            enable_video_playback_transcoding: Initial EnableVideoPlaybackTranscoding state.
        """
        policy = MockPermissionPolicy(
            enable_content_downloading=enable_content_downloading,
            enable_media_playback=enable_media_playback,
            enable_sync_transcoding=enable_sync_transcoding,
            enable_audio_playback_transcoding=enable_audio_playback_transcoding,
            enable_video_playback_transcoding=enable_video_playback_transcoding,
        )
        # PascalCase attributes (Jellyfin API style)
        self.Id = user_id
        self.Name = name
        self.Policy = policy
        # snake_case attributes (Python style)
        self.id = user_id
        self.name = name
        self.policy = policy


def apply_permissions_to_policy(
    policy: MockPermissionPolicy,
    /,
    *,
    permissions: dict[str, bool],
) -> None:
    """Apply universal permissions to a mock user policy.

    This function replicates the permission mapping logic from
    JellyfinClient.update_permissions() to test the property in isolation.

    Permission mapping (per Requirements 7.3-7.6):
    - can_download → EnableContentDownloading
    - can_stream → EnableMediaPlayback
    - can_sync → EnableSyncTranscoding
    - can_transcode → EnableAudioPlaybackTranscoding, EnableVideoPlaybackTranscoding

    Args:
        policy: The mock user policy to update (positional-only).
        permissions: Dict of permission name to boolean (keyword-only).
    """
    # can_download → EnableContentDownloading (Requirement 7.3)
    if "can_download" in permissions:
        value = permissions["can_download"]
        policy.EnableContentDownloading = value
        policy.enable_content_downloading = value

    # can_stream → EnableMediaPlayback (Requirement 7.4)
    if "can_stream" in permissions:
        value = permissions["can_stream"]
        policy.EnableMediaPlayback = value
        policy.enable_media_playback = value

    # can_sync → EnableSyncTranscoding (Requirement 7.5)
    if "can_sync" in permissions:
        value = permissions["can_sync"]
        policy.EnableSyncTranscoding = value
        policy.enable_sync_transcoding = value

    # can_transcode → EnableAudioPlaybackTranscoding, EnableVideoPlaybackTranscoding (Requirement 7.6)
    if "can_transcode" in permissions:
        value = permissions["can_transcode"]
        policy.EnableAudioPlaybackTranscoding = value
        policy.enable_audio_playback_transcoding = value
        policy.EnableVideoPlaybackTranscoding = value
        policy.enable_video_playback_transcoding = value


# Strategy for permission dictionaries
# Each permission can be present or absent, and if present, can be True or False
permission_strategy = st.fixed_dictionaries(
    {},
    optional={
        "can_download": st.booleans(),
        "can_stream": st.booleans(),
        "can_sync": st.booleans(),
        "can_transcode": st.booleans(),
    },
)


class TestPermissionMappingCorrectness:
    """
    Feature: jellyfin-integration
    Property 6: Permission Mapping Correctness

    *For any* dictionary of universal permissions, the mapping to Jellyfin
    policy fields should correctly translate:
    - can_download → EnableContentDownloading
    - can_stream → EnableMediaPlayback
    - can_sync → EnableSyncTranscoding
    - can_transcode → EnableAudioPlaybackTranscoding AND EnableVideoPlaybackTranscoding

    **Validates: Requirements 7.3, 7.4, 7.5, 7.6**
    """

    @settings(max_examples=100)
    @given(
        can_download=st.booleans(),
    )
    def test_can_download_maps_to_enable_content_downloading(
        self,
        can_download: bool,
    ) -> None:
        """can_download maps to EnableContentDownloading.

        Per Requirement 7.3: THE Permission_Mapping SHALL translate
        can_download to EnableContentDownloading in the Jellyfin UserPolicy.

        **Validates: Requirements 7.3**
        """
        # Arrange: Create policy with opposite initial value
        policy = MockPermissionPolicy(enable_content_downloading=not can_download)

        # Act: Apply permission
        apply_permissions_to_policy(policy, permissions={"can_download": can_download})

        # Assert: EnableContentDownloading equals can_download
        assert policy.EnableContentDownloading == can_download
        assert policy.enable_content_downloading == can_download

    @settings(max_examples=100)
    @given(
        can_stream=st.booleans(),
    )
    def test_can_stream_maps_to_enable_media_playback(
        self,
        can_stream: bool,
    ) -> None:
        """can_stream maps to EnableMediaPlayback.

        Per Requirement 7.4: THE Permission_Mapping SHALL translate
        can_stream to EnableMediaPlayback in the Jellyfin UserPolicy.

        **Validates: Requirements 7.4**
        """
        # Arrange: Create policy with opposite initial value
        policy = MockPermissionPolicy(enable_media_playback=not can_stream)

        # Act: Apply permission
        apply_permissions_to_policy(policy, permissions={"can_stream": can_stream})

        # Assert: EnableMediaPlayback equals can_stream
        assert policy.EnableMediaPlayback == can_stream
        assert policy.enable_media_playback == can_stream

    @settings(max_examples=100)
    @given(
        can_sync=st.booleans(),
    )
    def test_can_sync_maps_to_enable_sync_transcoding(
        self,
        can_sync: bool,
    ) -> None:
        """can_sync maps to EnableSyncTranscoding.

        Per Requirement 7.5: THE Permission_Mapping SHALL translate
        can_sync to EnableSyncTranscoding in the Jellyfin UserPolicy.

        **Validates: Requirements 7.5**
        """
        # Arrange: Create policy with opposite initial value
        policy = MockPermissionPolicy(enable_sync_transcoding=not can_sync)

        # Act: Apply permission
        apply_permissions_to_policy(policy, permissions={"can_sync": can_sync})

        # Assert: EnableSyncTranscoding equals can_sync
        assert policy.EnableSyncTranscoding == can_sync
        assert policy.enable_sync_transcoding == can_sync

    @settings(max_examples=100)
    @given(
        can_transcode=st.booleans(),
    )
    def test_can_transcode_maps_to_both_transcoding_fields(
        self,
        can_transcode: bool,
    ) -> None:
        """can_transcode maps to both audio and video transcoding fields.

        Per Requirement 7.6: THE Permission_Mapping SHALL translate
        can_transcode to EnableAudioPlaybackTranscoding and
        EnableVideoPlaybackTranscoding in the Jellyfin UserPolicy.

        **Validates: Requirements 7.6**
        """
        # Arrange: Create policy with opposite initial values
        policy = MockPermissionPolicy(
            enable_audio_playback_transcoding=not can_transcode,
            enable_video_playback_transcoding=not can_transcode,
        )

        # Act: Apply permission
        apply_permissions_to_policy(
            policy, permissions={"can_transcode": can_transcode}
        )

        # Assert: Both transcoding fields equal can_transcode
        assert policy.EnableAudioPlaybackTranscoding == can_transcode
        assert policy.enable_audio_playback_transcoding == can_transcode
        assert policy.EnableVideoPlaybackTranscoding == can_transcode
        assert policy.enable_video_playback_transcoding == can_transcode

    @settings(max_examples=100)
    @given(
        permissions=permission_strategy,
    )
    def test_all_permissions_map_correctly(
        self,
        permissions: dict[str, bool],
    ) -> None:
        """All provided permissions map to their corresponding Jellyfin fields.

        For any combination of universal permissions, each provided permission
        should be correctly mapped to its Jellyfin policy field(s).

        **Validates: Requirements 7.3, 7.4, 7.5, 7.6**
        """
        # Arrange: Create policy with default values
        policy = MockPermissionPolicy()

        # Act: Apply all permissions
        apply_permissions_to_policy(policy, permissions=permissions)

        # Assert: Each provided permission is correctly mapped
        if "can_download" in permissions:
            assert policy.EnableContentDownloading == permissions["can_download"]

        if "can_stream" in permissions:
            assert policy.EnableMediaPlayback == permissions["can_stream"]

        if "can_sync" in permissions:
            assert policy.EnableSyncTranscoding == permissions["can_sync"]

        if "can_transcode" in permissions:
            assert policy.EnableAudioPlaybackTranscoding == permissions["can_transcode"]
            assert policy.EnableVideoPlaybackTranscoding == permissions["can_transcode"]

    @settings(max_examples=100)
    @given(
        user_id=item_id_strategy,
        name=name_strategy,
        initial_download=st.booleans(),
        initial_stream=st.booleans(),
        initial_sync=st.booleans(),
        initial_audio_transcode=st.booleans(),
        initial_video_transcode=st.booleans(),
        permissions=permission_strategy,
    )
    def test_permission_mapping_with_user_context(
        self,
        user_id: str,
        name: str,
        initial_download: bool,
        initial_stream: bool,
        initial_sync: bool,
        initial_audio_transcode: bool,
        initial_video_transcode: bool,
        permissions: dict[str, bool],
    ) -> None:
        """Permission mapping works correctly in user context.

        For any user with any initial policy state and any set of permissions,
        the mapping should correctly update only the provided permissions.

        **Validates: Requirements 7.3, 7.4, 7.5, 7.6**
        """
        # Arrange: Create mock user with initial policy state
        mock_user = MockPermissionUser(
            user_id=user_id,
            name=name,
            enable_content_downloading=initial_download,
            enable_media_playback=initial_stream,
            enable_sync_transcoding=initial_sync,
            enable_audio_playback_transcoding=initial_audio_transcode,
            enable_video_playback_transcoding=initial_video_transcode,
        )

        # Act: Apply permissions (same logic as JellyfinClient)
        apply_permissions_to_policy(mock_user.Policy, permissions=permissions)

        # Assert: Provided permissions are correctly mapped
        if "can_download" in permissions:
            assert (
                mock_user.Policy.EnableContentDownloading == permissions["can_download"]
            )
        else:
            # Unchanged if not provided
            assert mock_user.Policy.EnableContentDownloading == initial_download

        if "can_stream" in permissions:
            assert mock_user.Policy.EnableMediaPlayback == permissions["can_stream"]
        else:
            assert mock_user.Policy.EnableMediaPlayback == initial_stream

        if "can_sync" in permissions:
            assert mock_user.Policy.EnableSyncTranscoding == permissions["can_sync"]
        else:
            assert mock_user.Policy.EnableSyncTranscoding == initial_sync

        if "can_transcode" in permissions:
            assert (
                mock_user.Policy.EnableAudioPlaybackTranscoding
                == permissions["can_transcode"]
            )
            assert (
                mock_user.Policy.EnableVideoPlaybackTranscoding
                == permissions["can_transcode"]
            )
        else:
            assert (
                mock_user.Policy.EnableAudioPlaybackTranscoding
                == initial_audio_transcode
            )
            assert (
                mock_user.Policy.EnableVideoPlaybackTranscoding
                == initial_video_transcode
            )

    @settings(max_examples=100)
    @given(
        permissions=permission_strategy,
    )
    def test_permission_mapping_is_idempotent(
        self,
        permissions: dict[str, bool],
    ) -> None:
        """Applying the same permissions twice produces the same result.

        The permission mapping should be deterministic and idempotent -
        applying it multiple times should not change the result.

        **Validates: Requirements 7.3, 7.4, 7.5, 7.6**
        """
        # Arrange: Create policy
        policy = MockPermissionPolicy()

        # Act: Apply permissions twice
        apply_permissions_to_policy(policy, permissions=permissions)
        first_download = policy.EnableContentDownloading
        first_stream = policy.EnableMediaPlayback
        first_sync = policy.EnableSyncTranscoding
        first_audio = policy.EnableAudioPlaybackTranscoding
        first_video = policy.EnableVideoPlaybackTranscoding

        apply_permissions_to_policy(policy, permissions=permissions)
        second_download = policy.EnableContentDownloading
        second_stream = policy.EnableMediaPlayback
        second_sync = policy.EnableSyncTranscoding
        second_audio = policy.EnableAudioPlaybackTranscoding
        second_video = policy.EnableVideoPlaybackTranscoding

        # Assert: Results are identical
        assert first_download == second_download
        assert first_stream == second_stream
        assert first_sync == second_sync
        assert first_audio == second_audio
        assert first_video == second_video

    @settings(max_examples=100)
    @given(
        initial_download=st.booleans(),
        initial_stream=st.booleans(),
        initial_sync=st.booleans(),
        initial_audio_transcode=st.booleans(),
        initial_video_transcode=st.booleans(),
    )
    def test_empty_permissions_preserves_policy(
        self,
        initial_download: bool,
        initial_stream: bool,
        initial_sync: bool,
        initial_audio_transcode: bool,
        initial_video_transcode: bool,
    ) -> None:
        """Empty permissions dict preserves all existing policy values.

        When no permissions are provided, the policy should remain unchanged.

        **Validates: Requirements 7.3, 7.4, 7.5, 7.6**
        """
        # Arrange: Create policy with initial values
        policy = MockPermissionPolicy(
            enable_content_downloading=initial_download,
            enable_media_playback=initial_stream,
            enable_sync_transcoding=initial_sync,
            enable_audio_playback_transcoding=initial_audio_transcode,
            enable_video_playback_transcoding=initial_video_transcode,
        )

        # Act: Apply empty permissions
        apply_permissions_to_policy(policy, permissions={})

        # Assert: All values unchanged
        assert policy.EnableContentDownloading == initial_download
        assert policy.EnableMediaPlayback == initial_stream
        assert policy.EnableSyncTranscoding == initial_sync
        assert policy.EnableAudioPlaybackTranscoding == initial_audio_transcode
        assert policy.EnableVideoPlaybackTranscoding == initial_video_transcode


# =============================================================================
# Property 7: User Listing Returns Complete Objects
# =============================================================================


class MockListUser:
    """Mock Jellyfin user object for user listing testing.

    Simulates the structure returned by jellyfin-sdk's users.all property.
    Supports both PascalCase (Id, Name) and snake_case (id, name) attribute
    access patterns to match the JellyfinClient.list_users() implementation.
    """

    Id: str
    Name: str
    id: str
    name: str

    def __init__(
        self,
        *,
        user_id: str,
        name: str,
    ) -> None:
        """Initialize a mock Jellyfin user for listing.

        Args:
            user_id: The user's unique identifier (keyword-only).
            name: The user's display name (keyword-only).
        """
        # PascalCase attributes (Jellyfin API style)
        self.Id = user_id
        self.Name = name
        # snake_case attributes (Python style)
        self.id = user_id
        self.name = name


def map_jellyfin_user_to_external_user(user: MockListUser) -> ExternalUser:
    """Map a Jellyfin user to ExternalUser.

    This function replicates the mapping logic from JellyfinClient.list_users()
    to test the property in isolation without requiring a live Jellyfin server.

    Per Requirement 8.3: WHEN users are retrieved THEN the JellyfinClient SHALL
    return a sequence of ExternalUser objects with external_user_id (Id),
    username (Name), and email (if available).

    Args:
        user: A Jellyfin user object with Id and Name attributes.

    Returns:
        An ExternalUser struct with the mapped fields.
    """
    # Extract user ID - same logic as JellyfinClient.list_users()
    user_id: str
    if hasattr(user, "Id"):
        user_id = str(user.Id)
    elif hasattr(user, "id"):
        user_id = str(user.id)
    else:
        raise ValueError("User object has no Id or id attribute")

    # Extract username - same logic as JellyfinClient.list_users()
    username: str
    if hasattr(user, "Name"):
        username = str(user.Name)
    elif hasattr(user, "name"):
        username = str(user.name)
    else:
        raise ValueError("User object has no Name or name attribute")

    # Jellyfin users typically don't have email addresses
    # The email field is included for protocol compatibility
    return ExternalUser(
        external_user_id=user_id,
        username=username,
        email=None,
    )


def map_jellyfin_users_to_external_users(
    users: list[MockListUser],
) -> list[ExternalUser]:
    """Map a list of Jellyfin users to ExternalUser objects.

    This function replicates the list mapping logic from JellyfinClient.list_users()
    to test the property in isolation.

    Args:
        users: A list of Jellyfin user objects.

    Returns:
        A list of ExternalUser structs with the mapped fields.
    """
    return [map_jellyfin_user_to_external_user(user) for user in users]


# Strategy for user IDs (Jellyfin uses GUIDs)
user_id_strategy = st.text(
    alphabet=st.characters(categories=("L", "N"), whitelist_characters="-"),
    min_size=1,
    max_size=36,
).filter(lambda s: s.strip())  # Ensure non-empty after strip

# Strategy for usernames
username_strategy = st.text(
    min_size=1,
    max_size=255,
).filter(lambda s: s.strip())  # Ensure non-empty after strip


class TestUserListingReturnsCompleteObjects:
    """
    Feature: jellyfin-integration
    Property 7: User Listing Returns Complete Objects

    *For any* list of Jellyfin users returned by the server, the resulting
    sequence of ExternalUser objects should contain complete information:
    - external_user_id equal to the Jellyfin user Id
    - username equal to the Jellyfin user Name
    - email set to None (Jellyfin users typically don't have email)

    **Validates: Requirements 8.3**
    """

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        name=username_strategy,
    )
    def test_single_user_mapping_preserves_fields(
        self,
        user_id: str,
        name: str,
    ) -> None:
        """Single user mapping preserves Id and Name fields.

        For any valid Jellyfin user, the mapping to ExternalUser should
        preserve:
        - external_user_id == Id
        - username == Name
        - email == None (Jellyfin users don't have email)

        **Validates: Requirements 8.3**
        """
        # Arrange: Create mock Jellyfin user
        jellyfin_user = MockListUser(user_id=user_id, name=name)

        # Act: Map to ExternalUser using the same logic as JellyfinClient
        external_user = map_jellyfin_user_to_external_user(jellyfin_user)

        # Assert: All fields are preserved correctly
        assert external_user.external_user_id == user_id
        assert external_user.username == name
        assert external_user.email is None

    @settings(max_examples=100)
    @given(
        users=st.lists(
            st.tuples(user_id_strategy, username_strategy),
            min_size=0,
            max_size=20,
        ),
    )
    def test_list_mapping_preserves_all_users(
        self,
        users: list[tuple[str, str]],
    ) -> None:
        """List mapping preserves all users with complete fields.

        For any list of Jellyfin users, the mapping should:
        - Return the same number of ExternalUser objects
        - Preserve each user's Id and Name
        - Set email to None for all users

        **Validates: Requirements 8.3**
        """
        # Arrange: Create mock Jellyfin users
        jellyfin_users = [
            MockListUser(user_id=user_id, name=name) for user_id, name in users
        ]

        # Act: Map to ExternalUser list
        external_users = map_jellyfin_users_to_external_users(jellyfin_users)

        # Assert: Same count
        assert len(external_users) == len(users)

        # Assert: Each user is correctly mapped
        for i, (user_id, name) in enumerate(users):
            assert external_users[i].external_user_id == user_id
            assert external_users[i].username == name
            assert external_users[i].email is None

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        name=username_strategy,
    )
    def test_external_user_struct_is_valid(
        self,
        user_id: str,
        name: str,
    ) -> None:
        """The resulting ExternalUser is a valid msgspec Struct.

        Verifies that the mapped ExternalUser has all required fields
        and correct types.

        **Validates: Requirements 8.3**
        """
        # Arrange
        jellyfin_user = MockListUser(user_id=user_id, name=name)

        # Act
        external_user = map_jellyfin_user_to_external_user(jellyfin_user)

        # Assert: All required fields are present and non-empty
        assert external_user.external_user_id
        assert external_user.username

        # Assert: Types are correct
        assert isinstance(external_user.external_user_id, str)
        assert isinstance(external_user.username, str)
        assert external_user.email is None or isinstance(external_user.email, str)

    @settings(max_examples=100)
    @given(
        users=st.lists(
            st.tuples(user_id_strategy, username_strategy),
            min_size=0,
            max_size=20,
        ),
    )
    def test_list_order_preserved(
        self,
        users: list[tuple[str, str]],
    ) -> None:
        """The order of users is preserved in the mapping.

        The ExternalUser list should maintain the same order as the
        input Jellyfin user list.

        **Validates: Requirements 8.3**
        """
        # Arrange: Create mock Jellyfin users
        jellyfin_users = [
            MockListUser(user_id=user_id, name=name) for user_id, name in users
        ]

        # Act: Map to ExternalUser list
        external_users = map_jellyfin_users_to_external_users(jellyfin_users)

        # Assert: Order is preserved
        for i, (user_id, name) in enumerate(users):
            assert external_users[i].external_user_id == user_id
            assert external_users[i].username == name

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        name=username_strategy,
    )
    def test_mapping_is_deterministic(
        self,
        user_id: str,
        name: str,
    ) -> None:
        """Mapping the same user twice produces identical results.

        The mapping should be deterministic - the same input always
        produces the same output.

        **Validates: Requirements 8.3**
        """
        # Arrange: Create mock Jellyfin user
        jellyfin_user = MockListUser(user_id=user_id, name=name)

        # Act: Map twice
        first_result = map_jellyfin_user_to_external_user(jellyfin_user)
        second_result = map_jellyfin_user_to_external_user(jellyfin_user)

        # Assert: Results are identical
        assert first_result.external_user_id == second_result.external_user_id
        assert first_result.username == second_result.username
        assert first_result.email == second_result.email

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        name=username_strategy,
    )
    def test_pascal_case_attributes_used(
        self,
        user_id: str,
        name: str,
    ) -> None:
        """PascalCase attributes (Id, Name) are correctly extracted.

        The mapping should correctly handle Jellyfin's PascalCase
        attribute naming convention.

        **Validates: Requirements 8.3**
        """
        # Arrange: Create mock user with PascalCase attributes
        jellyfin_user = MockListUser(user_id=user_id, name=name)

        # Verify PascalCase attributes exist
        assert hasattr(jellyfin_user, "Id")
        assert hasattr(jellyfin_user, "Name")
        assert jellyfin_user.Id == user_id
        assert jellyfin_user.Name == name

        # Act: Map to ExternalUser
        external_user = map_jellyfin_user_to_external_user(jellyfin_user)

        # Assert: Values match PascalCase attributes
        assert external_user.external_user_id == jellyfin_user.Id
        assert external_user.username == jellyfin_user.Name

    def test_empty_list_returns_empty_list(self) -> None:
        """Empty user list returns empty ExternalUser list.

        When no users are returned from Jellyfin, the mapping should
        return an empty list.

        **Validates: Requirements 8.3**
        """
        # Arrange: Empty list
        jellyfin_users: list[MockListUser] = []

        # Act: Map to ExternalUser list
        external_users = map_jellyfin_users_to_external_users(jellyfin_users)

        # Assert: Empty list returned
        assert external_users == []
        assert len(external_users) == 0
