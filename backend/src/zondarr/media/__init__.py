"""Media module - client protocol, registry, and implementations.

Provides:
- MediaClient: Protocol defining the interface for media server clients
- MediaClientClass: Protocol for media client classes that can be instantiated
- ClientRegistry: Singleton registry for media client implementations
- registry: Global ClientRegistry instance
- Capability: StrEnum for features that media clients may support
- LibraryInfo: msgspec Struct for library information from media servers
- ExternalUser: msgspec Struct for user information from media servers
- MediaClientError: Exception for media client operation failures
- UnknownServerTypeError: Exception for unknown server types
"""

from .exceptions import MediaClientError, UnknownServerTypeError
from .protocol import MediaClient
from .provider import MediaClientClass
from .registry import ClientRegistry, registry
from .types import Capability, ExternalUser, LibraryInfo

__all__ = [
    "Capability",
    "ClientRegistry",
    "ExternalUser",
    "LibraryInfo",
    "MediaClient",
    "MediaClientClass",
    "MediaClientError",
    "UnknownServerTypeError",
    "registry",
]
