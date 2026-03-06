"""Property-based tests for PlexClient permission updates and user listing.

Feature: plex-integration
Properties: Permission Update Mapping, List Users Returns ExternalUser Structs
"""

from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from .conftest import (
    MockMyPlexAccountWithUserList,
    MockMyPlexUserWithHome,
    MockPlexServer,
    api_key_strategy,
    email_strategy,
    url_strategy,
    username_strategy,
)


class MockMyPlexAccountWithPermissions:
    """Mock MyPlexAccount that supports user listing and permission updates."""

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
        self,
        user: object,
        server: object,
        allowSync: bool | None = None,
        **kwargs: object,
    ) -> None:
        """Mock updateFriend method with permission support."""
        if self._update_friend_error is not None:
            raise self._update_friend_error
        self.update_friend_calls.append(
            {"user": user, "server": server, "allowSync": allowSync, **kwargs}
        )


class TestPermissionUpdateMappingAndReturnValue:
    """
    Feature: plex-integration
    Property 9: Permission Update Mapping and Return Value

    For any connected PlexClient, valid user identifier, and permissions dict
    containing can_download, update_permissions() should map can_download to
    the Plex allowSync setting and return True on success, False if user not found.
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
        can_download=st.booleans(),
    )
    @pytest.mark.asyncio
    async def test_update_permissions_maps_can_download_to_allow_sync(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
        can_download: bool,
    ) -> None:
        """update_permissions maps can_download to Plex allowSync setting."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithPermissions(users=[mock_user])
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.update_permissions(
                    str(user_id), permissions={"can_download": can_download}
                )

                assert result is True
                assert len(mock_account.update_friend_calls) == 1
                # Verify can_download was mapped to allowSync
                assert mock_account.update_friend_calls[0]["allowSync"] == can_download

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_update_permissions_returns_true_on_success(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """update_permissions returns True when permissions are successfully updated."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithPermissions(users=[mock_user])
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.update_permissions(
                    str(user_id), permissions={"can_download": True}
                )

                assert result is True

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_update_permissions_returns_false_when_user_not_found(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """update_permissions returns False when user is not found."""
        from zondarr.media.providers.plex.client import PlexClient

        # Empty user list - user won't be found
        mock_account = MockMyPlexAccountWithPermissions(users=[])
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.update_permissions(
                    str(user_id), permissions={"can_download": True}
                )

                assert result is False
                assert len(mock_account.update_friend_calls) == 0

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_update_permissions_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """update_permissions raises MediaClientError when client is not initialized."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.update_permissions(
                str(user_id), permissions={"can_download": True}
            )

        assert exc_info.value.operation == "update_permissions"
        assert exc_info.value.server_url == url

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_update_permissions_with_empty_dict_returns_true(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """update_permissions with empty dict returns True (no-op for existing user)."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithPermissions(users=[mock_user])
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.update_permissions(str(user_id), permissions={})

                assert result is True
                # No updateFriend call should be made for empty permissions
                assert len(mock_account.update_friend_calls) == 0


class TestListUsersReturnsAllUsersAsExternalUserStructs:
    """
    Feature: plex-integration
    Property 10: List Users Returns All Users as ExternalUser Structs

    For any connected PlexClient, list_users() should return a sequence
    containing all Friends and Home Users, where each element is a valid
    ExternalUser with non-empty external_user_id and username.
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        users_data=st.lists(
            st.tuples(
                st.integers(min_value=1, max_value=999999999),
                username_strategy,
                st.one_of(email_strategy, st.none()),
                st.booleans(),
            ),
            min_size=0,
            max_size=10,
        ),
    )
    @pytest.mark.asyncio
    async def test_list_users_returns_all_users(
        self,
        url: str,
        api_key: str,
        users_data: list[tuple[int, str, str | None, bool]],
    ) -> None:
        """list_users returns all Friends and Home Users as ExternalUser structs."""
        from zondarr.media.providers.plex.client import PlexClient
        from zondarr.media.types import ExternalUser

        # Create mock users
        mock_users = [
            MockMyPlexUserWithHome(
                user_id=user_id, username=username, email=email, home=is_home
            )
            for user_id, username, email, is_home in users_data
        ]
        mock_account = MockMyPlexAccountWithUserList(users=mock_users)
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.list_users()

                # Should return same number of users
                assert len(result) == len(users_data)

                # Each result should be a valid ExternalUser
                for user in result:
                    assert isinstance(user, ExternalUser)
                    assert user.external_user_id  # non-empty
                    assert user.username is not None

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_list_users_maps_fields_correctly(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
        email: str,
    ) -> None:
        """list_users maps user fields correctly to ExternalUser."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=email, home=False
        )
        mock_account = MockMyPlexAccountWithUserList(users=[mock_user])
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.list_users()

                assert len(result) == 1
                user = result[0]
                assert user.external_user_id == str(user_id)
                assert user.username == username
                assert user.email == email

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_list_users_returns_empty_for_no_users(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """list_users returns empty sequence when no users exist."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_account = MockMyPlexAccountWithUserList(users=[])
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.list_users()
                assert len(result) == 0

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_list_users_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """list_users raises MediaClientError when client is not initialized."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.list_users()

        assert exc_info.value.operation == "list_users"
        assert exc_info.value.server_url == url

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        error_message=st.text(min_size=1, max_size=100).filter(
            lambda s: (
                s.strip()
                and not any(
                    kw in s.lower()
                    for kw in [
                        "permission",
                        "forbidden",
                        "403",
                        "not found",
                        "does not exist",
                        "taken",
                    ]
                )
                and not (
                    "already" in s.lower()
                    and ("shared" in s.lower() or "friend" in s.lower())
                )
                and not ("exists" in s.lower() and "user" in s.lower())
            )
        ),
    )
    @pytest.mark.asyncio
    async def test_list_users_raises_on_api_failure(
        self,
        url: str,
        api_key: str,
        error_message: str,
    ) -> None:
        """list_users raises ExternalServiceError on API failure."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.providers.plex.client import PlexClient

        mock_account = MockMyPlexAccountWithUserList(
            users_error=RuntimeError(error_message)
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client.list_users()

                assert f"Plex ({url})" in exc_info.value.service_name
