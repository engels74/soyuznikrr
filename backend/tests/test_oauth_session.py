"""Tests for OAuth session store with opaque handles.

Tests cover: handle generation, session lookup, authentication,
one-time redemption, expiry, and provider binding.
"""

import time

import pytest

from zondarr.services.oauth_session import OAuthSession, OAuthSessionStore


@pytest.fixture
def store() -> OAuthSessionStore:
    """Fresh session store for each test."""
    return OAuthSessionStore()


class TestHandleGeneration:
    """Handles are high-entropy and unique."""

    def test_create_returns_nonempty_handle(self, store: OAuthSessionStore) -> None:
        handle = store.create("plex", 12345)
        assert isinstance(handle, str)
        assert len(handle) > 20

    def test_handles_are_unique(self, store: OAuthSessionStore) -> None:
        handles = {store.create("plex", i) for i in range(50)}
        assert len(handles) == 50


class TestSessionLookup:
    """Session lookup by handle."""

    def test_get_returns_session(self, store: OAuthSessionStore) -> None:
        handle = store.create("plex", 42)
        session = store.get(handle)
        assert session is not None
        assert session.provider == "plex"
        assert session.pin_id == 42

    def test_get_unknown_handle_returns_none(self, store: OAuthSessionStore) -> None:
        assert store.get("nonexistent-handle") is None

    def test_provider_is_preserved(self, store: OAuthSessionStore) -> None:
        h1 = store.create("plex", 1)
        h2 = store.create("jellyfin", 2)
        assert store.get(h1) is not None
        assert store.get(h1).provider == "plex"  # pyright: ignore[reportOptionalMemberAccess]
        assert store.get(h2) is not None
        assert store.get(h2).provider == "jellyfin"  # pyright: ignore[reportOptionalMemberAccess]


class TestAuthentication:
    """Marking sessions as authenticated."""

    def test_set_authenticated_returns_redemption_token(
        self, store: OAuthSessionStore
    ) -> None:
        handle = store.create("plex", 1)
        token = store.set_authenticated(
            handle, auth_token="raw_plex_token", email="user@example.com"
        )
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 20

    def test_set_authenticated_stores_data(self, store: OAuthSessionStore) -> None:
        handle = store.create("plex", 1)
        _ = store.set_authenticated(
            handle, auth_token="raw_token", email="user@example.com"
        )
        session = store.get(handle)
        assert session is not None
        assert session.auth_token == "raw_token"  # noqa: S105
        assert session.email == "user@example.com"

    def test_set_authenticated_unknown_handle(self, store: OAuthSessionStore) -> None:
        result = store.set_authenticated("bad-handle", auth_token="x", email="y")
        assert result is None


class TestOneTimeRedemption:
    """Redemption tokens are consumed once."""

    def test_redeem_returns_provider_and_auth_token(
        self, store: OAuthSessionStore
    ) -> None:
        handle = store.create("plex", 1)
        redemption_token = store.set_authenticated(
            handle, auth_token="raw_token_abc", email="a@b.com"
        )
        assert redemption_token is not None
        result = store.redeem(redemption_token)
        assert result is not None
        provider, auth_token = result
        assert provider == "plex"
        assert auth_token == "raw_token_abc"  # noqa: S105

    def test_redeem_clears_auth_token_from_session(
        self, store: OAuthSessionStore
    ) -> None:
        handle = store.create("plex", 1)
        redemption_token = store.set_authenticated(
            handle, auth_token="secret", email="a@b.com"
        )
        assert redemption_token is not None
        _ = store.redeem(redemption_token)
        session = store.get(handle)
        assert session is not None
        assert session.auth_token is None
        assert session.redeemed is True

    def test_redeem_second_time_returns_none(self, store: OAuthSessionStore) -> None:
        handle = store.create("plex", 1)
        redemption_token = store.set_authenticated(
            handle, auth_token="x", email="a@b.com"
        )
        assert redemption_token is not None
        assert store.redeem(redemption_token) is not None
        assert store.redeem(redemption_token) is None

    def test_redeem_invalid_token_returns_none(self, store: OAuthSessionStore) -> None:
        assert store.redeem("totally-fake-token") is None


class TestExpiry:
    """TTL-based session expiry."""

    def test_expired_session_returns_none(self, store: OAuthSessionStore) -> None:
        handle = store.create("plex", 1, ttl=0)
        # Session with ttl=0 is immediately expired (monotonic has advanced)
        time.sleep(0.01)
        assert store.get(handle) is None

    def test_expired_session_not_redeemable(self, store: OAuthSessionStore) -> None:
        handle = store.create("plex", 1, ttl=0)
        redemption_token = store.set_authenticated(
            handle, auth_token="x", email="a@b.com"
        )
        time.sleep(0.01)
        # Even with valid redemption token, expired session can't be redeemed
        if redemption_token is not None:
            assert store.redeem(redemption_token) is None

    def test_is_expired_property(self) -> None:
        session = OAuthSession(
            provider="plex",
            pin_id=1,
            created_at=time.monotonic() - 1000,
            ttl=1,
        )
        assert session.is_expired is True

    def test_not_expired_property(self) -> None:
        session = OAuthSession(provider="plex", pin_id=1, ttl=9999)
        assert session.is_expired is False


class TestRemove:
    """Explicit session removal."""

    def test_remove_deletes_session(self, store: OAuthSessionStore) -> None:
        handle = store.create("plex", 1)
        store.remove(handle)
        assert store.get(handle) is None

    def test_remove_nonexistent_is_noop(self, store: OAuthSessionStore) -> None:
        store.remove("does-not-exist")  # Should not raise
