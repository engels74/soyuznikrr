"""SyncService for synchronizing local user records with media servers.

Provides functionality to compare local User records with actual users
on media servers, identifying discrepancies without making changes.
This enables administrators to detect out-of-band changes.

The sync operation is idempotent and read-only - it only reports
discrepancies, never modifies users automatically.
"""

from datetime import UTC, datetime
from uuid import UUID

from zondarr.api.schemas import SyncResult
from zondarr.core.exceptions import NotFoundError
from zondarr.media.registry import registry
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.user import UserRepository


class SyncService:
    """Synchronizes local user records with media server state.

    Compares users stored in the local database with users that exist
    on the external media server. Identifies:
    - Orphaned users: exist on server but not in local DB
    - Stale users: exist in local DB but not on server
    - Matched users: exist in both places

    The sync operation is read-only and idempotent - running it multiple
    times produces the same result without modifying any data.

    Attributes:
        server_repo: Repository for MediaServer entity operations.
        user_repo: Repository for User entity operations.
    """

    server_repo: MediaServerRepository
    user_repo: UserRepository

    def __init__(
        self,
        server_repo: MediaServerRepository,
        user_repo: UserRepository,
        /,
    ) -> None:
        """Initialize the SyncService with required repositories.

        Args:
            server_repo: Repository for MediaServer operations (positional-only).
            user_repo: Repository for User operations (positional-only).
        """
        self.server_repo = server_repo
        self.user_repo = user_repo

    async def sync_server(
        self,
        server_id: UUID,
        /,
        *,
        dry_run: bool = True,
    ) -> SyncResult:
        """Sync users between local database and media server.

        Fetches all users from the media server and compares them with
        local User records for that server. Identifies orphaned users
        (on server but not local) and stale users (local but not on server).

        The dry_run parameter is accepted for API compatibility but currently
        has no effect since sync is always read-only (Requirement 20.7).

        Args:
            server_id: The UUID of the media server to sync (positional-only).
            dry_run: If True, only report discrepancies without making changes.
                Currently always read-only regardless of this flag (keyword-only).

        Returns:
            SyncResult containing:
            - server_id: The synced server's ID
            - server_name: The synced server's name
            - synced_at: Timestamp of the sync operation
            - orphaned_users: Usernames on server but not in local DB
            - stale_users: Usernames in local DB but not on server
            - matched_users: Count of users that exist in both places

        Raises:
            NotFoundError: If the server_id does not exist.
            MediaClientError: If communication with the media server fails.
        """
        # Note: dry_run is currently unused as sync is always read-only
        # per Requirement 20.7. The parameter is kept for API compatibility
        # and potential future use when sync may support automatic cleanup.
        _ = dry_run  # Explicitly mark as intentionally unused
        # Fetch the media server from the repository
        server = await self.server_repo.get_by_id(server_id)
        if server is None:
            raise NotFoundError("MediaServer", str(server_id))

        # Create the appropriate client using the registry
        client = registry.create_client(
            server.server_type,
            url=server.url,
            api_key=server.api_key,
        )

        # Fetch users from the external media server
        async with client:
            external_users = await client.list_users()

        # Build sets for comparison using external_user_id
        external_ids = {u.external_user_id for u in external_users}
        external_names = {u.external_user_id: u.username for u in external_users}

        # Fetch local users for this server
        local_users = await self.user_repo.get_by_server(server_id)
        local_ids = {u.external_user_id for u in local_users}
        local_names = {u.external_user_id: u.username for u in local_users}

        # Identify discrepancies by comparing external_user_id sets
        # Orphaned: on server but not in local DB (Requirement 20.3)
        orphaned_ids = external_ids - local_ids
        # Stale: in local DB but not on server (Requirement 20.4)
        stale_ids = local_ids - external_ids
        # Matched: exist in both places
        matched_count = len(external_ids & local_ids)

        # Build result with usernames for human readability
        return SyncResult(
            server_id=server_id,
            server_name=server.name,
            synced_at=datetime.now(UTC),
            orphaned_users=[external_names[uid] for uid in orphaned_ids],
            stale_users=[local_names[uid] for uid in stale_ids],
            matched_users=matched_count,
        )
