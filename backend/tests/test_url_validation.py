"""Tests for SSRF URL validation (zondarr.core.url_validation)."""

from unittest.mock import AsyncMock, patch

import pytest

from zondarr.core.exceptions import ValidationError
from zondarr.core.url_validation import validate_url_host


class TestAllowPrivateBypass:
    """When allow_private=True, validation is skipped entirely."""

    @pytest.mark.asyncio
    async def test_allow_private_skips_all_checks(self) -> None:
        """Private IPs are allowed when allow_private=True."""
        await validate_url_host("http://192.168.1.1:8096", allow_private=True)
        await validate_url_host("http://127.0.0.1:32400", allow_private=True)
        await validate_url_host("http://10.0.0.5:8096", allow_private=True)


class TestSchemeEnforcement:
    """URL scheme is enforced at the msgspec level (UrlStr pattern).

    These tests verify the validation module handles edge cases.
    """

    @pytest.mark.asyncio
    async def test_missing_hostname_raises(self) -> None:
        """URLs without a hostname are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            await validate_url_host("http://", allow_private=False)
        assert "url" in exc_info.value.field_errors


class TestPrivateIPBlocking:
    """When allow_private=False, private/internal IPs are blocked."""

    @pytest.mark.asyncio
    async def test_loopback_ipv4_blocked(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await validate_url_host("http://127.0.0.1:32400", allow_private=False)
        assert "url" in exc_info.value.field_errors

    @pytest.mark.asyncio
    async def test_loopback_ipv6_blocked(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await validate_url_host("http://[::1]:32400", allow_private=False)
        assert "url" in exc_info.value.field_errors

    @pytest.mark.asyncio
    async def test_private_10_range_blocked(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await validate_url_host("http://10.0.0.1:8096", allow_private=False)
        assert "url" in exc_info.value.field_errors

    @pytest.mark.asyncio
    async def test_private_172_range_blocked(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await validate_url_host("http://172.16.0.1:8096", allow_private=False)
        assert "url" in exc_info.value.field_errors

    @pytest.mark.asyncio
    async def test_private_192_168_range_blocked(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await validate_url_host("http://192.168.1.100:8096", allow_private=False)
        assert "url" in exc_info.value.field_errors

    @pytest.mark.asyncio
    async def test_link_local_blocked(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await validate_url_host(
                "http://169.254.169.254/latest/meta-data/", allow_private=False
            )
        assert "url" in exc_info.value.field_errors

    @pytest.mark.asyncio
    async def test_ipv4_mapped_ipv6_blocked(self) -> None:
        """IPv4-mapped IPv6 addresses like ::ffff:127.0.0.1 are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            await validate_url_host(
                "http://[::ffff:127.0.0.1]:32400", allow_private=False
            )
        assert "url" in exc_info.value.field_errors

    @pytest.mark.asyncio
    async def test_unspecified_address_blocked(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await validate_url_host("http://0.0.0.0:8096", allow_private=False)
        assert "url" in exc_info.value.field_errors


class TestDNSResolution:
    """Hostnames are resolved via DNS and all resulting IPs are checked."""

    @pytest.mark.asyncio
    async def test_hostname_resolving_to_private_ip_blocked(self) -> None:
        """A hostname that resolves to a private IP is blocked."""
        mock_result = [(2, 1, 6, "", ("192.168.1.1", 0))]
        with patch("zondarr.core.url_validation.asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(return_value=mock_result)  # pyright: ignore[reportAny]
            with pytest.raises(ValidationError) as exc_info:
                await validate_url_host(
                    "http://evil.example.com:8096", allow_private=False
                )
            assert "url" in exc_info.value.field_errors

    @pytest.mark.asyncio
    async def test_hostname_resolving_to_public_ip_allowed(self) -> None:
        """A hostname that resolves to a public IP is allowed."""
        mock_result = [(2, 1, 6, "", ("93.184.216.34", 0))]
        with patch("zondarr.core.url_validation.asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(return_value=mock_result)  # pyright: ignore[reportAny]
            await validate_url_host("http://example.com:8096", allow_private=False)

    @pytest.mark.asyncio
    async def test_unresolvable_hostname_raises(self) -> None:
        """A hostname that cannot be resolved raises ValidationError."""
        import socket

        with patch("zondarr.core.url_validation.asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(  # pyright: ignore[reportAny]
                side_effect=socket.gaierror("Name resolution failed")
            )
            with pytest.raises(ValidationError) as exc_info:
                await validate_url_host(
                    "http://nonexistent.invalid:8096", allow_private=False
                )
            assert "url" in exc_info.value.field_errors

    @pytest.mark.asyncio
    async def test_mixed_resolution_blocks_if_any_private(self) -> None:
        """If any resolved IP is private, the URL is blocked."""
        mock_result = [
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("192.168.1.1", 0)),
        ]
        with patch("zondarr.core.url_validation.asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(return_value=mock_result)  # pyright: ignore[reportAny]
            with pytest.raises(ValidationError) as exc_info:
                await validate_url_host(
                    "http://dual.example.com:8096", allow_private=False
                )
            assert "url" in exc_info.value.field_errors


class TestPublicIPsAllowed:
    """Public IPs pass validation when allow_private=False."""

    @pytest.mark.asyncio
    async def test_public_ipv4_allowed(self) -> None:
        await validate_url_host("http://93.184.216.34:8096", allow_private=False)

    @pytest.mark.asyncio
    async def test_public_ipv6_allowed(self) -> None:
        await validate_url_host(
            "http://[2607:f8b0:4004:800::200e]:8096", allow_private=False
        )
