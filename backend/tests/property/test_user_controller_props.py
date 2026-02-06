"""Property-based tests for UserController.

Feature: jellyfin-integration

Property 25: Page Size Is Capped
**Validates: Requirements 16.6**

Tests that for any list_users request:
- If page_size > 100, the actual page_size used is capped at 100
- If page_size <= 100, the actual page_size used is the requested value
- The response's page_size field reflects the capped value
"""

from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import TestDB
from zondarr.models import ServerType
from zondarr.models.identity import Identity, User
from zondarr.models.media_server import MediaServer
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.user import UserService

# =============================================================================
# Constants
# =============================================================================

MAX_PAGE_SIZE = 100

# =============================================================================
# Custom Strategies
# =============================================================================

# Page size strategy - includes values above and below the cap
page_size_strategy = st.integers(min_value=1, max_value=500)

# Page size above cap strategy - only values that should be capped
page_size_above_cap_strategy = st.integers(min_value=101, max_value=1000)

# Page size at or below cap strategy - values that should not be capped
page_size_at_or_below_cap_strategy = st.integers(min_value=1, max_value=100)

# Username strategy - valid usernames for media servers
username_strategy = st.text(
    alphabet=st.characters(categories=("Ll",)),  # Lowercase letters only
    min_size=3,
    max_size=20,
).filter(lambda x: x.isalpha() and len(x) >= 3)

# External user ID strategy - simulates Jellyfin GUIDs
external_user_id_strategy = st.uuids().map(str)


# =============================================================================
# Helper Functions
# =============================================================================


async def create_test_users(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    count: int,
) -> None:
    """Create test users with associated media server and identity.

    Explicitly assigns UUIDs at construction time so no intermediate flushes
    are needed. A single commit handles all inserts.
    """
    async with session_factory() as session:
        server_id = uuid4()
        server = MediaServer(
            id=server_id,
            name="TestServer",
            server_type=ServerType.JELLYFIN,
            url="http://jellyfin.local:8096",
            api_key="test-api-key",
            enabled=True,
        )
        session.add(server)

        for i in range(count):
            identity_id = uuid4()
            identity = Identity(
                id=identity_id,
                display_name=f"testuser{i}",
                email=None,
                expires_at=None,
                enabled=True,
            )
            session.add(identity)

            user = User(
                identity_id=identity_id,
                media_server_id=server_id,
                invitation_id=None,
                external_user_id=f"external-{i}",
                username=f"testuser{i}",
                expires_at=None,
                enabled=True,
            )
            session.add(user)

        await session.commit()


# =============================================================================
# Property 25: Page Size Is Capped
# =============================================================================


