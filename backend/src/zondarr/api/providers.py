"""Provider metadata API controller.

Provides endpoint for querying registered media server providers:
- GET /api/v1/providers — List all provider metadata
"""

from collections.abc import Sequence

from litestar import Controller, get
from litestar.status_codes import HTTP_200_OK

from zondarr.media.registry import registry

from .schemas import ProviderMetadataResponse


class ProviderController(Controller):
    """Controller for provider metadata endpoints.

    Serves provider metadata to the frontend so it can render
    provider-specific UI (colors, icons, labels) without hardcoding.
    """

    path: str = "/api/v1/providers"
    tags: Sequence[str] | None = ["Providers"]

    @get(
        "/",
        status_code=HTTP_200_OK,
        summary="List registered providers",
        description="Returns metadata for all registered media server providers.",
        exclude_from_auth=True,
    )
    async def list_providers(self) -> list[ProviderMetadataResponse]:
        """List all registered provider metadata.

        Returns metadata including server_type, display_name, color,
        icon_svg, capabilities, supported_permissions, and join flow type.
        """
        result: list[ProviderMetadataResponse] = []

        for desc in registry.get_all_descriptors():
            meta = desc.metadata
            caps = desc.client_class.capabilities()
            perms = desc.client_class.supported_permissions()

            result.append(
                ProviderMetadataResponse(
                    server_type=meta.server_type,
                    display_name=meta.display_name,
                    color=meta.color,
                    icon_svg=meta.icon_svg,
                    api_key_help_text=meta.api_key_help_text,
                    capabilities=sorted(str(c) for c in caps),
                    supported_permissions=sorted(perms),
                    join_flow_type=(
                        desc.join_flow.flow_type if desc.join_flow else None
                    ),
                )
            )

        return result
