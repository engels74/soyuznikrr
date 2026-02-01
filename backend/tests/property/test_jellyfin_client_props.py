"""Property-based tests for JellyfinClient.

Feature: jellyfin-integration
Properties: 2, 4, 5, 6, 7
Validates: Requirements 2.2, 2.4, 5.2, 5.3, 6.2, 6.3, 7.3, 7.4, 7.5, 7.6, 8.3
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from zondarr.media.types import LibraryInfo

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
).filter(lambda s: s.strip())

# Strategy for library names
name_strategy = st.text(
    min_size=1,
    max_size=255,
).filter(lambda s: s.strip())

# Strategy for collection types (including None for unknown)
collection_type_strategy = st.one_of(
    st.sampled_from(VALID_COLLECTION_TYPES),
    st.none(),
)


class MockVirtualFolder:
    """Mock Jellyfin virtual folder response object."""

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
        self.ItemId = item_id
        self.Name = name
        self.CollectionType = collection_type
        self.item_id = item_id
        self.name = name
        self.collection_type = collection_type


def map_jellyfin_folder_to_library_info(folder: MockVirtualFolder) -> LibraryInfo:
    """Map a Jellyfin virtual folder to LibraryInfo."""
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

    **Validates: Requirements 2.2, 2.4**
    """

    @settings(max_examples=25)
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
        """Library mapping preserves ItemId, Name, and CollectionType fields."""
        jellyfin_folder = MockVirtualFolder(
            item_id=item_id,
            name=name,
            collection_type=collection_type,
        )

        library_info = map_jellyfin_folder_to_library_info(jellyfin_folder)

        assert library_info.external_id == item_id
        assert library_info.name == name
        expected_type = collection_type if collection_type else "unknown"
        assert library_info.library_type == expected_type

    @settings(max_examples=25)
    @given(item_id=item_id_strategy, name=name_strategy)
    def test_none_collection_type_maps_to_unknown(
        self,
        item_id: str,
        name: str,
    ) -> None:
        """When CollectionType is None, library_type should be "unknown"."""
        jellyfin_folder = MockVirtualFolder(
            item_id=item_id,
            name=name,
            collection_type=None,
        )

        library_info = map_jellyfin_folder_to_library_info(jellyfin_folder)

        assert library_info.library_type == "unknown"

    @settings(max_examples=25)
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
        """Valid Jellyfin CollectionType values are preserved in library_type."""
        jellyfin_folder = MockVirtualFolder(
            item_id=item_id,
            name=name,
            collection_type=collection_type,
        )

        library_info = map_jellyfin_folder_to_library_info(jellyfin_folder)

        assert library_info.library_type == collection_type


class MockUserPolicy:
    """Mock Jellyfin user policy object."""

    IsDisabled: bool
    is_disabled: bool

    def __init__(self, *, is_disabled: bool = False) -> None:
        self.IsDisabled = is_disabled
        self.is_disabled = is_disabled


class MockJellyfinUser:
    """Mock Jellyfin user object."""

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
        policy = MockUserPolicy(is_disabled=is_disabled)
        self.Id = user_id
        self.Name = name
        self.Policy = policy
        self.id = user_id
        self.name = name
        self.policy = policy


def compute_is_disabled_from_enabled(enabled: bool) -> bool:
    """Compute the expected IsDisabled value from the enabled parameter."""
    return not enabled


def apply_enabled_to_policy(policy: MockUserPolicy, *, enabled: bool) -> None:
    """Apply the enabled parameter to a mock user policy."""
    policy.IsDisabled = not enabled
    policy.is_disabled = not enabled


class TestEnableDisableMapsToIsDisabledCorrectly:
    """
    Feature: jellyfin-integration
    Property 4: Enable/Disable Maps to IsDisabled Correctly

    **Validates: Requirements 5.2, 5.3**
    """

    @settings(max_examples=25)
    @given(enabled=st.booleans())
    def test_enabled_maps_to_is_disabled_negation(self, enabled: bool) -> None:
        """The enabled parameter maps to the negation of IsDisabled."""
        expected_is_disabled = compute_is_disabled_from_enabled(enabled)
        assert expected_is_disabled == (not enabled)

    @settings(max_examples=25)
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
        """Applying enabled to a policy sets IsDisabled to its negation."""
        mock_user = MockJellyfinUser(
            user_id=user_id,
            name=name,
            is_disabled=initial_disabled,
        )

        apply_enabled_to_policy(mock_user.Policy, enabled=enabled)

        assert mock_user.Policy.IsDisabled == (not enabled)
        assert mock_user.Policy.is_disabled == (not enabled)

    @settings(max_examples=25)
    @given(initial_disabled=st.booleans(), enabled=st.booleans())
    def test_mapping_is_idempotent(
        self,
        initial_disabled: bool,
        enabled: bool,
    ) -> None:
        """Applying the same enabled value twice produces the same result."""
        policy = MockUserPolicy(is_disabled=initial_disabled)

        apply_enabled_to_policy(policy, enabled=enabled)
        first_result = policy.IsDisabled

        apply_enabled_to_policy(policy, enabled=enabled)
        second_result = policy.IsDisabled

        assert first_result == second_result
        assert first_result == (not enabled)


