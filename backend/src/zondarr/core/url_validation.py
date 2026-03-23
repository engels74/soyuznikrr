"""URL host validation to prevent SSRF attacks.

Validates that media server URLs do not target private, loopback,
link-local, or otherwise internal network addresses when
``allow_private_networks`` is disabled.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from zondarr.core.exceptions import ValidationError


def _is_internal_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if *addr* is a private/internal/special-use address."""
    # Handle IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped

    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


async def validate_url_host(url: str, *, allow_private: bool = False) -> None:
    """Validate that *url* does not target an internal network host.

    When *allow_private* is ``True`` the function returns immediately
    without performing any checks (the common case for self-hosted
    Zondarr instances where media servers live on the same LAN).

    Raises:
        ValidationError: If the URL targets a private/internal address.
    """
    if allow_private:
        return

    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise ValidationError(
            "Invalid URL: no hostname found",
            field_errors={"url": ["URL must contain a valid hostname"]},
        )

    # If the hostname is already an IP literal, validate directly
    try:
        addr = ipaddress.ip_address(hostname)
        if _is_internal_ip(addr):
            raise ValidationError(
                "URL targets a private or internal network address",
                field_errors={
                    "url": ["URLs targeting private/internal networks are not allowed"]
                },
            )
        return
    except ValueError:
        pass  # Not an IP literal — resolve via DNS below

    # Resolve the hostname and check ALL returned addresses
    loop = asyncio.get_event_loop()
    try:
        results = await loop.getaddrinfo(
            hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        raise ValidationError(
            f"Cannot resolve hostname: {hostname}",
            field_errors={"url": [f"Cannot resolve hostname: {hostname}"]},
        ) from None

    if not results:
        raise ValidationError(
            f"Cannot resolve hostname: {hostname}",
            field_errors={"url": [f"Cannot resolve hostname: {hostname}"]},
        )

    for _family, _type, _proto, _canonname, sockaddr in results:
        ip_str = sockaddr[0]
        addr = ipaddress.ip_address(ip_str)
        if _is_internal_ip(addr):
            raise ValidationError(
                "URL targets a private or internal network address",
                field_errors={
                    "url": ["URLs targeting private/internal networks are not allowed"]
                },
            )
