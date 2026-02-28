"""Repository layer - data access abstraction.

Provides generic repository base class and specialized repositories
for each entity type. All repositories wrap database operations in
RepositoryError for consistent error handling.
"""

from zondarr.repositories.base import Repository
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.invitation import InvitationRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.sync_run import SyncRunRepository
from zondarr.repositories.user import UserRepository
from zondarr.repositories.wizard import WizardRepository
from zondarr.repositories.wizard_step import WizardStepRepository

__all__ = [
    "IdentityRepository",
    "InvitationRepository",
    "MediaServerRepository",
    "Repository",
    "SyncRunRepository",
    "UserRepository",
    "WizardRepository",
    "WizardStepRepository",
]
