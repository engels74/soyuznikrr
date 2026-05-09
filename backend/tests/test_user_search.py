"""Tests for user list search and email response aliases."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.api.users import UserController
from zondarr.media.providers.plex import PlexProvider
from zondarr.media.registry import registry
from zondarr.models.identity import Identity, User
from zondarr.models.invitation import Invitation
from zondarr.models.media_server import MediaServer
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.user import UserService


async def _make_user(
    session: AsyncSession,
    *,
    username: str,
    external_user_id: str,
    identity_name: str,
    email: str | None,
    server_name: str,
    server_type: str = "plex",
    invitation_code: str | None = None,
    enabled: bool = True,
) -> User:
    server = MediaServer(
        name=server_name,
        server_type=server_type,
        url=f"http://{server_name.lower()}.local",
        api_key="token",
        enabled=True,
    )
    identity = Identity(display_name=identity_name, email=email, enabled=True)
    invitation = (
        Invitation(code=invitation_code, enabled=True) if invitation_code else None
    )
    session.add_all([server, identity])
    if invitation is not None:
        session.add(invitation)
    await session.flush()

    user = User(
        identity_id=identity.id,
        media_server_id=server.id,
        invitation_id=invitation.id if invitation is not None else None,
        external_user_id=external_user_id,
        username=username,
        enabled=enabled,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_list_users_search_matches_supported_fields(
    session: AsyncSession,
) -> None:
    """Broad search matches users, identities, servers, and invitation codes."""
    user = await _make_user(
        session,
        username="plexuser",
        external_user_id="external-123",
        identity_name="Plex Person",
        email="person@example.com",
        server_name="LivingRoom",
        invitation_code="WELCOME42",
    )
    _ = await _make_user(
        session,
        username="otheruser",
        external_user_id="external-999",
        identity_name="Other Person",
        email="other@example.com",
        server_name="Bedroom",
        server_type="jellyfin",
        invitation_code="OTHER42",
    )

    service = UserService(UserRepository(session), IdentityRepository(session))

    for term in [
        "PLEXUSER",
        "external-123",
        "plex person",
        "PERSON@EXAMPLE.COM",
        "livingroom",
        "plex",
        "welcome42",
    ]:
        items, total = await service.list_users(search=term)
        assert total == 1
        assert items[0].id == user.id


@pytest.mark.asyncio
async def test_list_users_search_composes_with_existing_filters(
    session: AsyncSession,
) -> None:
    """Search uses AND semantics with existing filters."""
    _ = await _make_user(
        session,
        username="targetuser",
        external_user_id="target-1",
        identity_name="Target Enabled",
        email="target-enabled@example.com",
        server_name="Main",
        enabled=True,
    )
    _ = await _make_user(
        session,
        username="targetuser2",
        external_user_id="target-2",
        identity_name="Target Disabled",
        email="target-disabled@example.com",
        server_name="Main",
        enabled=False,
    )

    service = UserService(UserRepository(session), IdentityRepository(session))

    items, total = await service.list_users(search="target", enabled=False)

    assert total == 1
    assert items[0].username == "targetuser2"


@pytest.mark.asyncio
async def test_user_detail_response_exposes_top_level_email(
    session: AsyncSession,
) -> None:
    """UserDetailResponse.email mirrors identity.email."""
    registry.register(PlexProvider())
    user = await _make_user(
        session,
        username="plexuser",
        external_user_id="external-123",
        identity_name="Plex Person",
        email="person@example.com",
        server_name="LivingRoom",
    )
    service = UserService(UserRepository(session), IdentityRepository(session))
    loaded_user = await service.get_user_detail(user.id)

    response = UserController._to_detail_response(loaded_user)  # pyright: ignore[reportPrivateUsage]

    assert response.email == "person@example.com"
    assert response.identity.email == "person@example.com"
