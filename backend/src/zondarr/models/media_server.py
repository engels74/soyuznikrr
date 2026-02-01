"""MediaServer and Library models for media server management.

Provides:
- ServerType: StrEnum for supported media server types (Jellyfin, Plex)
- MediaServer: Model representing a media server instance
- Library: Model representing a content library within a media server

Uses SQLAlchemy 2.0 patterns with mapped_column and Mapped types.
Relationships use selectinload for collections and joined for single relations
to avoid N+1 query issues in async contexts.
"""

from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ServerType(StrEnum):
    """Supported media server types.

    Uses StrEnum for type-safe server type values that serialize
    naturally to JSON strings.
    """

    JELLYFIN = "jellyfin"
    PLEX = "plex"


class MediaServer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A media server instance (Plex or Jellyfin).

    Represents a configured media server that Zondarr manages user access for.
    The api_key field stores the authentication token for the media server API.

    Attributes:
        id: UUID primary key
        name: Human-readable name for the server
        server_type: Type of media server (jellyfin or plex)
        url: Base URL for the media server API
        api_key: Authentication token (should be encrypted at rest)
        enabled: Whether the server is active for user management
        created_at: Timestamp when the server was added
        updated_at: Timestamp of last modification
        libraries: List of content libraries on this server
    """

    __tablename__: str = "media_servers"

    name: Mapped[str] = mapped_column(String(255))
    server_type: Mapped[ServerType] = mapped_column()
    url: Mapped[str] = mapped_column(String(2048))
    api_key: Mapped[str] = mapped_column(String(512))  # Encrypted at rest
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships - use selectinload for collections to avoid N+1
    libraries: Mapped[list[Library]] = relationship(
        back_populates="media_server",
        cascade="all, delete-orphan",
        lazy="selectin",  # Eager load by default
    )


class Library(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A content library within a media server.

    Represents a collection of media content (movies, TV shows, music, etc.)
    that can be granted access to via invitations.

    Attributes:
        id: UUID primary key
        media_server_id: Foreign key to the parent media server
        external_id: The library's ID on the media server
        name: Human-readable name of the library
        library_type: Type of content (movies, tvshows, music, etc.)
        created_at: Timestamp when the library was synced
        updated_at: Timestamp of last sync
        media_server: Reference to the parent media server
    """

    __tablename__: str = "libraries"

    media_server_id: Mapped[UUID] = mapped_column(ForeignKey("media_servers.id"))
    external_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    library_type: Mapped[str] = mapped_column(String(50))

    # Relationships - use joined for single relations
    media_server: Mapped[MediaServer] = relationship(
        back_populates="libraries",
        lazy="joined",
    )
