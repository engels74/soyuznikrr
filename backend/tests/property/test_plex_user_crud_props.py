"""Property-based tests for PlexClient user creation, deletion, and routing.

Feature: plex-integration
Properties: Friend Creation, Home User Creation, User Type Routing, Delete User
"""

from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from .conftest import (
    MockHTTPResponse,
    MockMyPlexAccountWithHomeUser,
    MockMyPlexAccountWithInvite,
    MockMyPlexUser,
    MockMyPlexUserWithHome,
    MockPlexServer,
    api_key_strategy,
    email_strategy,
    url_strategy,
    username_strategy,
)


class MockMyPlexAccountWithBothMethods:
    """Mock MyPlexAccount that supports both inviteFriend and createHomeUser."""

    _invite_result: MockMyPlexUser | None
    _invite_error: Exception | None
    _create_result: MockMyPlexUser | None
    _create_error: Exception | None
    _last_invited: MockMyPlexUser | None
    invite_friend_called: bool
    create_home_user_called: bool
    last_invite_email: str | None
    last_create_username: str | None

    def __init__(
        self,
        *,
        invite_result: MockMyPlexUser | None = None,
        invite_error: Exception | None = None,
        create_result: MockMyPlexUser | None = None,
        create_error: Exception | None = None,
    ) -> None:
        self._invite_result = invite_result
        self._invite_error = invite_error
        self._create_result = create_result
        self._create_error = create_error
        self._last_invited = None
        self.invite_friend_called = False
        self.create_home_user_called = False
        self.last_invite_email = None
        self.last_create_username = None

    def inviteFriend(
        self, user: str, server: object, sections: object = None
    ) -> MockMyPlexUser:
        """Mock inviteFriend method."""
        _ = server, sections  # Unused but required by API signature
        self.invite_friend_called = True
        self.last_invite_email = user
        if self._invite_error is not None:
            raise self._invite_error
        result = self._invite_result or MockMyPlexUser(
            user_id=12345, username=user, email=user
        )
        self._last_invited = result
        return result

    def users(self) -> list[MockMyPlexUser]:
        """Mock users() returning the invited user."""
        if self._last_invited is not None:
            return [self._last_invited]
        return []

    def createHomeUser(self, user: str, server: object) -> MockMyPlexUser:
        """Mock createHomeUser method."""
        _ = server  # Unused but required by API signature
        self.create_home_user_called = True
        self.last_create_username = user
        if self._create_error is not None:
            raise self._create_error
        if self._create_result is not None:
            return self._create_result
        return MockMyPlexUser(user_id=12345, username=user, email=None)


class MockSessionForSharedServers:
    """Mock HTTP session for shared_servers and v2 friends API calls."""

    _get_json: dict[str, object]
    _get_error: Exception | None
    _delete_error: Exception | None
    _friends_delete_error: Exception | None
    get_called: bool
    delete_called: bool
    delete_url: str | None
    delete_urls: list[str]

    def __init__(
        self,
        *,
        get_json: dict[str, object] | None = None,
        get_error: Exception | None = None,
        delete_error: Exception | None = None,
        friends_delete_error: Exception | None = None,
    ) -> None:
        self._get_json = get_json or {"SharedServer": []}
        self._get_error = get_error
        self._delete_error = delete_error
        self._friends_delete_error = friends_delete_error
        self.get_called = False
        self.delete_called = False
        self.delete_url = None
        self.delete_urls = []

    def get(self, _url: str, **_kwargs: object) -> MockHTTPResponse:
        """Mock GET request."""
        self.get_called = True
        if self._get_error is not None:
            raise self._get_error
        return MockHTTPResponse(json_data=self._get_json)

    def delete(self, url: str, **_kwargs: object) -> MockHTTPResponse:
        """Mock DELETE request."""
        self.delete_called = True
        self.delete_url = url
        self.delete_urls.append(url)
        # Route errors: friends_delete_error for v2 friends/sharings API,
        # delete_error for everything else (shared server removal)
        if "/api/v2/friends/" in url and self._friends_delete_error is not None:
            raise self._friends_delete_error
        if "/api/v2/sharings/" in url and self._friends_delete_error is not None:
            raise self._friends_delete_error
        if (
            "/api/v2/friends/" not in url
            and "/api/v2/sharings/" not in url
            and self._delete_error is not None
        ):
            raise self._delete_error
        return MockHTTPResponse(json_data={})

    def post(self, _url: str, **_kwargs: object) -> MockHTTPResponse:
        """Mock POST request (unused, for interface completeness)."""
        return MockHTTPResponse(json_data={})


