"""SyncRunRepository for sync execution history access operations."""

from typing import override
from uuid import UUID

from sqlalchemy import select

from zondarr.core.exceptions import RepositoryError
from zondarr.models.sync_run import SyncRun
from zondarr.repositories.base import Repository


class SyncRunRepository(Repository[SyncRun]):
    """Repository for SyncRun entity operations."""

    @property
    @override
    def _model_class(self) -> type[SyncRun]:
        return SyncRun

    async def get_latest_by_type(
        self, media_server_id: UUID, sync_type: str, /
    ) -> SyncRun | None:
        """Return the latest run for a server and sync type."""
        try:
            result = await self.session.scalars(
                select(SyncRun)
                .where(
                    SyncRun.media_server_id == media_server_id,
                    SyncRun.sync_type == sync_type,
                )
                .order_by(SyncRun.started_at.desc())
                .limit(1)
            )
            return result.first()
        except Exception as e:
            raise RepositoryError(
                "Failed to get latest sync run by type",
                operation="get_latest_by_type",
                original=e,
            ) from e

    async def get_latest_success_by_type(
        self, media_server_id: UUID, sync_type: str, /
    ) -> SyncRun | None:
        """Return the latest successful run for a server and sync type."""
        try:
            result = await self.session.scalars(
                select(SyncRun)
                .where(
                    SyncRun.media_server_id == media_server_id,
                    SyncRun.sync_type == sync_type,
                    SyncRun.status == "success",
                )
                .order_by(SyncRun.finished_at.desc())
                .limit(1)
            )
            return result.first()
        except Exception as e:
            raise RepositoryError(
                "Failed to get latest successful sync run by type",
                operation="get_latest_success_by_type",
                original=e,
            ) from e