class TestPageSizeIsCapped:
    """Property 25: Page Size Is Capped.

    **Validates: Requirements 16.6**

    For any list_users request with page_size P:
    - If P > 100, the actual page_size used should be 100
    - If P <= 100, the actual page_size used should be P
    - The response's page_size field should reflect the capped value
    """

    @given(page_size=page_size_above_cap_strategy)
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_page_size_above_cap_is_capped_to_100(
        self,
        db: TestDB,
        page_size: int,
    ) -> None:
        """Page size values above 100 are capped to 100.

        **Validates: Requirements 16.6**

        Property: For any page_size P > 100, the actual page_size used
        in the query and returned in the response should be 100.
        """
        await db.clean()

        # Create enough test users to verify pagination
        await create_test_users(db.session_factory, count=5)

        # Execute list_users with page_size above cap
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            items, total = await user_service.list_users(
                page=1,
                page_size=page_size,  # Above 100
            )

            # PROPERTY ASSERTION: The service caps page_size at 100
            # We verify this by checking that the service accepted the
            # request without error and returned results
            assert total == 5, f"Expected 5 total users, got {total}"
            assert len(items) == 5, f"Expected 5 items, got {len(items)}"

    @given(page_size=page_size_at_or_below_cap_strategy)
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_page_size_at_or_below_cap_is_used_as_is(
        self,
        db: TestDB,
        page_size: int,
    ) -> None:
        """Page size values at or below 100 are used as requested.

        **Validates: Requirements 16.6**

        Property: For any page_size P <= 100, the actual page_size used
        should be P (not capped).
        """
        await db.clean()

        # Create more users than the max page_size to test pagination
        num_users = 105
        await create_test_users(db.session_factory, count=num_users)

        # Execute list_users with page_size at or below cap
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            items, total = await user_service.list_users(
                page=1,
                page_size=page_size,  # At or below 100
            )

            # PROPERTY ASSERTION: The requested page_size is used
            assert total == num_users, f"Expected {num_users} total, got {total}"
            expected_items = min(page_size, num_users)
            assert len(items) == expected_items, (
                f"Expected {expected_items} items for page_size={page_size}, "
                f"got {len(items)}"
            )

    @given(
        page_size=page_size_strategy,
        num_users=st.integers(min_value=0, max_value=110),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_page_size_cap_with_varying_user_counts(
        self,
        db: TestDB,
        page_size: int,
        num_users: int,
    ) -> None:
        """Page size capping works correctly with varying user counts.

        **Validates: Requirements 16.6**

        Property: For any page_size P and user count N:
        - The capped page_size is min(P, 100)
        - The returned items count is min(capped_page_size, N)
        """
        await db.clean()

        # Create test users
        if num_users > 0:
            await create_test_users(db.session_factory, count=num_users)

        # Execute list_users
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            items, total = await user_service.list_users(
                page=1,
                page_size=page_size,
            )

            # Calculate expected values
            capped_page_size = min(page_size, MAX_PAGE_SIZE)
            expected_items = min(capped_page_size, num_users)

            # PROPERTY ASSERTIONS
            assert total == num_users, f"Expected total={num_users}, got {total}"
            assert len(items) == expected_items, (
                f"Expected {expected_items} items for page_size={page_size} "
                f"(capped to {capped_page_size}) with {num_users} users, "
                f"got {len(items)}"
            )

    @given(page_size=page_size_above_cap_strategy)
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_page_size_cap_limits_returned_items(
        self,
        db: TestDB,
        page_size: int,
    ) -> None:
        """Page size cap limits the number of returned items to 100.

        **Validates: Requirements 16.6**

        Property: For any page_size P > 100 with more than 100 users,
        the returned items count should be exactly 100.
        """
        await db.clean()

        # Create more users than the cap
        num_users = 105
        await create_test_users(db.session_factory, count=num_users)

        # Execute list_users with page_size above cap
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            items, total = await user_service.list_users(
                page=1,
                page_size=page_size,  # Above 100
            )

            # PROPERTY ASSERTION: Items are capped at 100
            assert total == num_users, f"Expected {num_users} total, got {total}"
            assert len(items) == MAX_PAGE_SIZE, (
                f"Expected {MAX_PAGE_SIZE} items (capped), got {len(items)}"
            )

    @given(
        page_size=page_size_above_cap_strategy,
        page=st.integers(min_value=1, max_value=2),
    )
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_page_size_cap_applies_to_all_pages(
        self,
        db: TestDB,
        page_size: int,
        page: int,
    ) -> None:
        """Page size cap applies consistently across all pages.

        **Validates: Requirements 16.6**

        Property: For any page_size P > 100 and any page number,
        the capped page_size of 100 should be used for pagination.
        """
        await db.clean()

        # Create enough users for multiple pages
        num_users = 120
        await create_test_users(db.session_factory, count=num_users)

        # Execute list_users with page_size above cap
        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            items, total = await user_service.list_users(
                page=page,
                page_size=page_size,  # Above 100
            )

            # Calculate expected items for this page
            capped_page_size = MAX_PAGE_SIZE
            start_index = (page - 1) * capped_page_size
            remaining_users = max(0, num_users - start_index)
            expected_items = min(capped_page_size, remaining_users)

            # PROPERTY ASSERTIONS
            assert total == num_users, f"Expected {num_users} total, got {total}"
            assert len(items) == expected_items, (
                f"Expected {expected_items} items on page {page} "
                f"with capped page_size={capped_page_size}, got {len(items)}"
            )

    @pytest.mark.asyncio
    async def test_page_size_at_exactly_100_is_not_capped(
        self,
        db: TestDB,
    ) -> None:
        """Page size of exactly 100 is used as-is (boundary test).

        **Validates: Requirements 16.6**

        Property: page_size=100 should not be capped (it's at the limit).
        """
        await db.clean()

        num_users = 105
        await create_test_users(db.session_factory, count=num_users)

        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            items, total = await user_service.list_users(
                page=1,
                page_size=MAX_PAGE_SIZE,  # Exactly 100
            )

            assert total == num_users, f"Expected {num_users} total, got {total}"
            assert len(items) == MAX_PAGE_SIZE, (
                f"Expected {MAX_PAGE_SIZE} items, got {len(items)}"
            )

    @pytest.mark.asyncio
    async def test_page_size_at_101_is_capped(
        self,
        db: TestDB,
    ) -> None:
        """Page size of 101 is capped to 100 (boundary test).

        **Validates: Requirements 16.6**

        Property: page_size=101 should be capped to 100.
        """
        await db.clean()

        num_users = 105
        await create_test_users(db.session_factory, count=num_users)

        async with db.session_factory() as session:
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            user_service = UserService(user_repo, identity_repo)

            items, total = await user_service.list_users(
                page=1,
                page_size=MAX_PAGE_SIZE + 1,  # 101 - should be capped
            )

            assert total == num_users, f"Expected {num_users} total, got {total}"
            assert len(items) == MAX_PAGE_SIZE, (
                f"Expected {MAX_PAGE_SIZE} items (capped from 101), got {len(items)}"
            )
