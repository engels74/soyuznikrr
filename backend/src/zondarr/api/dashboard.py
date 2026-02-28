"""Dashboard controller for aggregated statistics.

Provides a single endpoint that returns counts and recent activity
across invitations, users, media servers, and sync runs.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from litestar import Controller, get
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.api.schemas import (
    DashboardStatsResponse,
    RecentActivityItem,
)
from zondarr.models.identity import User
from zondarr.models.invitation import Invitation
from zondarr.models.media_server import MediaServer
from zondarr.models.sync_run import SyncRun


class DashboardController(Controller):
    """Controller for dashboard statistics endpoint."""

    path: str = "/api/v1/dashboard"
    tags: Sequence[str] | None = ["Dashboard"]

    @get(
        "/stats",
        summary="Get dashboard statistics",
        description="Returns aggregated counts and recent activity for the admin dashboard.",
    )
    async def get_stats(
        self,
        session: AsyncSession,
    ) -> DashboardStatsResponse:
        """Return aggregated dashboard statistics."""
        now = datetime.now(UTC)

        # --- Invitation counts ---
        total_invitations = (
            await session.scalar(select(func.count(Invitation.id)))
        ) or 0

        active_filter = (
            (Invitation.enabled.is_(True))
            & (
                or_(
                    Invitation.expires_at.is_(None),
                    Invitation.expires_at > now,
                )
            )
            & (
                or_(
                    Invitation.max_uses.is_(None),
                    Invitation.use_count < Invitation.max_uses,
                )
            )
        )
        active_invitations = (
            await session.scalar(select(func.count(Invitation.id)).where(active_filter))
        ) or 0

        pending_invitations = (
            await session.scalar(
                select(func.count(Invitation.id)).where(
                    active_filter, Invitation.use_count == 0
                )
            )
        ) or 0

        # --- User counts ---
        total_users = (await session.scalar(select(func.count(User.id)))) or 0

        active_users = (
            await session.scalar(
                select(func.count(User.id)).where(
                    User.enabled.is_(True),
                    or_(
                        User.expires_at.is_(None),
                        User.expires_at > now,
                    ),
                )
            )
        ) or 0

        # --- Server counts ---
        total_servers = (await session.scalar(select(func.count(MediaServer.id)))) or 0

        enabled_servers = (
            await session.scalar(
                select(func.count(MediaServer.id)).where(MediaServer.enabled.is_(True))
            )
        ) or 0

        # --- Recent activity (last 10 events) ---
        recent_activity = await self._build_recent_activity(session)

        return DashboardStatsResponse(
            total_invitations=total_invitations,
            active_invitations=active_invitations,
            total_users=total_users,
            active_users=active_users,
            total_servers=total_servers,
            enabled_servers=enabled_servers,
            pending_invitations=pending_invitations,
            recent_activity=recent_activity,
        )

    @staticmethod
    async def _build_recent_activity(
        session: AsyncSession,
    ) -> list[RecentActivityItem]:
        """Query the 10 most recent events across entity types."""
        items: list[RecentActivityItem] = []

        # Recent users
        user_rows = (
            await session.scalars(
                select(User).order_by(User.created_at.desc()).limit(10)
            )
        ).all()
        for u in user_rows:
            items.append(
                RecentActivityItem(
                    type="user_created",
                    description=f"User '{u.username}' was created",
                    timestamp=u.created_at,
                )
            )

        # Recent invitations
        inv_rows = (
            await session.scalars(
                select(Invitation).order_by(Invitation.created_at.desc()).limit(10)
            )
        ).all()
        for inv in inv_rows:
            items.append(
                RecentActivityItem(
                    type="invitation_created",
                    description=f"Invitation '{inv.code}' was created",
                    timestamp=inv.created_at,
                )
            )

        # Recent successful sync runs
        sync_rows = (
            await session.scalars(
                select(SyncRun)
                .where(SyncRun.status == "success")
                .order_by(SyncRun.created_at.desc())
                .limit(10)
            )
        ).all()
        for sr in sync_rows:
            items.append(
                RecentActivityItem(
                    type="sync_completed",
                    description=f"Sync ({sr.sync_type}) completed",
                    timestamp=sr.created_at,
                )
            )

        # Recent media servers
        server_rows = (
            await session.scalars(
                select(MediaServer).order_by(MediaServer.created_at.desc()).limit(10)
            )
        ).all()
        for ms in server_rows:
            items.append(
                RecentActivityItem(
                    type="server_added",
                    description=f"Server '{ms.name}' was added",
                    timestamp=ms.created_at,
                )
            )

        # Sort all items by timestamp descending and take top 10
        items.sort(key=lambda item: item.timestamp, reverse=True)
        return items[:10]
