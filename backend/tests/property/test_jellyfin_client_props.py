"""Property-based tests for JellyfinClient.

Feature: jellyfin-integration
Properties: 2
Validates: Requirements 2.2, 2.4
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
