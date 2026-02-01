"""InvitationService for invitation business logic orchestration.

Provides methods to create, validate, and redeem invitations.
Implements Property 11: Invitation Validation Checks All Conditions -
for any invitation redemption attempt, the service SHALL check:
(1) enabled status, (2) expiration time, (3) use count vs max_uses.
If any check fails, it SHALL return a specific error indicating
which condition failed.

Implements Property 8: Generated Codes Are Valid -
for any generated invitation code, the code SHALL:
(1) be exactly 12 characters long,
(2) contain only uppercase letters and digits,
(3) exclude ambiguous characters (0, O, I, L).
"""

import secrets
import string
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from zondarr.core.exceptions import NotFoundError, ValidationError
from zondarr.models.invitation import Invitation
from zondarr.models.media_server import Library, MediaServer
from zondarr.repositories.invitation import InvitationRepository
from zondarr.repositories.media_server import MediaServerRepository


class InvitationValidationFailure(StrEnum):
    """Specific reasons why invitation validation can fail.

    Used to provide clear, actionable error messages to users
    attempting to redeem invitations.
    """

    DISABLED = "disabled"
    EXPIRED = "expired"
    MAX_USES_REACHED = "max_uses_reached"
    NOT_FOUND = "not_found"


# Valid alphabet for invitation codes: uppercase letters and digits excluding ambiguous characters
# Excludes: 0 (zero), O (letter O), I (letter I), L (letter L)
CODE_ALPHABET: str = "".join(
    c for c in string.ascii_uppercase + string.digits if c not in "0OIL"
)
CODE_LENGTH: int = 12
MAX_CODE_GENERATION_RETRIES: int = 3