class MockMyPlexAccountWithUserManagement:
    """Mock MyPlexAccount that supports user listing and deletion."""

    _users: list[MockMyPlexUser]
    _remove_friend_error: Exception | None
    _remove_home_user_error: Exception | None
    _session: MockSessionForSharedServers
    removed_users: list[str]

    @property
    def session(self) -> MockSessionForSharedServers:
        """Public accessor for the mock session."""
        return self._session

    def __init__(
        self,
        *,
        users: list[MockMyPlexUser] | None = None,
        remove_friend_error: Exception | None = None,
        remove_home_user_error: Exception | None = None,
        session: MockSessionForSharedServers | None = None,
    ) -> None:
        self._users = users or []
        self._remove_friend_error = remove_friend_error
        self._remove_home_user_error = remove_home_user_error
        self._session = session or MockSessionForSharedServers()
        self.removed_users = []

    def users(self) -> list[MockMyPlexUser]:
        """Return the list of mock users."""
        return self._users

    def removeFriend(self, user: MockMyPlexUser) -> None:
        """Mock removeFriend method."""
        if self._remove_friend_error is not None:
            raise self._remove_friend_error
        self.removed_users.append(str(user.id))

    def removeHomeUser(self, user: MockMyPlexUser) -> None:
        """Mock removeHomeUser method."""
        if self._remove_home_user_error is not None:
            raise self._remove_home_user_error
        self.removed_users.append(str(user.id))

    def _headers(self) -> dict[str, str]:
        """Return mock headers."""
        return {"X-Plex-Token": "mock-token"}