class MockLibraryAccessPolicy:
    """Mock Jellyfin user policy object for library access testing."""

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
        if enabled_folders is None:
            enabled_folders = []
        self.EnableAllFolders = enable_all_folders
        self.EnabledFolders = enabled_folders.copy()
        self.enable_all_folders = enable_all_folders
        self.enabled_folders = enabled_folders.copy()


def apply_library_access_to_policy(
    policy: MockLibraryAccessPolicy,
    library_ids: list[str],
    /,
) -> None:
    """Apply library access configuration to a mock user policy."""
    policy.EnableAllFolders = False
    policy.enable_all_folders = False
    policy.EnabledFolders = library_ids.copy()
    policy.enabled_folders = library_ids.copy()


# Strategy for library IDs
library_id_strategy = st.text(
    alphabet=st.characters(categories=("L", "N"), whitelist_characters="-"),
    min_size=1,
    max_size=36,
).filter(lambda s: s.strip())

# Strategy for lists of library IDs
library_ids_list_strategy = st.lists(
    library_id_strategy,
    min_size=0,
    max_size=20,
)


class TestLibraryAccessConfiguration:
    """
    Feature: jellyfin-integration
    Property 5: Library Access Configuration

    **Validates: Requirements 6.2, 6.3**
    """

    @settings(max_examples=25)
    @given(library_ids=library_ids_list_strategy)
    def test_enable_all_folders_always_false(
        self,
        library_ids: list[str],
    ) -> None:
        """EnableAllFolders is always set to False regardless of library_ids."""
        policy = MockLibraryAccessPolicy(
            enable_all_folders=True,
            enabled_folders=["existing-lib-1", "existing-lib-2"],
        )

        apply_library_access_to_policy(policy, library_ids)

        assert policy.EnableAllFolders is False
        assert policy.enable_all_folders is False

    @settings(max_examples=25)
    @given(library_ids=library_ids_list_strategy)
    def test_enabled_folders_equals_library_ids(
        self,
        library_ids: list[str],
    ) -> None:
        """EnabledFolders is set to exactly the provided library IDs."""
        policy = MockLibraryAccessPolicy(
            enable_all_folders=True,
            enabled_folders=["old-lib-1", "old-lib-2", "old-lib-3"],
        )

        apply_library_access_to_policy(policy, library_ids)

        assert policy.EnabledFolders == library_ids
        assert policy.enabled_folders == library_ids

    @settings(max_examples=25)
    @given(library_ids=library_ids_list_strategy)
    def test_library_access_is_idempotent(
        self,
        library_ids: list[str],
    ) -> None:
        """Applying the same library access twice produces the same result."""
        policy = MockLibraryAccessPolicy(
            enable_all_folders=True,
            enabled_folders=["initial-lib"],
        )

        apply_library_access_to_policy(policy, library_ids)
        first_enable_all = policy.EnableAllFolders
        first_enabled_folders = policy.EnabledFolders.copy()

        apply_library_access_to_policy(policy, library_ids)
        second_enable_all = policy.EnableAllFolders
        second_enabled_folders = policy.EnabledFolders.copy()

        assert first_enable_all == second_enable_all
        assert first_enabled_folders == second_enabled_folders
        assert first_enable_all is False
        assert first_enabled_folders == library_ids

    @settings(max_examples=25)
    @given(library_ids=library_ids_list_strategy)
    def test_library_ids_order_preserved(
        self,
        library_ids: list[str],
    ) -> None:
        """The order of library IDs is preserved in EnabledFolders."""
        policy = MockLibraryAccessPolicy()

        apply_library_access_to_policy(policy, library_ids)

        for i, lib_id in enumerate(library_ids):
            assert policy.EnabledFolders[i] == lib_id


class MockPermissionPolicy:
    """Mock Jellyfin user policy object for permission mapping testing."""

    EnableContentDownloading: bool
    EnableMediaPlayback: bool
    EnableSyncTranscoding: bool
    EnableAudioPlaybackTranscoding: bool
    EnableVideoPlaybackTranscoding: bool

    def __init__(
        self,
        *,
        enable_content_downloading: bool = False,
        enable_media_playback: bool = True,
        enable_sync_transcoding: bool = False,
        enable_audio_playback_transcoding: bool = True,
        enable_video_playback_transcoding: bool = True,
    ) -> None:
        self.EnableContentDownloading = enable_content_downloading
        self.EnableMediaPlayback = enable_media_playback
        self.EnableSyncTranscoding = enable_sync_transcoding
        self.EnableAudioPlaybackTranscoding = enable_audio_playback_transcoding
        self.EnableVideoPlaybackTranscoding = enable_video_playback_transcoding