class InvitationService:
    """Service for managing invitation operations.

    Orchestrates business logic for invitation management including:
    - Creating new invitations with configurable limits
    - Validating invitations before redemption
    - Redeeming invitations and tracking usage

    All redemption operations validate the invitation state before
    incrementing usage to ensure only valid invitations are redeemed.

    Attributes:
        repository: The InvitationRepository for data access.
        server_repository: Optional MediaServerRepository for server/library validation.
    """

    repository: InvitationRepository
    server_repository: MediaServerRepository | None

    def __init__(
        self,
        repository: InvitationRepository,
        /,
        *,
        server_repository: MediaServerRepository | None = None,
    ) -> None:
        """Initialize the InvitationService.

        Args:
            repository: The InvitationRepository for data access (positional-only).
            server_repository: Optional MediaServerRepository for server/library
                validation (keyword-only).
        """
        self.repository = repository
        self.server_repository = server_repository

    async def create(
        self,
        *,
        code: str | None = None,
        expires_at: datetime | None = None,
        max_uses: int | None = None,
        duration_days: int | None = None,
        server_ids: Sequence[UUID] | None = None,
        library_ids: Sequence[UUID] | None = None,
        target_servers: Sequence[MediaServer] | None = None,
        allowed_libraries: Sequence[Library] | None = None,
        created_by: str | None = None,
    ) -> Invitation:
        """Create a new invitation with the specified configuration.

        Generates a unique invitation code if not provided and creates an invitation
        entity with the provided settings. Implements collision handling with up to
        3 retries for code generation.

        Validates that all server_ids reference existing enabled MediaServer records
        and that all library_ids belong to the specified servers.

        Args:
            code: Optional custom invitation code (keyword-only). If not provided,
                a cryptographically secure 12-character code is generated.
            expires_at: Optional expiration timestamp (keyword-only).
            max_uses: Optional maximum number of redemptions (keyword-only).
            duration_days: Optional duration in days for user access (keyword-only).
            server_ids: Optional list of server UUIDs to grant access to (keyword-only).
                Requires server_repository to be set for validation.
            library_ids: Optional list of library UUIDs to grant access to (keyword-only).
                Requires server_repository to be set for validation.
            target_servers: Optional list of media servers to grant access to (keyword-only).
                Use this when you already have MediaServer objects.
            allowed_libraries: Optional list of specific libraries to grant access to (keyword-only).
                Use this when you already have Library objects.
            created_by: Optional identifier of who created the invitation (keyword-only).

        Returns:
            The created Invitation entity with generated code.

        Raises:
            ValidationError: If code generation fails after max retries due to collisions,
                or if server_ids/library_ids validation fails.
            RepositoryError: If the database operation fails.
        """
        # Use provided code or generate a unique one with collision handling
        if code is not None:
            invitation_code = code
        else:
            invitation_code = await self._generate_unique_code()

        # Validate and resolve server_ids if provided
        resolved_servers: list[MediaServer] = []
        if server_ids is not None:
            resolved_servers = await self._validate_server_ids(server_ids)
        elif target_servers is not None:
            resolved_servers = list(target_servers)

        # Validate and resolve library_ids if provided
        resolved_libraries: list[Library] = []
        if library_ids is not None:
            resolved_libraries = await self._validate_library_ids(
                library_ids, resolved_servers
            )
        elif allowed_libraries is not None:
            resolved_libraries = list(allowed_libraries)

        # Create the invitation entity
        invitation = Invitation(
            code=invitation_code,
            expires_at=expires_at,
            max_uses=max_uses,
            duration_days=duration_days,
            created_by=created_by,
        )

        # Add target servers if resolved
        if resolved_servers:
            invitation.target_servers = resolved_servers

        # Add allowed libraries if resolved
        if resolved_libraries:
            invitation.allowed_libraries = resolved_libraries

        return await self.repository.create(invitation)

    async def _validate_server_ids(
        self, server_ids: Sequence[UUID], /
    ) -> list[MediaServer]:
        """Validate that all server_ids reference existing enabled MediaServer records.

        Args:
            server_ids: Sequence of server UUIDs to validate (positional-only).

        Returns:
            List of validated MediaServer entities.

        Raises:
            ValidationError: If server_repository is not set, or if any server_id
                is invalid or references a disabled server.
        """
        if self.server_repository is None:
            raise ValidationError(
                "Cannot validate server_ids without server_repository",
                field_errors={"server_ids": ["Server validation not available"]},
            )

        if not server_ids:
            return []

        # Get enabled servers matching the provided IDs
        servers = await self.server_repository.get_enabled_by_ids(server_ids)
        found_ids = {server.id for server in servers}
        missing_ids = set(server_ids) - found_ids

        if missing_ids:
            raise ValidationError(
                f"Invalid or disabled server IDs: {missing_ids}",
                field_errors={
                    "server_ids": [
                        f"Server ID {sid} does not exist or is disabled"
                        for sid in missing_ids
                    ]
                },
            )

        return list(servers)

    async def _validate_library_ids(
        self,
        library_ids: Sequence[UUID],
        target_servers: Sequence[MediaServer],
        /,
    ) -> list[Library]:
        """Validate that all library_ids belong to the specified target servers.

        Args:
            library_ids: Sequence of library UUIDs to validate (positional-only).
            target_servers: Sequence of target MediaServer entities (positional-only).

        Returns:
            List of validated Library entities.

        Raises:
            ValidationError: If server_repository is not set, or if any library_id
                is invalid or doesn't belong to a target server.
        """
        if self.server_repository is None:
            raise ValidationError(
                "Cannot validate library_ids without server_repository",
                field_errors={"library_ids": ["Library validation not available"]},
            )

        if not library_ids:
            return []

        # Get libraries matching the provided IDs
        libraries = await self.server_repository.get_libraries_by_ids(library_ids)
        found_ids = {lib.id for lib in libraries}
        missing_ids = set(library_ids) - found_ids

        if missing_ids:
            raise ValidationError(
                f"Invalid library IDs: {missing_ids}",
                field_errors={
                    "library_ids": [
                        f"Library ID {lid} does not exist" for lid in missing_ids
                    ]
                },
            )

        # Validate that all libraries belong to target servers
        target_server_ids = {server.id for server in target_servers}
        invalid_libraries: list[UUID] = []

        for lib in libraries:
            if lib.media_server_id not in target_server_ids:
                invalid_libraries.append(lib.id)

        if invalid_libraries:
            raise ValidationError(
                f"Libraries do not belong to target servers: {invalid_libraries}",
                field_errors={
                    "library_ids": [
                        f"Library ID {lid} does not belong to any target server"
                        for lid in invalid_libraries
                    ]
                },
            )

        return list(libraries)

    async def validate(
        self, code: str, /
    ) -> tuple[bool, InvitationValidationFailure | None]:
        """Validate an invitation code without redeeming it.

        Checks all validation conditions:
        1. Invitation exists
        2. Invitation is enabled
        3. Invitation has not expired
        4. Invitation has not reached max uses

        Args:
            code: The invitation code to validate (positional-only).

        Returns:
            A tuple of (is_valid, failure_reason). If valid, failure_reason is None.
            If invalid, failure_reason indicates which condition failed.

        Raises:
            RepositoryError: If the database operation fails.
        """
        invitation = await self.repository.get_by_code(code)

        if invitation is None:
            return False, InvitationValidationFailure.NOT_FOUND

        return self._check_invitation_validity(invitation)

    async def redeem(self, code: str, /) -> Invitation:
        """Redeem an invitation, incrementing its use count.

        Validates the invitation and increments the use count if valid.
        This is the primary method for processing invitation redemptions.

        Implements Property 11: Invitation Validation Checks All Conditions.

        Args:
            code: The invitation code to redeem (positional-only).

        Returns:
            The redeemed Invitation with updated use_count.

        Raises:
            NotFoundError: If the invitation does not exist.
            ValidationError: If the invitation is invalid (disabled, expired, or exhausted).
            RepositoryError: If the database operation fails.
        """
        invitation = await self.repository.get_by_code(code)

        if invitation is None:
            raise NotFoundError("Invitation", code)

        # Check all validation conditions (Property 11)
        is_valid, failure_reason = self._check_invitation_validity(invitation)

        if not is_valid:
            error_messages = self._get_validation_error_messages(failure_reason)
            raise ValidationError(
                f"Invitation cannot be redeemed: {failure_reason}",
                field_errors=error_messages,
            )

        # Increment use count
        return await self.repository.increment_use_count(invitation)

    async def get_by_id(self, invitation_id: UUID, /) -> Invitation:
        """Retrieve an invitation by ID.

        Args:
            invitation_id: The UUID of the invitation to retrieve (positional-only).

        Returns:
            The Invitation entity.

        Raises:
            NotFoundError: If the invitation does not exist.
            RepositoryError: If the database operation fails.
        """
        invitation = await self.repository.get_by_id(invitation_id)
        if invitation is None:
            raise NotFoundError("Invitation", str(invitation_id))
        return invitation

    async def get_by_code(self, code: str, /) -> Invitation:
        """Retrieve an invitation by its code.

        Args:
            code: The invitation code to look up (positional-only).

        Returns:
            The Invitation entity.

        Raises:
            NotFoundError: If the invitation does not exist.
            RepositoryError: If the database operation fails.
        """
        invitation = await self.repository.get_by_code(code)
        if invitation is None:
            raise NotFoundError("Invitation", code)
        return invitation

    async def get_all(self) -> Sequence[Invitation]:
        """Retrieve all invitations.

        Returns:
            A sequence of all Invitation entities.

        Raises:
            RepositoryError: If the database operation fails.
        """
        return await self.repository.get_all()

    async def get_active(self) -> Sequence[Invitation]:
        """Retrieve all active invitations.

        Returns invitations that are enabled, not expired, and not exhausted.

        Returns:
            A sequence of active Invitation entities.

        Raises:
            RepositoryError: If the database operation fails.
        """
        return await self.repository.get_active()

    async def disable(self, invitation_id: UUID, /) -> Invitation:
        """Disable an invitation, preventing further redemptions.

        Args:
            invitation_id: The UUID of the invitation to disable (positional-only).

        Returns:
            The disabled Invitation entity.

        Raises:
            NotFoundError: If the invitation does not exist.
            RepositoryError: If the database operation fails.
        """
        invitation = await self.repository.get_by_id(invitation_id)
        if invitation is None:
            raise NotFoundError("Invitation", str(invitation_id))

        return await self.repository.disable(invitation)

    async def calculate_user_expiration(
        self, invitation: Invitation, /
    ) -> datetime | None:
        """Calculate the expiration date for a user created from this invitation.

        If the invitation has a duration_days value, calculates the expiration
        date from the current time. Otherwise returns None (no expiration).

        Args:
            invitation: The invitation being redeemed (positional-only).

        Returns:
            The calculated expiration datetime, or None if no duration is set.
        """
        if invitation.duration_days is None:
            return None

        return datetime.now(UTC) + timedelta(days=invitation.duration_days)

    def is_active(self, invitation: Invitation, /) -> bool:
        """Calculate whether an invitation is currently active.

        An invitation is active if:
        1. It is enabled
        2. It has not expired (expires_at is None or in the future)
        3. It has not reached max uses (max_uses is None or use_count < max_uses)

        Implements Property 10: Invitation Computed Fields.

        Args:
            invitation: The invitation to check (positional-only).

        Returns:
            True if the invitation is active, False otherwise.
        """
        # Check enabled status
        if not invitation.enabled:
            return False

        # Check expiration
        if invitation.expires_at is not None:
            now = datetime.now(UTC)
            if invitation.expires_at <= now:
                return False

        # Check max uses
        if invitation.max_uses is not None:
            if invitation.use_count >= invitation.max_uses:
                return False

        return True

    def remaining_uses(self, invitation: Invitation, /) -> int | None:
        """Calculate the remaining number of uses for an invitation.

        If max_uses is set, returns max_uses - use_count.
        If max_uses is not set (unlimited), returns None.

        Implements Property 10: Invitation Computed Fields.

        Args:
            invitation: The invitation to check (positional-only).

        Returns:
            The remaining number of uses, or None if unlimited.
        """
        if invitation.max_uses is None:
            return None

        return max(0, invitation.max_uses - invitation.use_count)

    def _generate_code(self, length: int = CODE_LENGTH) -> str:
        """Generate a random invitation code.

        Creates a cryptographically secure random code using uppercase
        letters and digits, excluding ambiguous characters (0, O, I, L).

        Implements Property 8: Generated Codes Are Valid.

        Args:
            length: The length of the code to generate. Defaults to 12.

        Returns:
            A random invitation code string.
        """
        return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))

    async def _generate_unique_code(self) -> str:
        """Generate a unique invitation code with collision handling.

        Attempts to generate a unique code up to MAX_CODE_GENERATION_RETRIES times.
        If a collision is detected (code already exists), a new code is generated.

        Returns:
            A unique invitation code string.

        Raises:
            ValidationError: If code generation fails after max retries due to collisions.
        """
        for _ in range(MAX_CODE_GENERATION_RETRIES):
            code = self._generate_code()

            # Check if code already exists
            existing = await self.repository.get_by_code(code)
            if existing is None:
                return code

        # All retries exhausted - this should be extremely rare with 12-char codes
        raise ValidationError(
            "Failed to generate unique invitation code after maximum retries",
            field_errors={"code": ["Code generation failed due to collisions"]},
        )

    def _check_invitation_validity(
        self, invitation: Invitation, /
    ) -> tuple[bool, InvitationValidationFailure | None]:
        """Check all validity conditions for an invitation.

        Implements Property 11: Invitation Validation Checks All Conditions.
        Checks in order:
        1. Enabled status
        2. Expiration time
        3. Use count vs max_uses

        Args:
            invitation: The invitation to validate (positional-only).

        Returns:
            A tuple of (is_valid, failure_reason). If valid, failure_reason is None.
        """
        # Check 1: Enabled status
        if not invitation.enabled:
            return False, InvitationValidationFailure.DISABLED

        # Check 2: Expiration time
        if invitation.expires_at is not None:
            now = datetime.now(UTC)
            if invitation.expires_at <= now:
                return False, InvitationValidationFailure.EXPIRED

        # Check 3: Use count vs max_uses
        if invitation.max_uses is not None:
            if invitation.use_count >= invitation.max_uses:
                return False, InvitationValidationFailure.MAX_USES_REACHED

        return True, None

    def _get_validation_error_messages(
        self, failure_reason: InvitationValidationFailure | None, /
    ) -> dict[str, list[str]]:
        """Get field-level error messages for a validation failure.

        Args:
            failure_reason: The reason validation failed (positional-only).

        Returns:
            A dictionary mapping field names to lists of error messages.
        """
        match failure_reason:
            case InvitationValidationFailure.DISABLED:
                return {"code": ["This invitation has been disabled"]}
            case InvitationValidationFailure.EXPIRED:
                return {"code": ["This invitation has expired"]}
            case InvitationValidationFailure.MAX_USES_REACHED:
                return {
                    "code": ["This invitation has reached its maximum number of uses"]
                }
            case InvitationValidationFailure.NOT_FOUND:
                return {"code": ["Invalid invitation code"]}
            case _:
                return {"code": ["Invitation validation failed"]}
