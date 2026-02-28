"""Property-based tests for database migrations.

Feature: zondarr-foundation
Property: 14
"""

from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.conftest import KNOWN_SERVER_TYPES, TestDB, create_test_engine
from zondarr.models import (
    Identity,
    Invitation,
    Library,
    MediaServer,
    User,
)
from zondarr.models.base import Base

# Custom strategies for model fields
server_type_strategy = st.sampled_from(KNOWN_SERVER_TYPES)
name_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=1,
    max_size=50,
).filter(lambda x: x.strip())
url_strategy = st.from_regex(r"https?://[a-z0-9]+\.[a-z]{2,}", fullmatch=True)
# Use UUIDs for codes to ensure uniqueness across Hypothesis examples
code_strategy = st.uuids().map(lambda u: str(u).replace("-", "")[:12].upper())
positive_int_strategy = st.integers(min_value=0, max_value=1000)
optional_positive_int_strategy = st.one_of(st.none(), positive_int_strategy)


async def rollback_migration(engine: AsyncEngine) -> None:
    """Rollback migration by dropping all tables (simulates downgrade)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def verify_tables_exist(session: AsyncSession) -> dict[str, bool]:
    """Verify that all expected tables exist in the database."""
    expected_tables = [
        "media_servers",
        "libraries",
        "identities",
        "invitations",
        "users",
        "sync_exclusions",
        "sync_runs",
        "invitation_servers",
        "invitation_libraries",
    ]
    results: dict[str, bool] = {}
    for table in expected_tables:
        try:
            _ = await session.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))  # noqa: S608
            results[table] = True
        except Exception:
            results[table] = False
    return results


class TestMigrationsPreserveData:
    """
    Feature: zondarr-foundation
    Property 14: Migrations Preserve Data
    """

    @given(
        name=name_strategy,
        server_type=server_type_strategy,
        url=url_strategy,
        api_key=name_strategy,
        enabled=st.booleans(),
    )
    @pytest.mark.asyncio
    async def test_media_server_data_survives_migration_cycle(
        self,
        db: TestDB,
        name: str,
        server_type: str,
        url: str,
        api_key: str,
        enabled: bool,
    ) -> None:
        """MediaServer data is preserved through migration upgrade."""
        await db.clean()
        server_id = uuid4()
        async with db.session_factory() as session:
            server = MediaServer()
            server.id = server_id
            server.name = name
            server.server_type = server_type
            server.url = url
            server.api_key = api_key
            server.enabled = enabled
            session.add(server)
            await session.commit()

        async with db.session_factory() as session:
            result = await session.get(MediaServer, server_id)
            assert result is not None
            assert result.name == name
            assert result.server_type == server_type
            assert result.url == url
            assert result.api_key == api_key
            assert result.enabled == enabled

    @given(
        data=st.data(),
        code=code_strategy,
        max_uses=optional_positive_int_strategy,
        enabled=st.booleans(),
    )
    @pytest.mark.asyncio
    async def test_invitation_data_survives_migration_cycle(
        self,
        db: TestDB,
        data: st.DataObject,
        code: str,
        max_uses: int | None,
        enabled: bool,
    ) -> None:
        """Invitation data is preserved through migration upgrade."""
        # use_count must not exceed max_uses (DB CHECK constraint)
        upper = max_uses if max_uses is not None else 1000
        use_count = data.draw(st.integers(min_value=0, max_value=upper))

        await db.clean()
        invitation_id = uuid4()
        async with db.session_factory() as session:
            invitation = Invitation()
            invitation.id = invitation_id
            invitation.code = code
            invitation.max_uses = max_uses
            invitation.use_count = use_count
            invitation.enabled = enabled
            session.add(invitation)
            await session.commit()

        async with db.session_factory() as session:
            result = await session.get(Invitation, invitation_id)
            assert result is not None
            assert result.code == code
            assert result.max_uses == max_uses
            assert result.use_count == use_count
            assert result.enabled == enabled

    @given(
        display_name=name_strategy,
        enabled=st.booleans(),
    )
    @pytest.mark.asyncio
    async def test_identity_data_survives_migration_cycle(
        self,
        db: TestDB,
        display_name: str,
        enabled: bool,
    ) -> None:
        """Identity data is preserved through migration upgrade."""
        await db.clean()
        identity_id = uuid4()
        async with db.session_factory() as session:
            identity = Identity()
            identity.id = identity_id
            identity.display_name = display_name
            identity.enabled = enabled
            session.add(identity)
            await session.commit()

        async with db.session_factory() as session:
            result = await session.get(Identity, identity_id)
            assert result is not None
            assert result.display_name == display_name
            assert result.enabled == enabled

    @given(
        external_user_id=name_strategy,
        username=name_strategy,
        enabled=st.booleans(),
    )
    @pytest.mark.asyncio
    async def test_user_data_survives_migration_cycle(
        self,
        db: TestDB,
        external_user_id: str,
        username: str,
        enabled: bool,
    ) -> None:
        """User data with relationships is preserved through migration upgrade."""
        await db.clean()
        identity_id = uuid4()
        server_id = uuid4()
        user_id = uuid4()

        async with db.session_factory() as session:
            identity = Identity()
            identity.id = identity_id
            identity.display_name = "Test Identity"
            identity.enabled = True
            session.add(identity)

            server = MediaServer()
            server.id = server_id
            server.name = "Test Server"
            server.server_type = "jellyfin"
            server.url = "http://test.local"
            server.api_key = "testkey"
            server.enabled = True
            session.add(server)
            await session.commit()

        async with db.session_factory() as session:
            user = User()
            user.id = user_id
            user.identity_id = identity_id
            user.media_server_id = server_id
            user.external_user_id = external_user_id
            user.username = username
            user.enabled = enabled
            session.add(user)
            await session.commit()

        async with db.session_factory() as session:
            result = await session.get(User, user_id)
            assert result is not None
            assert result.identity_id == identity_id
            assert result.media_server_id == server_id
            assert result.external_user_id == external_user_id
            assert result.username == username
            assert result.enabled == enabled

    @given(
        external_id=name_strategy,
        library_name=name_strategy,
        library_type=st.sampled_from(["movies", "tvshows", "music", "photos"]),
    )
    @pytest.mark.asyncio
    async def test_library_data_survives_migration_cycle(
        self,
        db: TestDB,
        external_id: str,
        library_name: str,
        library_type: str,
    ) -> None:
        """Library data with foreign key relationships is preserved."""
        await db.clean()
        server_id = uuid4()
        library_id = uuid4()

        async with db.session_factory() as session:
            server = MediaServer()
            server.id = server_id
            server.name = "Test Server"
            server.server_type = "plex"
            server.url = "http://plex.local"
            server.api_key = "plexkey"
            server.enabled = True
            session.add(server)
            await session.commit()

        async with db.session_factory() as session:
            library = Library()
            library.id = library_id
            library.media_server_id = server_id
            library.external_id = external_id
            library.name = library_name
            library.library_type = library_type
            session.add(library)
            await session.commit()

        async with db.session_factory() as session:
            result = await session.get(Library, library_id)
            assert result is not None
            assert result.media_server_id == server_id
            assert result.external_id == external_id
            assert result.name == library_name
            assert result.library_type == library_type


class TestMigrationRollback:
    """Property 14: Migrations Support Rollback."""

    @pytest.mark.asyncio
    async def test_migration_rollback_removes_all_tables(self) -> None:
        """Migration rollback successfully removes all foundation tables."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                tables_before = await verify_tables_exist(session)
                assert all(tables_before.values())

            await rollback_migration(engine)

            async with session_factory() as session:
                tables_after = await verify_tables_exist(session)
                assert not any(tables_after.values())
        finally:
            await engine.dispose()


