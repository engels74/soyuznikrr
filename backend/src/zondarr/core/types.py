"""Shared type definitions for Zondarr.

This module provides common type aliases used throughout the application.
Uses msgspec.Meta for validation constraints on annotated types.

These types are used in:
- API request/response schemas (api/schemas.py)
- Service layer validation
- Repository layer type hints
"""

from typing import Annotated
from uuid import UUID

import msgspec

# =============================================================================
# String Constraints
# =============================================================================

NonEmptyStr = Annotated[str, msgspec.Meta(min_length=1, max_length=255)]
"""Non-empty string with reasonable max length for names and titles."""

UrlStr = Annotated[
    str, msgspec.Meta(min_length=1, max_length=2048, pattern=r"^https?://")
]
"""URL string with max length suitable for most URLs. Only HTTP(S) schemes allowed."""

Email = Annotated[str, msgspec.Meta(pattern=r"^[\w.-]+@[\w.-]+\.\w+$", max_length=255)]
"""Email address with basic pattern validation."""

Username = Annotated[
    str, msgspec.Meta(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")
]
"""Username: lowercase, starts with letter, allows numbers and underscores."""

SecretKey = Annotated[str, msgspec.Meta(min_length=32)]
"""Secret key with minimum length for security."""

InvitationCode = Annotated[str, msgspec.Meta(min_length=1, max_length=20)]
"""Invitation code with reasonable length constraints."""

# =============================================================================
# Numeric Constraints
# =============================================================================

PositiveInt = Annotated[int, msgspec.Meta(gt=0)]
"""Positive integer (greater than zero)."""

NonNegativeInt = Annotated[int, msgspec.Meta(ge=0)]
"""Non-negative integer (zero or greater)."""

PortNumber = Annotated[int, msgspec.Meta(ge=1, le=65535)]
"""Valid TCP/UDP port number."""

# =============================================================================
# ID Types
# =============================================================================

type UUIDStr = str
"""UUID serialized as string for JSON responses."""

type EntityId = UUID
"""Standard entity identifier type (UUID)."""

# =============================================================================
# Collection Types
# =============================================================================

type UUIDList = list[UUID]
"""List of UUIDs, commonly used for batch operations."""

type StringList = list[str]
"""List of strings, commonly used for tags or identifiers."""
