"""Media types for client protocol and registry.

Provides:
- Capability: StrEnum for features that media clients may support
- LibraryInfo: msgspec Struct for library information from media servers
- ExternalUser: msgspec Struct for user information from media servers

Uses msgspec.Struct for high-performance serialization with validation
constraints via Meta annotations. All structs use omit_defaults=True
for minimal JSON output.
"""

from enum import StrEnum

import msgspec


class Capability(StrEnum):
    """Features that a media client may support.

    Used by the ClientRegistry to query what operations are available
    for a given server type. Clients declare their capabilities via
    the capabilities() class method.

    Attributes:
        CREATE_USER: Can create new users on the media server
        DELETE_USER: Can delete users from the media server
        ENABLE_DISABLE_USER: Can enable/disable user accounts
        LIBRARY_ACCESS: Can configure per-library access permissions
        DOWNLOAD_PERMISSION: Can configure download permissions
    """

    CREATE_USER = "create_user"
    DELETE_USER = "delete_user"
    ENABLE_DISABLE_USER = "enable_disable_user"
    LIBRARY_ACCESS = "library_access"
    DOWNLOAD_PERMISSION = "download_permission"


class LibraryInfo(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Information about a library retrieved from a media server.

    Returned by MediaClient.get_libraries() to provide details about
    available content libraries that can be granted access to.

    Attributes:
        external_id: The library's unique identifier on the media server
        name: Human-readable name of the library
        library_type: Type of content (movies, tvshows, music, etc.)
    """

    external_id: str
    name: str
    library_type: str


class ExternalUser(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Information about a user created on a media server.

    Returned by MediaClient.create_user() to provide details about
    the newly created user account on the external media server.

    Attributes:
        external_user_id: The user's unique identifier on the media server
        username: The username assigned to the user
        email: The user's email address (if provided during creation)
    """

    external_user_id: str
    username: str
    email: str | None = None
