"""Property-based tests for PlexClient direct library sharing and v2 auto-accept.

Feature: plex-integration
Properties: Direct Share Failure Propagation, Cancel Pending Invites, v2 Auto-Accept
"""

from typing import Protocol
from unittest.mock import patch

import pytest
from hypothesis import given, settings

from .conftest import (
    MockLibrarySection,
    MockLibraryWithSections,
    MockPlexServer,
    MockResponse,
    api_key_strategy,
    email_strategy,
    url_strategy,
)


class MockSessionForDirectShare:
    """Mock requests session used by the admin account for direct share."""

    _response: MockResponse | None
    _post_error: Exception | None
    last_post_url: str | None
    last_post_json: dict[str, object] | None

    def __init__(
        self,
        *,
        response: MockResponse | None = None,
        post_error: Exception | None = None,
    ) -> None:
        self._response = response or MockResponse()
        self._post_error = post_error
        self.last_post_url = None
        self.last_post_json = None

    def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
        timeout: int | None = None,
    ) -> MockResponse:
        _ = headers, timeout
        self.last_post_url = url
        self.last_post_json = json
        if self._post_error is not None:
            raise self._post_error
        assert self._response is not None
        return self._response


class MockMyPlexInviteServerShare:
    """Mock MyPlexServerShare inside an invite."""

    machineIdentifier: str

    def __init__(self, *, machine_identifier: str) -> None:
        self.machineIdentifier = machine_identifier


class MockMyPlexInvite:
    """Mock MyPlexInvite for pending invite tests."""

    email: str
    friend: bool
    home: bool
    server: bool
    servers: list[MockMyPlexInviteServerShare]

    def __init__(
        self,
        *,
        email: str,
        friend: bool = True,
        home: bool = False,
        server: bool = True,
        servers: list[MockMyPlexInviteServerShare] | None = None,
    ) -> None:
        self.email = email
        self.friend = friend
        self.home = home
        self.server = server
        self.servers = servers or []


class MockMyPlexAccountForDirectShare:
    """Mock MyPlexAccount that supports direct share and invite cancellation."""

    _session: MockSessionForDirectShare
    _pending_invites: list[MockMyPlexInvite]
    _cancel_invite_error: Exception | None
    cancelled_invites: list[MockMyPlexInvite]
    pending_invites_called: bool
    username: str

    def __init__(
        self,
        *,
        session: MockSessionForDirectShare | None = None,
        pending_invites: list[MockMyPlexInvite] | None = None,
        cancel_invite_error: Exception | None = None,
        username: str = "admin_user",
    ) -> None:
        self._session = session or MockSessionForDirectShare()
        self._pending_invites = pending_invites or []
        self._cancel_invite_error = cancel_invite_error
        self.cancelled_invites = []
        self.pending_invites_called = False
        self.username = username

    def _headers(self) -> dict[str, str]:
        return {"X-Plex-Token": "admin-token"}

    def pendingInvites(
        self,
        includeSent: bool = False,
        includeReceived: bool = False,
    ) -> list[MockMyPlexInvite]:
        _ = includeSent, includeReceived
        self.pending_invites_called = True
        return self._pending_invites

    def cancelInvite(self, invite: MockMyPlexInvite) -> None:
        if self._cancel_invite_error is not None:
            raise self._cancel_invite_error
        self.cancelled_invites.append(invite)

    def _getSectionIds(
        self,
        server: object,
        sections: list[object],
    ) -> list[int]:
        """Mock cloud-side section ID translation.

        Returns sequential cloud IDs (100001, 100002, ...) to simulate
        the local-key → cloud-ID translation that plexapi performs.
        """
        _ = server
        return [100000 + getattr(s, "key", i) for i, s in enumerate(sections)]


class MockV2InviteResponse:
    """Mock HTTP response for Plex v2 invite API calls."""

    _json: object
    status_code: int

    def __init__(self, *, json_data: object = None, status_code: int = 200) -> None:
        self._json = json_data if json_data is not None else []
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self) -> object:
        return self._json


class V2InviteSessionProtocol(Protocol):
    """Protocol for mock v2 invite session objects."""

    def get(self, url: str, **kwargs: object) -> MockV2InviteResponse: ...
    def post(self, url: str, **kwargs: object) -> MockV2InviteResponse: ...


