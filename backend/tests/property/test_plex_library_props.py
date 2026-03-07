"""Property-based tests for PlexClient library retrieval and access.

Feature: plex-integration
Properties: Library Retrieval Produces Valid Structs, Library Access Update Return Value Correctness
"""

from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from .conftest import (
    MockLibrarySection,
    MockLibraryWithSections,
    MockMyPlexAccount,
    MockMyPlexUserWithHome,
    MockPlexServer,
    api_key_strategy,
    library_title_strategy,
    library_type_strategy,
    section_key_strategy,
    url_strategy,
    username_strategy,
)


class MockMyPlexAccountWithLibraryAccess:
    """Mock MyPlexAccount that supports user listing and library access updates."""

    _users: list[MockMyPlexUserWithHome]
    _update_friend_error: Exception | None
    update_friend_calls: list[dict[str, object]]

    def __init__(
        self,
        *,
        users: list[MockMyPlexUserWithHome] | None = None,
        update_friend_error: Exception | None = None,
    ) -> None:
        self._users = users or []
        self._update_friend_error = update_friend_error
        self.update_friend_calls = []

    def users(self) -> list[MockMyPlexUserWithHome]:
        """Return the list of mock users."""
        return self._users

    def updateFriend(
        self, user: object, server: object, sections: list[object]
    ) -> None:
        """Mock updateFriend method."""
        if self._update_friend_error is not None:
            raise self._update_friend_error
        self.update_friend_calls.append(
            {"user": user, "server": server, "sections": sections}
        )


class TestLibraryRetrievalProducesValidStructs:
    """
    Feature: plex-integration
    Property 3: Library Retrieval Produces Valid Structs

    For any connected PlexClient with accessible libraries, get_libraries()
    should return a sequence where each element is a valid LibraryInfo with
    non-empty external_id, name, and library_type fields.
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        sections=st.lists(
            st.tuples(
                section_key_strategy, library_title_strategy, library_type_strategy
            ),
            min_size=0,
            max_size=10,
        ),
    )
    @pytest.mark.asyncio
    async def test_get_libraries_returns_valid_library_info(
        self,
        url: str,
        api_key: str,
        sections: list[tuple[int, str, str]],
    ) -> None:
        """get_libraries returns valid LibraryInfo structs for each section."""
        from zondarr.media.providers.plex.client import PlexClient
        from zondarr.media.types import LibraryInfo

        mock_server = MockPlexServer(url, api_key, account=MockMyPlexAccount())
        mock_server.library._sections = [  # pyright: ignore[reportPrivateUsage]
            MockLibrarySection(key=key, title=title, section_type=lib_type)
            for key, title, lib_type in sections
        ]

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                libraries = await client.get_libraries()

                # Should return same number of libraries as sections
                assert len(libraries) == len(sections)

                # Each library should be a valid LibraryInfo
                for lib in libraries:
                    assert isinstance(lib, LibraryInfo)
                    assert lib.external_id  # non-empty
                    assert lib.name  # non-empty
                    assert lib.library_type  # non-empty

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        key=section_key_strategy,
        title=library_title_strategy,
        lib_type=library_type_strategy,
    )
    @pytest.mark.asyncio
    async def test_get_libraries_maps_fields_correctly(
        self,
        url: str,
        api_key: str,
        key: int,
        title: str,
        lib_type: str,
    ) -> None:
        """get_libraries maps section key→external_id, title→name, type→library_type."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_server = MockPlexServer(url, api_key, account=MockMyPlexAccount())
        mock_server.library._sections = [  # pyright: ignore[reportPrivateUsage]
            MockLibrarySection(key=key, title=title, section_type=lib_type)
        ]

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                libraries = await client.get_libraries()

                assert len(libraries) == 1
                lib = libraries[0]
                assert lib.external_id == str(key)
                assert lib.name == title
                assert lib.library_type == lib_type

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_get_libraries_returns_empty_for_no_sections(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """get_libraries returns empty sequence when server has no sections."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_server = MockPlexServer(url, api_key, account=MockMyPlexAccount())
        mock_server.library._sections = []  # pyright: ignore[reportPrivateUsage]

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                libraries = await client.get_libraries()
                assert len(libraries) == 0

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_get_libraries_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """get_libraries raises MediaClientError when client is not initialized."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _server is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.get_libraries()

        assert exc_info.value.operation == "get_libraries"
        assert exc_info.value.server_url == url


class TestLibraryAccessUpdateReturnValueCorrectness:
    """
    Feature: plex-integration
    Property 8: Library Access Update Return Value Correctness

    For any connected PlexClient, valid user identifier, and library ID list,
    set_library_access() should return True if the user exists and access was
    updated, False if the user was not found.
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
        library_ids=st.lists(
            st.integers(min_value=1, max_value=100), min_size=1, max_size=5
        ),
    )
    @pytest.mark.asyncio
    async def test_set_library_access_returns_true_for_friend(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
        library_ids: list[int],
    ) -> None:
        """set_library_access returns True when Friend's access is updated."""
        from zondarr.media.providers.plex.client import PlexClient

        # Create a Friend user
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithLibraryAccess(users=[mock_user])

        # Create library sections
        sections = [
            MockLibrarySection(
                key=lib_id, title=f"Library {lib_id}", section_type="movie"
            )
            for lib_id in library_ids
        ]

        mock_server = MockPlexServer(
            url,
            api_key,
            account=mock_account,
            library=MockLibraryWithSections(sections),
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.set_library_access(
                    str(user_id), [str(lib_id) for lib_id in library_ids]
                )

                assert result is True
                assert len(mock_account.update_friend_calls) == 1

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
        library_ids=st.lists(
            st.integers(min_value=1, max_value=100), min_size=1, max_size=5
        ),
    )
    @pytest.mark.asyncio
    async def test_set_library_access_returns_true_for_home_user(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
        library_ids: list[int],
    ) -> None:
        """set_library_access returns True when Home User's access is updated."""
        from zondarr.media.providers.plex.client import PlexClient

        # Create a Home User
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=None, home=True
        )
        mock_account = MockMyPlexAccountWithLibraryAccess(users=[mock_user])

        # Create library sections
        sections = [
            MockLibrarySection(
                key=lib_id, title=f"Library {lib_id}", section_type="movie"
            )
            for lib_id in library_ids
        ]

        mock_server = MockPlexServer(
            url,
            api_key,
            account=mock_account,
            library=MockLibraryWithSections(sections),
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.set_library_access(
                    str(user_id), [str(lib_id) for lib_id in library_ids]
                )

                assert result is True
                assert len(mock_account.update_friend_calls) == 1

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_set_library_access_returns_false_when_user_not_found(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """set_library_access returns False when user is not found."""
        from zondarr.media.providers.plex.client import PlexClient

        # Empty user list - user won't be found
        mock_account = MockMyPlexAccountWithLibraryAccess(users=[])
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.set_library_access(str(user_id), ["1", "2"])

                assert result is False
                assert len(mock_account.update_friend_calls) == 0

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_set_library_access_with_empty_list_revokes_access(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """set_library_access with empty list revokes all access."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithLibraryAccess(users=[mock_user])
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.set_library_access(str(user_id), [])

                assert result is True
                assert len(mock_account.update_friend_calls) == 1
                # Empty sections list should be passed
                assert mock_account.update_friend_calls[0]["sections"] == []

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_set_library_access_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """set_library_access raises MediaClientError when client is not initialized."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.set_library_access(str(user_id), ["1"])

        assert exc_info.value.operation == "set_library_access"
        assert exc_info.value.server_url == url
