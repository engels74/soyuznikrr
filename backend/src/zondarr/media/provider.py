"""Provider descriptor protocol and metadata types.

Defines the ProviderDescriptor protocol that each media server provider
implements to declare its capabilities, authentication flows, and metadata.

The registry stores ProviderDescriptors, enabling zero-touch provider
addition: create a provider module, implement ProviderDescriptor, register it.
"""

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

import msgspec

if TYPE_CHECKING:
    from zondarr.config import Settings
    from zondarr.models.admin import AdminAccount
    from zondarr.repositories.admin import AdminAccountRepository

    from .protocol import MediaClient
    from .types import Capability


class AuthFlowType(StrEnum):
    """Admin authentication flow types."""

    OAUTH = "oauth"
    CREDENTIALS = "credentials"


class AuthFieldDescriptor(msgspec.Struct, kw_only=True):
    """Describes a field in a credential-based auth form.

    Attributes:
        name: Field key (e.g., "server_url").
        label: Display label (e.g., "Server URL").
        field_type: HTML input type ("text", "password", "url").
        placeholder: Placeholder text for the input.
        required: Whether the field is required.
    """

    name: str
    label: str
    field_type: str
    placeholder: str = ""
    required: bool = True


class AdminAuthDescriptor(msgspec.Struct, kw_only=True):
    """Describes how a provider handles admin authentication.

    Attributes:
        method_name: Auth method identifier (e.g., "plex").
        display_name: Human-readable name (e.g., "Plex").
        flow_type: Whether this uses OAuth or credential forms.
        fields: Field descriptors for CREDENTIALS flow.
    """

    method_name: str
    display_name: str
    flow_type: AuthFlowType
    fields: list[AuthFieldDescriptor] = []


class JoinFlowType(StrEnum):
    """User join/redemption flow types."""

    OAUTH_LINK = "oauth_link"
    CREDENTIAL_CREATE = "credential_create"


class JoinFlowDescriptor(msgspec.Struct, kw_only=True):
    """Describes how a provider handles user join/redemption.

    Attributes:
        flow_type: Whether users link via OAuth or create credentials.
        fields: Extra fields beyond username/password/email.
    """

    flow_type: JoinFlowType
    fields: list[AuthFieldDescriptor] = []


class ProviderMetadata(msgspec.Struct, kw_only=True):
    """Static metadata about a media server provider.

    Attributes:
        server_type: Provider identifier string.
        display_name: Human-readable name.
        color: Brand hex color.
        icon_svg: SVG path data for the provider icon.
        env_url_var: Environment variable name for the server URL.
        env_api_key_var: Environment variable name for the API key.
        api_key_help_text: Help text for the "add server" form.
    """

    server_type: str
    display_name: str
    color: str
    icon_svg: str
    env_url_var: str
    env_api_key_var: str
    api_key_help_text: str = ""


class AdminAuthProvider(Protocol):
    """Protocol for provider-specific admin authentication."""

    async def authenticate(
        self,
        credentials: Mapping[str, object],
        *,
        settings: Settings,
        admin_repo: AdminAccountRepository,
    ) -> AdminAccount:
        """Authenticate an admin user via this provider.

        Args:
            credentials: Provider-specific credential dict.
            settings: Application settings.
            admin_repo: Repository for admin account lookups/creation.

        Returns:
            The authenticated or newly created AdminAccount.

        Raises:
            AuthenticationError: If authentication fails.
        """
        ...

    def is_configured(self, settings: Settings) -> bool:
        """Check whether this auth provider is configured and available.

        Args:
            settings: Application settings.

        Returns:
            True if the provider has the required configuration.
        """
        ...


class MediaClientClass(Protocol):
    """Protocol for media client classes that can be instantiated.

    Defines the expected constructor signature for media client implementations.
    """

    def __call__(self, *, url: str, api_key: str) -> MediaClient:
        """Create a new client instance."""
        ...

    @classmethod
    def capabilities(cls) -> set[Capability]:
        """Return the set of capabilities this client supports."""
        ...

    @classmethod
    def supported_permissions(cls) -> frozenset[str]:
        """Return the set of universal permission keys this client supports."""
        ...


class OAuthPinResult(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Result from OAuth PIN creation.

    Attributes:
        pin_id: The PIN identifier for status checking.
        code: The PIN code to display to the user.
        auth_url: URL where user authenticates.
        expires_at: When the PIN expires.
    """

    pin_id: int
    code: str
    auth_url: str
    expires_at: datetime


class OAuthCheckResult(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Result from OAuth PIN status check.

    Attributes:
        authenticated: Whether the PIN has been authenticated.
        auth_token: Auth token (only if authenticated).
        email: User's email (only if authenticated).
        error: Error message (only if failed).
    """

    authenticated: bool
    auth_token: str | None = None
    email: str | None = None
    error: str | None = None


class OAuthFlowProvider(Protocol):
    """Protocol for provider-specific OAuth flow implementations."""

    async def create_pin(self) -> OAuthPinResult:
        """Generate an OAuth PIN and return auth URL."""
        ...

    async def check_pin(self, pin_id: int, /) -> OAuthCheckResult:
        """Check if a PIN has been authenticated."""
        ...

    async def close(self) -> None:
        """Close resources."""
        ...


class ProviderDescriptor(Protocol):
    """Protocol that each media server provider implements.

    Declares everything about a provider: metadata, client class,
    admin auth, join flow, route handlers, and OAuth support.
    """

    @property
    def metadata(self) -> ProviderMetadata:
        """Provider metadata (server_type, display_name, color, etc.)."""
        ...

    @property
    def client_class(self) -> MediaClientClass:
        """The MediaClient implementation class."""
        ...

    @property
    def admin_auth(self) -> AdminAuthDescriptor | None:
        """Admin authentication descriptor, or None if not supported."""
        ...

    @property
    def admin_auth_provider(self) -> AdminAuthProvider | None:
        """Admin authentication handler, or None if not supported."""
        ...

    @property
    def join_flow(self) -> JoinFlowDescriptor | None:
        """Join/redemption flow descriptor, or None if not supported."""
        ...

    @property
    def route_handlers(self) -> list[type] | None:
        """Litestar route handler classes to register, or None."""
        ...

    def create_oauth_flow_provider(
        self, settings: Settings
    ) -> OAuthFlowProvider | None:
        """Create an OAuth flow provider, or None if not supported."""
        ...