class MockV2InviteSession:
    """Mock requests session for the user account's v2 invite API calls."""

    _get_response: MockV2InviteResponse
    _post_response: MockV2InviteResponse

    def __init__(
        self,
        *,
        get_response: MockV2InviteResponse | None = None,
        post_response: MockV2InviteResponse | None = None,
    ) -> None:
        self._get_response = get_response or MockV2InviteResponse()
        self._post_response = post_response or MockV2InviteResponse()

    def get(self, url: str, **kwargs: object) -> MockV2InviteResponse:
        _ = url, kwargs
        return self._get_response

    def post(self, url: str, **kwargs: object) -> MockV2InviteResponse:
        _ = url, kwargs
        return self._post_response


class MockMyPlexAccountUserForDirectShare:
    """Mock MyPlexAccount created from user's auth token."""

    id: int
    username: str
    uuid: str
    _session: V2InviteSessionProtocol

    def __init__(
        self,
        *,
        user_id: int,
        username: str,
        uuid: str = "user-uuid-1234",
        session: V2InviteSessionProtocol | None = None,
    ) -> None:
        self.id = user_id
        self.username = username
        self.uuid = uuid
        self._session = session or MockV2InviteSession()


class MockV2InviteSessionSequenced:
    """Mock session that returns different v2 responses on successive GET calls.

    Allows testing retry logic by providing a sequence of responses.
    """

    _get_responses: list[MockV2InviteResponse]
    _post_response: MockV2InviteResponse
    get_call_index: int

    def __init__(
        self,
        *,
        get_responses: list[MockV2InviteResponse] | None = None,
        post_response: MockV2InviteResponse | None = None,
    ) -> None:
        self._get_responses = get_responses or [MockV2InviteResponse()]
        self._post_response = post_response or MockV2InviteResponse()
        self.get_call_index = 0

    def get(self, url: str, **kwargs: object) -> MockV2InviteResponse:
        _ = url, kwargs
        idx = min(self.get_call_index, len(self._get_responses) - 1)
        self.get_call_index += 1
        return self._get_responses[idx]

    def post(self, url: str, **kwargs: object) -> MockV2InviteResponse:
        _ = url, kwargs
        return self._post_response


class MockV2InviteSessionError:
    """Mock session that raises on GET (simulating network failure)."""

    _error: Exception
    _post_response: MockV2InviteResponse

    def __init__(
        self,
        *,
        error: Exception,
        post_response: MockV2InviteResponse | None = None,
    ) -> None:
        self._error = error
        self._post_response = post_response or MockV2InviteResponse()

    def get(self, url: str, **kwargs: object) -> MockV2InviteResponse:
        _ = url, kwargs
        raise self._error

    def post(self, url: str, **kwargs: object) -> MockV2InviteResponse:
        _ = url, kwargs
        return self._post_response


def _make_v2_invite_json(
    *,
    admin_username: str = "admin_user",
    invite_id: int = 99999,
    machine_identifier: str = "test-machine-id",
) -> list[dict[str, object]]:
    """Build a v2 pending-invite JSON list with one invite from the admin."""
    return [
        {
            "owner": {
                "username": admin_username,
                "email": "",
                "title": "",
                "friendlyName": "",
            },
            "sharedServers": [
                {"id": invite_id, "machineIdentifier": machine_identifier}
            ],
        }
    ]


