"""Repository layer - data access abstraction.

Provides generic repository base class and specialized repositories
for each entity type. All repositories wrap database operations in
RepositoryError for consistent error handling.
"""

from zondarr.repositories.base import Repository
from zondarr.repositories.media_server import MediaServerRepository

__all__ = ["MediaServerRepository", "Repository"]
