"""Core module - database, exceptions, and shared types."""

from zondarr.core.database import (
    create_engine_from_url,
    create_session_factory,
    db_lifespan,
    provide_db_session,
)
from zondarr.core.exceptions import (
    ConfigurationError,
    NotFoundError,
    RepositoryError,
    ValidationError,
    ZondarrError,
)
from zondarr.core.types import (
    Email,
    EntityId,
    InvitationCode,
    NonEmptyStr,
    NonNegativeInt,
    PortNumber,
    PositiveInt,
    SecretKey,
    StringList,
    UrlStr,
    Username,
    UUIDList,
    UUIDStr,
)

__all__ = [
    "ConfigurationError",
    "Email",
    "EntityId",
    "InvitationCode",
    "NonEmptyStr",
    "NonNegativeInt",
    "NotFoundError",
    "PortNumber",
    "PositiveInt",
    "RepositoryError",
    "SecretKey",
    "StringList",
    "UUIDList",
    "UUIDStr",
    "UrlStr",
    "Username",
    "ValidationError",
    "ZondarrError",
    "create_engine_from_url",
    "create_session_factory",
    "db_lifespan",
    "provide_db_session",
]