class TestDirectShareFailurePropagatesError:
    """
    Feature: plex-integration
    Property: Direct Share Failure Propagation

    When _share_library_direct fails, the error should propagate as
    MediaClientError or ExternalServiceError instead of silently
    falling back to _invite_friend.

    **Validates: No silent friend relationship creation**
    """

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_direct_share_api_failure_raises_external_service_error(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """Direct share API failure raises ExternalServiceError, not fallback."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.providers.plex.client import PlexClient

        # Session that raises a connection error on POST
        mock_session = MockSessionForDirectShare(
            post_error=ConnectionError("Plex API unreachable")
        )
        mock_account = MockMyPlexAccountForDirectShare(session=mock_session)
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        mock_user_account = MockMyPlexAccountUserForDirectShare(
            user_id=12345, username="testuser"
        )

        with (
            patch("plexapi.server.PlexServer", return_value=mock_server),
            patch("plexapi.myplex.MyPlexAccount", return_value=mock_user_account),
        ):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError):
                    _ = await client._share_library_direct(email, "fake-token")  # pyright: ignore[reportPrivateUsage]

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_direct_share_http_error_raises_error(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """Direct share HTTP 4xx/5xx raises instead of falling back."""
        from zondarr.core.exceptions import ExternalServiceError
        from zondarr.media.providers.plex.client import PlexClient

        # Session that returns a 500 response
        mock_session = MockSessionForDirectShare(response=MockResponse(status_code=500))
        mock_account = MockMyPlexAccountForDirectShare(session=mock_session)
        mock_server = MockPlexServer(url, api_key, account=mock_account)

        mock_user_account = MockMyPlexAccountUserForDirectShare(
            user_id=12345, username="testuser"
        )

        with (
            patch("plexapi.server.PlexServer", return_value=mock_server),
            patch("plexapi.myplex.MyPlexAccount", return_value=mock_user_account),
        ):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                with pytest.raises(ExternalServiceError):
                    _ = await client._share_library_direct(email, "fake-token")  # pyright: ignore[reportPrivateUsage]

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_direct_share_raises_when_not_initialized(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """_share_library_direct raises MediaClientError when not initialized."""
        from zondarr.media.exceptions import MediaClientError
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url=url, api_key=api_key)

        with pytest.raises(MediaClientError) as exc_info:
            _ = await client._share_library_direct(email, "fake-token")  # pyright: ignore[reportPrivateUsage]

        assert exc_info.value.operation == "share_library_direct"
        assert exc_info.value.server_url == url

    @settings(max_examples=25)
    @given(
        url=url_strategy,
        api_key=api_key_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_direct_share_sends_cloud_translated_section_ids(
        self,
        url: str,
        api_key: str,
        email: str,
    ) -> None:
        """Direct share POST payload uses cloud-translated section IDs from _getSectionIds."""
        from zondarr.media.providers.plex.client import PlexClient

        # Set up library sections with known local keys
        sections = [
            MockLibrarySection(key=1, title="Movies", section_type="movie"),
            MockLibrarySection(key=2, title="TV Shows", section_type="show"),
        ]
        mock_session = MockSessionForDirectShare()
        mock_account = MockMyPlexAccountForDirectShare(session=mock_session)
        mock_library = MockLibraryWithSections(sections=sections)
        mock_server = MockPlexServer(
            url, api_key, account=mock_account, library=mock_library
        )

        mock_user_account = MockMyPlexAccountUserForDirectShare(
            user_id=12345, username="testuser"
        )

        with (
            patch("plexapi.server.PlexServer", return_value=mock_server),
            patch("plexapi.myplex.MyPlexAccount", return_value=mock_user_account),
        ):
            client = PlexClient(url=url, api_key=api_key)

            async with client:
                _ = await client._share_library_direct(  # pyright: ignore[reportPrivateUsage]
                    email, "fake-token", library_section_ids=[1, 2]
                )

        # Verify POST payload contains cloud-translated IDs (100000 + key),
        # not the raw local section keys (1, 2)
        payload = mock_session.last_post_json
        assert payload is not None
        shared_server = payload["shared_server"]
        assert isinstance(shared_server, dict)
        assert shared_server["library_section_ids"] == [100001, 100002]


class TestCancelPendingInvitesForUser:
    """
    Feature: plex-integration
    Property: Cancel Pending Invites Cleanup

    _cancel_pending_invites_for_user should cancel matching pending
    invites sent by the admin for the given email and server, and
    should never raise exceptions (best-effort).

    **Validates: Stale invite cleanup**
    """

    @pytest.mark.asyncio
    async def test_cancels_matching_invite(self) -> None:
        """Cancels a pending invite matching the email and server machineIdentifier."""
        from zondarr.media.providers.plex.client import PlexClient

        machine_id = "test-machine-123"
        email = "user@example.com"

        invite = MockMyPlexInvite(
            email=email,
            servers=[MockMyPlexInviteServerShare(machine_identifier=machine_id)],
        )
        mock_account = MockMyPlexAccountForDirectShare(pending_invites=[invite])
        mock_server = MockPlexServer(
            "http://plex:32400",
            "token123",
            account=mock_account,
            machine_identifier=machine_id,
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url="http://plex:32400", api_key="token123")

            async with client:
                count = await client._cancel_pending_invites_for_user(email)  # pyright: ignore[reportPrivateUsage]

                assert count == 1
                assert len(mock_account.cancelled_invites) == 1
                assert mock_account.cancelled_invites[0] is invite

    @pytest.mark.asyncio
    async def test_no_op_when_no_pending_invites(self) -> None:
        """Returns 0 when there are no pending invites."""
        from zondarr.media.providers.plex.client import PlexClient

        mock_account = MockMyPlexAccountForDirectShare(pending_invites=[])
        mock_server = MockPlexServer(
            "http://plex:32400", "token123", account=mock_account
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url="http://plex:32400", api_key="token123")

            async with client:
                count = await client._cancel_pending_invites_for_user(  # pyright: ignore[reportPrivateUsage]
                    "user@example.com"
                )

                assert count == 0
                assert len(mock_account.cancelled_invites) == 0

    @pytest.mark.asyncio
    async def test_ignores_invite_for_different_email(self) -> None:
        """Does not cancel invites for a different email address."""
        from zondarr.media.providers.plex.client import PlexClient

        machine_id = "test-machine-123"
        invite = MockMyPlexInvite(
            email="other@example.com",
            servers=[MockMyPlexInviteServerShare(machine_identifier=machine_id)],
        )
        mock_account = MockMyPlexAccountForDirectShare(pending_invites=[invite])
        mock_server = MockPlexServer(
            "http://plex:32400",
            "token123",
            account=mock_account,
            machine_identifier=machine_id,
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url="http://plex:32400", api_key="token123")

            async with client:
                count = await client._cancel_pending_invites_for_user(  # pyright: ignore[reportPrivateUsage]
                    "user@example.com"
                )

                assert count == 0
                assert len(mock_account.cancelled_invites) == 0

    @pytest.mark.asyncio
    async def test_ignores_invite_for_different_server(self) -> None:
        """Does not cancel invites for a different server machineIdentifier."""
        from zondarr.media.providers.plex.client import PlexClient

        invite = MockMyPlexInvite(
            email="user@example.com",
            servers=[
                MockMyPlexInviteServerShare(machine_identifier="other-machine-456")
            ],
        )
        mock_account = MockMyPlexAccountForDirectShare(pending_invites=[invite])
        mock_server = MockPlexServer(
            "http://plex:32400",
            "token123",
            account=mock_account,
            machine_identifier="test-machine-123",
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url="http://plex:32400", api_key="token123")

            async with client:
                count = await client._cancel_pending_invites_for_user(  # pyright: ignore[reportPrivateUsage]
                    "user@example.com"
                )

                assert count == 0
                assert len(mock_account.cancelled_invites) == 0

    @pytest.mark.asyncio
    async def test_swallows_exceptions(self) -> None:
        """Failures are swallowed and return 0 (best-effort)."""
        from zondarr.media.providers.plex.client import PlexClient

        machine_id = "test-machine-123"
        invite = MockMyPlexInvite(
            email="user@example.com",
            servers=[MockMyPlexInviteServerShare(machine_identifier=machine_id)],
        )
        mock_account = MockMyPlexAccountForDirectShare(
            pending_invites=[invite],
            cancel_invite_error=RuntimeError("Plex API error"),
        )
        mock_server = MockPlexServer(
            "http://plex:32400",
            "token123",
            account=mock_account,
            machine_identifier=machine_id,
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url="http://plex:32400", api_key="token123")

            async with client:
                # Should not raise
                count = await client._cancel_pending_invites_for_user(  # pyright: ignore[reportPrivateUsage]
                    "user@example.com"
                )

                assert count == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_not_initialized(self) -> None:
        """Returns 0 when client is not initialized (no context manager)."""
        from zondarr.media.providers.plex.client import PlexClient

        client = PlexClient(url="http://plex:32400", api_key="token123")

        count = await client._cancel_pending_invites_for_user("user@example.com")  # pyright: ignore[reportPrivateUsage]

        assert count == 0

    @pytest.mark.asyncio
    async def test_email_matching_is_case_insensitive(self) -> None:
        """Email matching is case-insensitive."""
        from zondarr.media.providers.plex.client import PlexClient

        machine_id = "test-machine-123"
        invite = MockMyPlexInvite(
            email="User@Example.COM",
            servers=[MockMyPlexInviteServerShare(machine_identifier=machine_id)],
        )
        mock_account = MockMyPlexAccountForDirectShare(pending_invites=[invite])
        mock_server = MockPlexServer(
            "http://plex:32400",
            "token123",
            account=mock_account,
            machine_identifier=machine_id,
        )

        with patch("plexapi.server.PlexServer", return_value=mock_server):
            client = PlexClient(url="http://plex:32400", api_key="token123")

            async with client:
                count = await client._cancel_pending_invites_for_user(  # pyright: ignore[reportPrivateUsage]
                    "user@example.com"
                )

                assert count == 1
                assert len(mock_account.cancelled_invites) == 1


class TestAutoAcceptV2Invite:
    """
    Feature: plex-integration
    Property: v2 Auto-Accept Invite Behaviour

    After _share_library_direct creates a server share, it uses the Plex v2
    API to automatically accept the pending invite on behalf of the user.
    This test class covers the retry logic and error handling for that flow.
    """

    @pytest.mark.asyncio
    async def test_auto_accept_succeeds_on_first_attempt(self) -> None:
        """v2 auto-accept finds matching invite and accepts on first try."""
        from zondarr.media.providers.plex.client import PlexClient

        admin_username = "admin_user"
        invite_json = _make_v2_invite_json(admin_username=admin_username, invite_id=42)
        v2_session = MockV2InviteSessionSequenced(
            get_responses=[MockV2InviteResponse(json_data=invite_json)],
        )
        mock_user_account = MockMyPlexAccountUserForDirectShare(
            user_id=12345, username="testuser", session=v2_session
        )

        mock_session = MockSessionForDirectShare()
        mock_account = MockMyPlexAccountForDirectShare(
            session=mock_session, username=admin_username
        )
        mock_server = MockPlexServer(
            "http://plex:32400", "token123", account=mock_account
        )

        with (
            patch("plexapi.server.PlexServer", return_value=mock_server),
            patch("plexapi.myplex.MyPlexAccount", return_value=mock_user_account),
            patch("time.sleep"),
        ):
            client = PlexClient(url="http://plex:32400", api_key="token123")

            async with client:
                result = await client._share_library_direct(  # pyright: ignore[reportPrivateUsage]
                    "user@example.com", "fake-token"
                )

                assert result.external_user_id == "12345"
                assert result.username == "testuser"
                # auto-accept succeeded → stale invites should have been cleaned up
                assert mock_account.pending_invites_called

    @pytest.mark.asyncio
    async def test_auto_accept_succeeds_on_retry(self) -> None:
        """v2 auto-accept finds no invite on first attempt, succeeds on second."""
        from zondarr.media.providers.plex.client import PlexClient

        admin_username = "admin_user"
        invite_json = _make_v2_invite_json(admin_username=admin_username)
        v2_session = MockV2InviteSessionSequenced(
            get_responses=[
                MockV2InviteResponse(json_data=[]),  # first call: empty
                MockV2InviteResponse(json_data=invite_json),  # second call: found
            ],
        )
        mock_user_account = MockMyPlexAccountUserForDirectShare(
            user_id=12345, username="testuser", session=v2_session
        )

        mock_session = MockSessionForDirectShare()
        mock_account = MockMyPlexAccountForDirectShare(
            session=mock_session, username=admin_username
        )
        mock_server = MockPlexServer(
            "http://plex:32400", "token123", account=mock_account
        )

        with (
            patch("plexapi.server.PlexServer", return_value=mock_server),
            patch("plexapi.myplex.MyPlexAccount", return_value=mock_user_account),
            patch("time.sleep"),
        ):
            client = PlexClient(url="http://plex:32400", api_key="token123")

            async with client:
                result = await client._share_library_direct(  # pyright: ignore[reportPrivateUsage]
                    "user@example.com", "fake-token"
                )

                assert result.external_user_id == "12345"
                # Confirm v2 session GET was called twice (empty then found)
                assert v2_session.get_call_index == 2
                # auto-accept succeeded → stale invites cleaned up
                assert mock_account.pending_invites_called

    @pytest.mark.asyncio
    async def test_auto_accept_gives_up_after_max_retries(self) -> None:
        """v2 auto-accept gives up after 3 attempts; auto_accepted=False."""
        from zondarr.media.providers.plex.client import PlexClient

        # All attempts return empty → never finds a matching invite
        v2_session = MockV2InviteSessionSequenced(
            get_responses=[MockV2InviteResponse(json_data=[])],
        )
        mock_user_account = MockMyPlexAccountUserForDirectShare(
            user_id=12345, username="testuser", session=v2_session
        )

        mock_session = MockSessionForDirectShare()
        mock_account = MockMyPlexAccountForDirectShare(
            session=mock_session, username="admin_user"
        )
        mock_server = MockPlexServer(
            "http://plex:32400", "token123", account=mock_account
        )

        with (
            patch("plexapi.server.PlexServer", return_value=mock_server),
            patch("plexapi.myplex.MyPlexAccount", return_value=mock_user_account),
            patch("time.sleep"),
        ):
            client = PlexClient(url="http://plex:32400", api_key="token123")

            async with client:
                result = await client._share_library_direct(  # pyright: ignore[reportPrivateUsage]
                    "user@example.com", "fake-token"
                )

                # The share itself succeeded even though auto-accept didn't
                assert result.external_user_id == "12345"
                # 3 GET attempts were made
                assert v2_session.get_call_index == 3
                # auto-accept failed → stale invites NOT cleaned up
                assert not mock_account.pending_invites_called

    @pytest.mark.asyncio
    async def test_auto_accept_exception_logged_at_warning(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Exception during v2 auto-accept is logged at warning level."""
        from zondarr.media.providers.plex.client import PlexClient

        v2_session = MockV2InviteSessionError(
            error=ConnectionError("v2 API unreachable")
        )
        mock_user_account = MockMyPlexAccountUserForDirectShare(
            user_id=12345, username="testuser", session=v2_session
        )

        mock_session = MockSessionForDirectShare()
        mock_account = MockMyPlexAccountForDirectShare(
            session=mock_session, username="admin_user"
        )
        mock_server = MockPlexServer(
            "http://plex:32400", "token123", account=mock_account
        )

        with (
            patch("plexapi.server.PlexServer", return_value=mock_server),
            patch("plexapi.myplex.MyPlexAccount", return_value=mock_user_account),
            patch("time.sleep"),
        ):
            client = PlexClient(url="http://plex:32400", api_key="token123")

            async with client:
                result = await client._share_library_direct(  # pyright: ignore[reportPrivateUsage]
                    "user@example.com", "fake-token"
                )

                # Share succeeded despite auto-accept failure
                assert result.external_user_id == "12345"

        # structlog writes to stdout; verify warning-level log with error detail
        captured = capsys.readouterr()
        assert "plex_auto_accept_invite_failed" in captured.out
        assert "warning" in captured.out
        assert "v2 API unreachable" in captured.out

    @pytest.mark.asyncio
    async def test_auto_accept_matches_by_owner_username(self) -> None:
        """v2 auto-accept matches invite by owner.username against admin username."""
        from zondarr.media.providers.plex.client import PlexClient

        admin_username = "my_special_admin"
        # Two invites: one from a different owner, one from our admin
        invites_json: list[dict[str, object]] = [
            {
                "owner": {
                    "username": "someone_else",
                    "email": "",
                    "title": "",
                    "friendlyName": "",
                },
                "sharedServers": [{"id": 11111, "machineIdentifier": "other_machine"}],
            },
            {
                "owner": {
                    "username": admin_username,
                    "email": "",
                    "title": "",
                    "friendlyName": "",
                },
                "sharedServers": [
                    {"id": 22222, "machineIdentifier": "test-machine-id"}
                ],
            },
        ]
        v2_session = MockV2InviteSessionSequenced(
            get_responses=[MockV2InviteResponse(json_data=invites_json)],
        )
        mock_user_account = MockMyPlexAccountUserForDirectShare(
            user_id=12345, username="testuser", session=v2_session
        )

        mock_session = MockSessionForDirectShare()
        mock_account = MockMyPlexAccountForDirectShare(
            session=mock_session, username=admin_username
        )
        mock_server = MockPlexServer(
            "http://plex:32400", "token123", account=mock_account
        )

        with (
            patch("plexapi.server.PlexServer", return_value=mock_server),
            patch("plexapi.myplex.MyPlexAccount", return_value=mock_user_account),
            patch("time.sleep"),
        ):
            client = PlexClient(url="http://plex:32400", api_key="token123")

            async with client:
                result = await client._share_library_direct(  # pyright: ignore[reportPrivateUsage]
                    "user@example.com", "fake-token"
                )

                assert result.external_user_id == "12345"
                # Only 1 GET call needed (matched on first attempt)
                assert v2_session.get_call_index == 1
                # auto-accept succeeded → stale invites cleaned up
                assert mock_account.pending_invites_called
