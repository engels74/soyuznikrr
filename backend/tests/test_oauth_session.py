"""Tests for database-backed OAuth session store.

Tests cover: handle generation, session lookup, authentication,
one-time redemption, expiry, and provider binding.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.models.oauth_session import OAuthSessionModel
from zondarr.services.oauth_session import OAuthSessionStore


@pytest.fixture
def store() -> OAuthSessionStore:
    """Fresh session store for each test."""
    return OAuthSessionStore()


class TestHandleGeneration:
    """Handles are high-entropy and unique."""

    async def test_create_returns_nonempty_handle(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handle = await store.create(session, "plex", 12345)
        assert isinstance(handle, str)
        assert len(handle) > 20

    async def test_handles_are_unique(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handles: set[str] = set()
        for i in range(50):
            handles.add(await store.create(session, "plex", i))
        assert len(handles) == 50


class TestSessionLookup:
    """Session lookup by handle."""

    async def test_get_returns_session(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handle = await store.create(session, "plex", 42)
        oauth_session = await store.get(session, handle)
        assert oauth_session is not None
        assert oauth_session.provider == "plex"
        assert oauth_session.pin_id == 42

    async def test_get_unknown_handle_returns_none(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        assert await store.get(session, "nonexistent-handle") is None

    async def test_provider_is_preserved(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        h1 = await store.create(session, "plex", 1)
        h2 = await store.create(session, "jellyfin", 2)
        s1 = await store.get(session, h1)
        s2 = await store.get(session, h2)
        assert s1 is not None
        assert s1.provider == "plex"
        assert s2 is not None
        assert s2.provider == "jellyfin"


class TestAuthentication:
    """Marking sessions as authenticated."""

    async def test_set_authenticated_returns_redemption_token(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handle = await store.create(session, "plex", 1)
        token = await store.set_authenticated(
            session, handle, auth_token="raw_plex_token", email="user@example.com"
        )
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 20

    async def test_set_authenticated_stores_data(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handle = await store.create(session, "plex", 1)
        _ = await store.set_authenticated(
            session, handle, auth_token="raw_token", email="user@example.com"
        )
        oauth_session = await store.get(session, handle)
        assert oauth_session is not None
        assert oauth_session.auth_token == "raw_token"  # noqa: S105
        assert oauth_session.email == "user@example.com"

    async def test_set_authenticated_unknown_handle(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        result = await store.set_authenticated(
            session, "bad-handle", auth_token="x", email="y"
        )
        assert result is None


class TestOneTimeRedemption:
    """Redemption tokens are consumed once."""

    async def test_redeem_returns_provider_auth_token_and_email(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handle = await store.create(session, "plex", 1)
        redemption_token = await store.set_authenticated(
            session, handle, auth_token="raw_token_abc", email="a@b.com"
        )
        assert redemption_token is not None
        result = await store.redeem(session, redemption_token)
        assert result is not None
        provider, auth_token, email = result
        assert provider == "plex"
        assert auth_token == "raw_token_abc"  # noqa: S105
        assert email == "a@b.com"

    async def test_redeem_returns_none_email_when_not_supplied(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handle = await store.create(session, "plex", 1)
        redemption_token = await store.set_authenticated(
            session, handle, auth_token="raw_token_abc", email=None
        )
        assert redemption_token is not None
        result = await store.redeem(session, redemption_token)
        assert result is not None
        provider, auth_token, email = result
        assert provider == "plex"
        assert auth_token == "raw_token_abc"  # noqa: S105
        assert email is None

    async def test_redeem_preserves_email_after_consumption(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        """Email is kept on the session after redemption for audit."""
        handle = await store.create(session, "plex", 1)
        redemption_token = await store.set_authenticated(
            session, handle, auth_token="x", email="audit@example.com"
        )
        assert redemption_token is not None
        _ = await store.redeem(session, redemption_token)
        oauth_session = await store.get(session, handle)
        assert oauth_session is not None
        assert oauth_session.email == "audit@example.com"

    async def test_redeem_clears_auth_token_from_session(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handle = await store.create(session, "plex", 1)
        redemption_token = await store.set_authenticated(
            session, handle, auth_token="secret", email="a@b.com"
        )
        assert redemption_token is not None
        _ = await store.redeem(session, redemption_token)
        oauth_session = await store.get(session, handle)
        assert oauth_session is not None
        assert oauth_session.auth_token is None
        assert oauth_session.redeemed is True

    async def test_redeem_second_time_returns_none(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handle = await store.create(session, "plex", 1)
        redemption_token = await store.set_authenticated(
            session, handle, auth_token="x", email="a@b.com"
        )
        assert redemption_token is not None
        assert await store.redeem(session, redemption_token) is not None
        assert await store.redeem(session, redemption_token) is None

    async def test_redeem_invalid_token_returns_none(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        assert await store.redeem(session, "totally-fake-token") is None


class TestExpiry:
    """TTL-based session expiry."""

    async def test_expired_session_returns_none(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handle = await store.create(session, "plex", 1, ttl=0)
        # Manually backdate created_at to ensure expiry
        from sqlalchemy import update

        stmt = (
            update(OAuthSessionModel)
            .where(OAuthSessionModel.handle == handle)
            .values(created_at=datetime.now(UTC) - timedelta(seconds=10))
        )
        _ = await session.execute(stmt)
        await session.flush()
        assert await store.get(session, handle) is None

    async def test_expired_session_not_redeemable(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handle = await store.create(session, "plex", 1, ttl=600)
        redemption_token = await store.set_authenticated(
            session, handle, auth_token="x", email="a@b.com"
        )
        # Backdate created_at to make it expired
        from sqlalchemy import update

        stmt = (
            update(OAuthSessionModel)
            .where(OAuthSessionModel.handle == handle)
            .values(created_at=datetime.now(UTC) - timedelta(seconds=700))
        )
        _ = await session.execute(stmt)
        await session.flush()
        if redemption_token is not None:
            assert await store.redeem(session, redemption_token) is None


class TestRemove:
    """Explicit session removal."""

    async def test_remove_deletes_session(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        handle = await store.create(session, "plex", 1)
        await store.remove(session, handle)
        assert await store.get(session, handle) is None

    async def test_remove_nonexistent_is_noop(
        self, store: OAuthSessionStore, session: AsyncSession
    ) -> None:
        await store.remove(session, "does-not-exist")  # Should not raise