class TestFriendCreationReturnsValidExternalUser:
    """
    Feature: plex-integration
    Property 4: Friend Creation Returns Valid ExternalUser

    For any valid email address and connected PlexClient, creating a Friend
    user should return an ExternalUser where external_user_id is non-empty
    and email matches the input email.
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_friend_creation_returns_valid_external_user(
        self,
        url: str,
        api_key: str,
        email: str,
        user_id: int,
    ) -> None:
        """Friend creation returns ExternalUser with non-empty external_user_id and matching email."""
        from zondarr.media.providers.plex.client import PlexClient
        from zondarr.media.types import ExternalUser

        mock_user = MockMyPlexUser(user_id=user_id, username=email, email=email)
        mock_account = MockMyPlexAccountWithInvite(invite_result=mock_user)
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

                # Verify result is ExternalUser
                assert isinstance(result, ExternalUser)
                # external_user_id should be non-empty
                assert result.external_user_id
                assert len(result.external_user_id) > 0
                # email should match input
                assert result.email == email

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_friend_creation_uses_returned_user_id(
        self,
        url: str,
        api_key: str,
        email: str,
        user_id: int,
        username: str,
    ) -> None:
        """Friend creation uses the user ID returned by inviteFriend."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_user = MockMyPlexUser(user_id=user_id, username=username, email=email)
        mock_account = MockMyPlexAccountWithInvite(invite_result=mock_user)
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

                # external_user_id should be the string representation of user_id
                assert result.external_user_id == str(user_id)
                # username should be from the returned user
                assert result.username == username

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_friend_creation_raises_user_already_exists_on_duplicate(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """Friend creation raises MediaClientError with USER_ALREADY_EXISTS on duplicate."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        # Simulate duplicate user error from Plex API
        mock_account = MockMyPlexAccountWithInvite(
            invite_error=Exception("User is already shared with this server")
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(MediaClientError) as exc_info:
                    _ = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

                assert exc_info.value.media_error_code == "USER_ALREADY_EXISTS"
                assert exc_info.value.operation == "create_friend"

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_friend_creation_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """Friend creation raises MediaClientError when client is not initialized."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

        assert exc_info.value.operation == "create_friend"
        assert exc_info.value.server_url == url


class TestHomeUserCreationReturnsValidExternalUser:
    """
    Feature: plex-integration
    Property 5: Home User Creation Returns Valid ExternalUser

    For any valid username and connected PlexClient, creating a Home User
    should return an ExternalUser where external_user_id is non-empty
    and username matches the input username.
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_home_user_creation_returns_valid_external_user(
        self,
        url: str,
        api_key: str,
        username: str,
        user_id: int,
    ) -> None:
        """Home User creation returns ExternalUser with non-empty external_user_id and matching username."""
        from zondarr.media.providers.plex.client import PlexClient
        from zondarr.media.types import ExternalUser

        mock_user = MockMyPlexUser(user_id=user_id, username=username, email=None)
        mock_account = MockMyPlexAccountWithHomeUser(create_result=mock_user)
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

                # Verify result is ExternalUser
                assert isinstance(result, ExternalUser)
                # external_user_id should be non-empty
                assert result.external_user_id
                assert len(result.external_user_id) > 0
                # username should match input
                assert result.username == username
                # email should be None for Home Users
                assert result.email is None

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_home_user_creation_uses_returned_user_id(
        self,
        url: str,
        api_key: str,
        username: str,
        user_id: int,
    ) -> None:
        """Home User creation uses the user ID returned by createHomeUser."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_user = MockMyPlexUser(user_id=user_id, username=username, email=None)
        mock_account = MockMyPlexAccountWithHomeUser(create_result=mock_user)
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

                # external_user_id should be the string representation of user_id
                assert result.external_user_id == str(user_id)

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_home_user_creation_raises_username_taken_on_duplicate(
        self,
        url: str,
        api_key: str,
        username: str,
    ) -> None:
        """Home User creation raises MediaClientError with USERNAME_TAKEN on duplicate."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        # Simulate duplicate username error from Plex API
        mock_account = MockMyPlexAccountWithHomeUser(
            create_error=Exception("Username already taken")
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(MediaClientError) as exc_info:
                    _ = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

                assert exc_info.value.media_error_code == "USERNAME_TAKEN"
                assert exc_info.value.operation == "create_home_user"

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_home_user_creation_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
        username: str,
    ) -> None:
        """Home User creation raises MediaClientError when client is not initialized."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

        assert exc_info.value.operation == "create_home_user"
        assert exc_info.value.server_url == url


class TestUserTypeRoutingCorrectness:
    """
    Feature: plex-integration
    Property 6: User Type Routing Correctness

    For any call to create_user, if email is provided the Friend creation path
    is used (inviteFriend); if no email is provided, the Home User creation
    path is used (createHomeUser).
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
        email=email_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_friend_type_with_email_routes_to_invite_friend(
        self,
        url: str,
        api_key: str,
        username: str,
        email: str,
        user_id: int,
    ) -> None:
        """create_user with email routes to inviteFriend."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_user = MockMyPlexUser(user_id=user_id, username=email, email=email)
        mock_account = MockMyPlexAccountWithBothMethods(invite_result=mock_user)
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.create_user(
                    username,
                    "ignored_password",
                    email=email,
                )

                # Verify inviteFriend was called, not createHomeUser
                assert mock_account.invite_friend_called is True
                assert mock_account.create_home_user_called is False
                assert mock_account.last_invite_email == email
                # Result should have the email
                assert result.email == email

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_home_type_routes_to_create_home_user(
        self,
        url: str,
        api_key: str,
        username: str,
        user_id: int,
    ) -> None:
        """create_user without email routes to createHomeUser."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_user = MockMyPlexUser(user_id=user_id, username=username, email=None)
        mock_account = MockMyPlexAccountWithBothMethods(create_result=mock_user)
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.create_user(username, "ignored_password")

                # Verify createHomeUser was called, not inviteFriend
                assert mock_account.create_home_user_called is True
                assert mock_account.invite_friend_called is False
                assert mock_account.last_create_username == username
                # Result should have the username
                assert result.username == username
                # Result should not have email for Home Users
                assert result.email is None

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_create_user_without_email_creates_home_user(
        self,
        url: str,
        api_key: str,
        username: str,
        user_id: int,
    ) -> None:
        """create_user without email routes to createHomeUser."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_user = MockMyPlexUser(user_id=user_id, username=username, email=None)
        mock_account = MockMyPlexAccountWithBothMethods(create_result=mock_user)
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                _ = await client.create_user(username, "ignored_password")

                assert mock_account.create_home_user_called is True
                assert mock_account.invite_friend_called is False

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
        email=email_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_create_user_with_email_routes_to_friend(
        self,
        url: str,
        api_key: str,
        username: str,
        email: str,
        user_id: int,
    ) -> None:
        """create_user with email routes to inviteFriend."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_user = MockMyPlexUser(user_id=user_id, username=email, email=email)
        mock_account = MockMyPlexAccountWithBothMethods(invite_result=mock_user)
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.create_user(
                    username, "ignored_password", email=email
                )

                # Verify inviteFriend was called (email triggers Friend path)
                assert mock_account.invite_friend_called is True
                assert mock_account.create_home_user_called is False
                assert result.email == email


class TestDeleteUserReturnValueCorrectness:
    """
    Feature: plex-integration
    Property 7: Delete User Return Value Correctness

    For any connected PlexClient and user identifier, delete_user() should
    return True if the user existed and was deleted, False if the user was
    not found, and raise MediaClientError only for other failures.
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_delete_user_returns_true_when_friend_deleted(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """delete_user returns True when Friend is successfully deleted."""
        from zondarr.media.providers.plex.client import PlexClient

        # Create a Friend user (home=False)
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_account = MockMyPlexAccountWithUserManagement(users=[mock_user])
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.delete_user(str(user_id))

                assert result is True
                # Friend removal now uses v2 friends API via session.delete()
                friends_url = f"https://plex.tv/api/v2/friends/{user_id}"
                assert any(friends_url in u for u in mock_account.session.delete_urls)

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_delete_user_returns_true_when_home_user_deleted(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """delete_user returns True when Home User is successfully deleted."""
        from zondarr.media.providers.plex.client import PlexClient

        # Create a Home User (home=True)
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=None, home=True
        )
        mock_account = MockMyPlexAccountWithUserManagement(users=[mock_user])
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.delete_user(str(user_id))

                assert result is True
                assert str(user_id) in mock_account.removed_users

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_delete_user_returns_false_when_user_not_found(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """delete_user returns False when user is not in friends list or shared_servers and v2 cleanup also fails."""
        from zondarr.media.providers.plex.client import PlexClient

        # Empty user list AND empty shared_servers response AND v2 cleanup fails
        mock_session = MockSessionForSharedServers(
            get_json={"SharedServer": []},
            friends_delete_error=Exception("not found"),
        )
        mock_account = MockMyPlexAccountWithUserManagement(
            users=[], session=mock_session
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.delete_user(str(user_id))

                assert result is False
                assert len(mock_account.removed_users) == 0
                assert mock_session.get_called is True

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_delete_user_returns_true_when_shared_server_user_deleted(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """delete_user returns True when user is only in shared_servers (not friends)."""
        from zondarr.media.providers.plex.client import PlexClient

        # User NOT in friends list, but IS in shared_servers
        mock_session = MockSessionForSharedServers(
            get_json={
                "SharedServer": [
                    {"id": 42, "userID": user_id},
                ]
            }
        )
        mock_account = MockMyPlexAccountWithUserManagement(
            users=[], session=mock_session
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.delete_user(str(user_id))

                assert result is True
                assert len(mock_account.removed_users) == 0  # Not in friends
                assert mock_session.delete_called is True
                # Shared server entry 42 was deleted
                assert any("42" in u for u in mock_session.delete_urls)
                # Best-effort friend/sharing cleanup was also attempted
                assert any("/api/v2/friends/" in u for u in mock_session.delete_urls)
                assert any("/api/v2/sharings/" in u for u in mock_session.delete_urls)

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_delete_user_removes_both_friend_and_shared_access(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """delete_user removes both friend relationship and shared server entry."""
        from zondarr.media.providers.plex.client import PlexClient

        # User IS in friends list AND has shared_servers entry
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_session = MockSessionForSharedServers(
            get_json={
                "SharedServer": [
                    {"id": 99, "userID": user_id},
                ]
            }
        )
        mock_account = MockMyPlexAccountWithUserManagement(
            users=[mock_user], session=mock_session
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                result = await client.delete_user(str(user_id))

                assert result is True
                # Friend removal via v2 friends API + shared server removal
                friends_url = f"https://plex.tv/api/v2/friends/{user_id}"
                assert any(friends_url in u for u in mock_session.delete_urls)
                assert mock_session.delete_called is True

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
    )
    @pytest.mark.asyncio
    async def test_delete_user_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
        user_id: int,
    ) -> None:
        """delete_user raises MediaClientError when client is not initialized."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, _account is None
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.delete_user(str(user_id))

        assert exc_info.value.operation == "delete_user"
        assert exc_info.value.server_url == url

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
        error_message=st.text(min_size=1, max_size=100).filter(
            lambda s: (
                s.strip()
                and "not found" not in s.lower()
                and "does not exist" not in s.lower()
            )
        ),
    )
    @pytest.mark.asyncio
    async def test_delete_user_raises_on_api_failure(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
        error_message: str,
    ) -> None:
        """delete_user raises ExternalServiceError on API failure (not 'not found')."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.providers.plex.client import PlexClient

        # Create a Friend user that will fail to delete via v2 friends API
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_session = MockSessionForSharedServers(
            friends_delete_error=RuntimeError(error_message),
        )
        mock_account = MockMyPlexAccountWithUserManagement(
            users=[mock_user],
            session=mock_session,
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client.delete_user(str(user_id))

                assert f"Plex ({url})" in exc_info.value.service_name

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.integers(min_value=1, max_value=999999999),
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_delete_user_raises_when_shared_server_removal_fails(
        self,
        url: str,
        api_key: str,
        user_id: int,
        username: str,
    ) -> None:
        """delete_user raises ExternalServiceError when shared server removal fails, without attempting friend removal."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.providers.plex.client import PlexClient

        # Create a Friend user with a shared server entry that will fail on DELETE
        mock_user = MockMyPlexUserWithHome(
            user_id=user_id, username=username, email=f"{username}@test.com", home=False
        )
        mock_session = MockSessionForSharedServers(
            get_json={
                "SharedServer": [
                    {"id": 77, "userID": user_id},
                ]
            },
            delete_error=RuntimeError("shared server API failure"),
        )
        mock_account = MockMyPlexAccountWithUserManagement(
            users=[mock_user],
            session=mock_session,
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client.delete_user(str(user_id))

                assert f"Plex ({url})" in exc_info.value.service_name
                # No friend removal should have been attempted
                assert not any(
                    "/api/v2/friends/" in u for u in mock_session.delete_urls
                )
