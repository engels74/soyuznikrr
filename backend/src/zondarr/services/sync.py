"""SyncService for synchronizing local user records with media servers.

Provides functionality to compare local User records with actual users
on media servers, identifying discrepancies. When dry_run=False, imports
orphaned users (those on the server but not in the local DB) by creating
Identity and User records.
"""

from datetime import UTC, datetime
from uuid import UUID

import structlog

from zondarr.api.schemas import SyncResult
from zondarr.core.exceptions import NotFoundError
from zondarr.media.registry import registry
from zondarr.models.identity import Identity, User
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.sync_exclusion import SyncExclusionRepository
from zondarr.repositories.user import UserRepository

log = structlog.get_logger()  # pyright: ignore[reportAny]  # structlog lacks stubs


class SyncService:
    """Synchronizes local user records with media server state.

    Compares users stored in the local database with users that exist
    on the external media server. Identifies:
    - Orphaned users: exist on server but not in local DB
    - Stale users: exist in local DB but not on server
    - Matched users: exist in both places

    When dry_run=False, imports orphaned users by creating Identity
    and User records in the local database.

    Attributes:
        server_repo: Repository for MediaServer entity operations.
        user_repo: Repository for User entity operations.
        identity_repo: Repository for Identity entity operations.
    """

    server_repo: MediaServerRepository
    user_repo: UserRepository
    identity_repo: IdentityRepository
    sync_exclusion_repo: SyncExclusionRepository | None

    def __init__(
        self,
        server_repo: MediaServerRepository,
        user_repo: UserRepository,
        identity_repo: IdentityRepository,
        /,
        *,
        sync_exclusion_repo: SyncExclusionRepository | None = None,
    ) -> None:
        """Initialize the SyncService with required repositories.

        Args:
            server_repo: Repository for MediaServer operations (positional-only).
            user_repo: Repository for User operations (positional-only).
            identity_repo: Repository for Identity operations (positional-only).
            sync_exclusion_repo: Optional repository for sync exclusions (keyword-only).
        """
        self.server_repo = server_repo
        self.user_repo = user_repo
        self.identity_repo = identity_repo
        self.sync_exclusion_repo = sync_exclusion_repo

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

        When dry_run=False, imports orphaned users by creating an Identity
        and User record for each one.

        Args:
            server_id: The UUID of the media server to sync (positional-only).
            dry_run: If True, only report discrepancies without making changes.
                If False, import orphaned users into the local DB (keyword-only).

        Returns:
            SyncResult containing:
            - server_id: The synced server's ID
            - server_name: The synced server's name
            - synced_at: Timestamp of the sync operation
            - orphaned_users: Usernames on server but not in local DB
            - stale_users: Usernames in local DB but not on server
            - matched_users: Count of users that exist in both places
            - imported_users: Count of orphaned users imported (0 if dry_run)

        Raises:
            NotFoundError: If the server_id does not exist.
            MediaClientError: If communication with the media server fails.
        """
        # Fetch the media server from the repository
        server = await self.server_repo.get_by_id(server_id)
        if server is None:
            raise NotFoundError("MediaServer", str(server_id))

        # Create the appropriate client using the registry
        client = registry.create_client_for_server(server)

        # Fetch users from the external media server
        async with client:
            external_users = await client.list_users()

        # Build maps for comparison using external_user_id
        external_map = {u.external_user_id: u for u in external_users}
        external_ids = set(external_map.keys())

        # Fetch local users for this server
        local_users = await self.user_repo.get_by_server(server_id)
        local_ids = {u.external_user_id for u in local_users}
        local_names = {u.external_user_id: u.username for u in local_users}

        # Identify discrepancies by comparing external_user_id sets
        # Orphaned: on server but not in local DB
        orphaned_ids = external_ids - local_ids
        # Stale: in local DB but not on server
        stale_ids = local_ids - external_ids
        # Matched: exist in both places
        matched_ids = external_ids & local_ids
        matched_count = len(matched_ids)

        # Update external_user_type for matched users whose type is missing or changed
        if matched_ids and not dry_run:
            local_user_map = {u.external_user_id: u for u in local_users}
            for ext_id in matched_ids:
                local_user = local_user_map.get(ext_id)
                ext_user = external_map[ext_id]
                if (
                    local_user is not None
                    and ext_user.user_type is not None
                    and local_user.external_user_type != ext_user.user_type
                ):
                    local_user.external_user_type = ext_user.user_type
                    _ = await self.user_repo.update(local_user)

        # Filter orphaned users against sync exclusions to prevent
        # re-import of deleted users (Plex API caching bug workaround)
        if orphaned_ids and self.sync_exclusion_repo is not None:
            excluded_ids = await self.sync_exclusion_repo.get_excluded_ids(server_id)
            excluded_matches = orphaned_ids & excluded_ids
            if excluded_matches:
                log.info(  # pyright: ignore[reportAny]
                    "sync_skipping_excluded_users",
                    server_name=server.name,
                    excluded_count=len(excluded_matches),
                    excluded_ids=sorted(excluded_matches),
                )
                orphaned_ids -= excluded_matches

        # Import orphaned users when not a dry run
        imported_count = 0
        if not dry_run and orphaned_ids:
            for ext_id in orphaned_ids:
                ext_user = external_map[ext_id]

                # Dedup check: skip if user already exists locally
                existing = await self.user_repo.get_by_external_and_server(
                    ext_user.external_user_id, server.id
                )
                if existing is not None:
                    log.info(  # pyright: ignore[reportAny]
                        "Skipping already-imported user during sync",
                        external_user_id=ext_user.external_user_id,
                        username=ext_user.username,
                    )
                    orphaned_ids.discard(ext_id)
                    matched_count += 1
                    continue

                # Create an Identity for the orphaned user
                identity = Identity()
                identity.display_name = ext_user.username
                identity.email = ext_user.email
                identity.enabled = True
                identity = await self.identity_repo.create(identity)

                # Create a User linked to the identity and server
                user = User()
                user.identity_id = identity.id
                user.media_server_id = server.id
                user.external_user_id = ext_user.external_user_id
                user.username = ext_user.username
                user.external_user_type = ext_user.user_type
                user.enabled = True
                _ = await self.user_repo.create(user)

                imported_count += 1

        # Build result with usernames for human readability
        return SyncResult(
            server_id=server_id,
            server_name=server.name,
            synced_at=datetime.now(UTC),
            orphaned_users=[external_map[uid].username for uid in orphaned_ids],
            stale_users=[local_names[uid] for uid in stale_ids],
            matched_users=matched_count,
            imported_users=imported_count,
        )