class TestMigrationSchemaIntegrity:
    """Property 14: Migration Schema Integrity."""

    @pytest.mark.asyncio
    async def test_all_foundation_tables_created(self) -> None:
        """Migration creates all foundation tables."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                tables = await verify_tables_exist(session)

                assert tables["media_servers"]
                assert tables["libraries"]
                assert tables["identities"]
                assert tables["invitations"]
                assert tables["users"]
                assert tables["sync_exclusions"]
                assert tables["sync_runs"]
                assert tables["invitation_servers"]
                assert tables["invitation_libraries"]
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_foreign_key_constraints_enforced(self) -> None:
        """Foreign key constraints are properly enforced after migration."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                user = User()
                user.identity_id = uuid4()  # Non-existent
                user.media_server_id = uuid4()  # Non-existent
                user.external_user_id = "ext123"
                user.username = "testuser"
                user.enabled = True
                session.add(user)

                with pytest.raises(Exception):  # noqa: B017
                    await session.commit()
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_unique_constraint_on_invitation_code(self) -> None:
        """Unique constraint on invitation code is enforced."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                invitation1 = Invitation()
                invitation1.code = "UNIQUE123"
                invitation1.use_count = 0
                invitation1.enabled = True
                session.add(invitation1)
                await session.commit()

            async with session_factory() as session:
                invitation2 = Invitation()
                invitation2.code = "UNIQUE123"  # Same code
                invitation2.use_count = 0
                invitation2.enabled = True
                session.add(invitation2)

                with pytest.raises(Exception):  # noqa: B017
                    await session.commit()
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_cascade_delete_on_media_server(self) -> None:
        """Cascade delete removes related libraries when media server is deleted."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            server_id = uuid4()
            library_id = uuid4()

            async with session_factory() as session:
                server = MediaServer()
                server.id = server_id
                server.name = "Test Server"
                server.server_type = "jellyfin"
                server.url = "http://test.local"
                server.api_key = "testkey"
                server.enabled = True
                session.add(server)
                await session.commit()

            async with session_factory() as session:
                library = Library()
                library.id = library_id
                library.media_server_id = server_id
                library.external_id = "lib123"
                library.name = "Movies"
                library.library_type = "movies"
                session.add(library)
                await session.commit()

            async with session_factory() as session:
                server = await session.get(MediaServer, server_id)
                assert server is not None
                await session.delete(server)
                await session.commit()

            async with session_factory() as session:
                library = await session.get(Library, library_id)
                assert library is None
        finally:
            await engine.dispose()
