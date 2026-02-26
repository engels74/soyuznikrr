"""SyncExclusion model for preventing re-import of deleted users.

When a user is deleted from the local DB, a SyncExclusion record is created
to prevent the background sync from re-importing the user if the Plex API
still returns them (known Plex API caching bug).
"""

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SyncExclusion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Prevents re-import of a deleted external user during sync.

    Attributes:
        id: UUID primary key.
        external_user_id: The user's ID on the media server.
        media_server_id: The media server this exclusion applies to.
        created_at: When the exclusion was created.
        updated_at: Last modification timestamp.
    """

    __tablename__: str = "sync_exclusions"

    external_user_id: Mapped[str] = mapped_column(String(255), index=True)
    media_server_id: Mapped[UUID] = mapped_column(ForeignKey("media_servers.id"))