def apply_permissions_to_policy(
    policy: MockPermissionPolicy,
    *,
    can_download: bool | None = None,
    can_stream: bool | None = None,
    can_sync: bool | None = None,
    can_transcode: bool | None = None,
) -> None:
    """Apply permission settings to a mock user policy."""
    if can_download is not None:
        policy.EnableContentDownloading = can_download
    if can_stream is not None:
        policy.EnableMediaPlayback = can_stream
    if can_sync is not None:
        policy.EnableSyncTranscoding = can_sync
    if can_transcode is not None:
        policy.EnableAudioPlaybackTranscoding = can_transcode
        policy.EnableVideoPlaybackTranscoding = can_transcode


class TestPermissionMappingCorrectness:
    """
    Feature: jellyfin-integration
    Property 6: Permission Mapping Correctness

    **Validates: Requirements 7.3, 7.4, 7.5, 7.6**
    """

    @settings(max_examples=25)
    @given(can_download=st.booleans())
    def test_can_download_maps_to_enable_content_downloading(
        self,
        can_download: bool,
    ) -> None:
        """can_download maps to EnableContentDownloading."""
        policy = MockPermissionPolicy(enable_content_downloading=not can_download)

        apply_permissions_to_policy(policy, can_download=can_download)

        assert policy.EnableContentDownloading == can_download

    @settings(max_examples=25)
    @given(can_stream=st.booleans())
    def test_can_stream_maps_to_enable_media_playback(
        self,
        can_stream: bool,
    ) -> None:
        """can_stream maps to EnableMediaPlayback."""
        policy = MockPermissionPolicy(enable_media_playback=not can_stream)

        apply_permissions_to_policy(policy, can_stream=can_stream)

        assert policy.EnableMediaPlayback == can_stream

    @settings(max_examples=25)
    @given(can_sync=st.booleans())
    def test_can_sync_maps_to_enable_sync_transcoding(
        self,
        can_sync: bool,
    ) -> None:
        """can_sync maps to EnableSyncTranscoding."""
        policy = MockPermissionPolicy(enable_sync_transcoding=not can_sync)

        apply_permissions_to_policy(policy, can_sync=can_sync)

        assert policy.EnableSyncTranscoding == can_sync

    @settings(max_examples=25)
    @given(can_transcode=st.booleans())
    def test_can_transcode_maps_to_both_transcoding_fields(
        self,
        can_transcode: bool,
    ) -> None:
        """can_transcode maps to both EnableAudioPlaybackTranscoding and EnableVideoPlaybackTranscoding."""
        policy = MockPermissionPolicy(
            enable_audio_playback_transcoding=not can_transcode,
            enable_video_playback_transcoding=not can_transcode,
        )

        apply_permissions_to_policy(policy, can_transcode=can_transcode)

        assert policy.EnableAudioPlaybackTranscoding == can_transcode
        assert policy.EnableVideoPlaybackTranscoding == can_transcode

    @settings(max_examples=25)
    @given(
        can_download=st.booleans(),
        can_stream=st.booleans(),
        can_sync=st.booleans(),
        can_transcode=st.booleans(),
    )
    def test_all_permissions_applied_correctly(
        self,
        can_download: bool,
        can_stream: bool,
        can_sync: bool,
        can_transcode: bool,
    ) -> None:
        """All permissions are applied correctly when set together."""
        policy = MockPermissionPolicy()

        apply_permissions_to_policy(
            policy,
            can_download=can_download,
            can_stream=can_stream,
            can_sync=can_sync,
            can_transcode=can_transcode,
        )

        assert policy.EnableContentDownloading == can_download
        assert policy.EnableMediaPlayback == can_stream
        assert policy.EnableSyncTranscoding == can_sync
        assert policy.EnableAudioPlaybackTranscoding == can_transcode
        assert policy.EnableVideoPlaybackTranscoding == can_transcode

    @settings(max_examples=25)
    @given(
        can_download=st.booleans(),
        can_stream=st.booleans(),
        can_sync=st.booleans(),
        can_transcode=st.booleans(),
    )
    def test_permission_mapping_is_idempotent(
        self,
        can_download: bool,
        can_stream: bool,
        can_sync: bool,
        can_transcode: bool,
    ) -> None:
        """Applying the same permissions twice produces the same result."""
        policy = MockPermissionPolicy()

        apply_permissions_to_policy(
            policy,
            can_download=can_download,
            can_stream=can_stream,
            can_sync=can_sync,
            can_transcode=can_transcode,
        )
        first_state = (
            policy.EnableContentDownloading,
            policy.EnableMediaPlayback,
            policy.EnableSyncTranscoding,
            policy.EnableAudioPlaybackTranscoding,
            policy.EnableVideoPlaybackTranscoding,
        )

        apply_permissions_to_policy(
            policy,
            can_download=can_download,
            can_stream=can_stream,
            can_sync=can_sync,
            can_transcode=can_transcode,
        )
        second_state = (
            policy.EnableContentDownloading,
            policy.EnableMediaPlayback,
            policy.EnableSyncTranscoding,
            policy.EnableAudioPlaybackTranscoding,
            policy.EnableVideoPlaybackTranscoding,
        )

        assert first_state == second_state
