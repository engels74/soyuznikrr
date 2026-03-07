"""Property-based tests for PlexClient error structure validation.

Feature: plex-integration
Property: Error Structure Contains Required Fields
"""

from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from .conftest import (
    MockMyPlexAccountWithHomeUser,
    MockMyPlexAccountWithInvite,
    MockMyPlexAccountWithUserList,
    MockPlexServer,
    api_key_strategy,
    email_strategy,
    url_strategy,
    username_strategy,
)


class TestErrorStructureContainsRequiredFields:
    """
    Feature: plex-integration
    Property 14: Error Structure Contains Required Fields

    For any MediaClientError raised by PlexClient, the error should contain
    non-empty operation field, and the server_url should match the client's
    configured URL.
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_get_libraries_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """get_libraries error contains operation and server_url fields."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, should raise with proper error structure
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.get_libraries()

        error = exc_info.value
        # operation field must be non-empty
        assert error.operation
        assert len(error.operation) > 0
        assert error.operation == "get_libraries"
        # server_url must match client's configured URL
        assert error.server_url == url
        # cause field must be present (can be empty string but not None)
        assert error.cause is not None

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_friend_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """create_friend error contains service_name field for external errors."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.providers.plex.client import PlexClient

        # Create mock that raises an error
        mock_account = MockMyPlexAccountWithInvite(
            invite_error=RuntimeError("Test API error")
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

                error = exc_info.value
                # service_name must contain the server URL
                assert f"Plex ({url})" in error.service_name

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_home_user_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        username: str,
    ) -> None:
        """create_home_user error contains service_name field for external errors."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.providers.plex.client import PlexClient

        # Create mock that raises an error
        mock_account = MockMyPlexAccountWithHomeUser(
            create_error=RuntimeError("Test API error")
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

                error = exc_info.value
                # service_name must contain the server URL
                assert f"Plex ({url})" in error.service_name

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.text(min_size=1, max_size=20).filter(lambda s: s.strip()),
    )
    @pytest.mark.asyncio
    async def test_delete_user_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        user_id: str,
    ) -> None:
        """delete_user error contains service_name field for external errors."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.providers.plex.client import PlexClient

        # Create mock that raises an error
        mock_account = MockMyPlexAccountWithUserList(
            users_error=RuntimeError("Test API error")
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client.delete_user(user_id)

                error = exc_info.value
                # service_name must contain the server URL
                assert f"Plex ({url})" in error.service_name

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
    )
    @pytest.mark.asyncio
    async def test_list_users_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
    ) -> None:
        """list_users error contains operation and server_url fields."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url=url, api_key=api_key)

        # Without entering context, should raise with proper error structure
        with pytest.raises(MediaClientError) as exc_info:
            _ = await client.list_users()

        error = exc_info.value
        # operation field must be non-empty
        assert error.operation
        assert len(error.operation) > 0
        assert error.operation == "list_users"
        # server_url must match client's configured URL
        assert error.server_url == url
        # cause field must be present
        assert error.cause is not None

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.text(min_size=1, max_size=20).filter(lambda s: s.strip()),
        library_ids=st.lists(
            st.integers(min_value=1, max_value=1000).map(str),
            min_size=0,
            max_size=5,
        ),
    )
    @pytest.mark.asyncio
    async def test_set_library_access_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        user_id: str,
        library_ids: list[str],
    ) -> None:
        """set_library_access error contains service_name field for external errors."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.providers.plex.client import PlexClient

        # Create mock that raises an error
        mock_account = MockMyPlexAccountWithUserList(
            users_error=RuntimeError("Test API error")
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client.set_library_access(user_id, library_ids)

                error = exc_info.value
                # service_name must contain the server URL
                assert f"Plex ({url})" in error.service_name

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        user_id=st.text(min_size=1, max_size=20).filter(lambda s: s.strip()),
        permissions=st.fixed_dictionaries({"can_download": st.booleans()}),
    )
    @pytest.mark.asyncio
    async def test_update_permissions_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        user_id: str,
        permissions: dict[str, bool],
    ) -> None:
        """update_permissions error contains service_name field for external errors."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.providers.plex.client import PlexClient

        # Create mock that raises an error
        mock_account = MockMyPlexAccountWithUserList(
            users_error=RuntimeError("Test API error")
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    _ = await client.update_permissions(
                        user_id, permissions=permissions
                    )

                error = exc_info.value
                # service_name must contain the server URL
                assert f"Plex ({url})" in error.service_name

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_user_already_exists_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """USER_ALREADY_EXISTS error contains operation, server_url, and error_code."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient, PlexErrorCode

        # Create mock that raises "already shared" error
        mock_account = MockMyPlexAccountWithInvite(
            invite_error=Exception("User is already shared with this server")
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(MediaClientError) as exc_info:
                    _ = await client._create_friend(email)  # pyright: ignore[reportPrivateUsage]

                error = exc_info.value
                # operation field must be non-empty
                assert error.operation
                assert error.operation == "create_friend"
                # server_url must match client's configured URL
                assert error.server_url == url
                # error_code should be USER_ALREADY_EXISTS
                assert error.media_error_code == PlexErrorCode.USER_ALREADY_EXISTS
                # cause field must be present
                assert error.cause is not None

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        username=username_strategy,
    )
    @pytest.mark.asyncio
    async def test_username_taken_error_contains_required_fields(
        self,
        url: str,
        api_key: str,
        username: str,
    ) -> None:
        """USERNAME_TAKEN error contains operation, server_url, and error_code."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient, PlexErrorCode

        # Create mock that raises "username taken" error
        mock_account = MockMyPlexAccountWithHomeUser(
            create_error=Exception("Username is already taken")
        )
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(MediaClientError) as exc_info:
                    _ = await client._create_home_user(username)  # pyright: ignore[reportPrivateUsage]

                error = exc_info.value
                # operation field must be non-empty
                assert error.operation
                assert error.operation == "create_home_user"
                # server_url must match client's configured URL
                assert error.server_url == url
                # error_code should be USERNAME_TAKEN
                assert error.media_error_code == PlexErrorCode.USERNAME_TAKEN
                # cause field must be present
                assert error.cause is not None
