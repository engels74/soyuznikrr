"""Onboarding state management service.

Tracks setup/onboarding progress in app_settings and enforces a
step-by-step progression for the initial admin onboarding flow.
"""

from typing import Literal, cast

import structlog

from zondarr.core.exceptions import AuthenticationError
from zondarr.repositories.admin import AdminAccountRepository
from zondarr.repositories.app_setting import AppSettingRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]

# Persistent setting key for onboarding flow state
ONBOARDING_STEP_KEY = "onboarding_step"

# Public step values used by API responses and frontend guards
OnboardingStep = Literal["account", "security", "server", "complete"]

# Only these values are persisted in app_settings once an admin exists
PersistedOnboardingStep = Literal["security", "server", "complete"]

_PERSISTED_STEPS = frozenset({"security", "server", "complete"})


class OnboardingService:
    """Service for onboarding status and step transitions.

    Attributes:
        admin_repo: Repository used to determine whether admin setup is complete.
        app_setting_repo: Repository used to persist onboarding step state.
    """

    admin_repo: AdminAccountRepository
    app_setting_repo: AppSettingRepository

    def __init__(
        self,
        admin_repo: AdminAccountRepository,
        app_setting_repo: AppSettingRepository,
    ) -> None:
        self.admin_repo = admin_repo
        self.app_setting_repo = app_setting_repo

    async def get_status(self) -> tuple[bool, OnboardingStep]:
        """Get onboarding status for the current installation.

        Returns:
            A tuple of (onboarding_required, onboarding_step).
            If no admin exists, onboarding is required and step is ``account``.
        """
        admin_count = await self.admin_repo.count()
        if admin_count == 0:
            return True, "account"

        step = await self._get_existing_admin_step()
        return step != "complete", step

    async def initialize_after_admin_setup(self) -> None:
        """Initialize onboarding state after first admin creation."""
        await self._set_step("security", reason="admin_created")

    async def advance_skip_step(self) -> OnboardingStep:
        """Advance onboarding by one step via explicit skip action.

        Transitions:
        - security -> server
        - server -> complete
        - complete -> complete (idempotent)
        """
        _, step = await self.get_status()
        if step == "account":
            raise AuthenticationError(
                "Admin setup is required before onboarding can advance",
                "SETUP_REQUIRED",
            )

        if step == "security":
            await self._set_step("server", reason="step_skipped")
            return "server"
        if step == "server":
            await self._set_step("complete", reason="step_skipped")
            return "complete"
        return "complete"

    async def complete_security_step(self) -> OnboardingStep:
        """Mark the security step as completed when CSRF origin is saved."""
        _, step = await self.get_status()
        if step == "security":
            await self._set_step("server", reason="security_completed")
            return "server"
        return step

    async def complete_server_step(self) -> OnboardingStep:
        """Mark the server step as completed when first server setup finishes."""
        _, step = await self.get_status()
        if step == "server":
            await self._set_step("complete", reason="server_completed")
            return "complete"
        return step

    async def _get_existing_admin_step(self) -> PersistedOnboardingStep:
        """Return persisted onboarding step for existing-admin installations."""
        setting = await self.app_setting_repo.get_by_key(ONBOARDING_STEP_KEY)
        if setting is None or setting.value is None:
            # Unreleased app behavior: force onboarding for existing admins once.
            await self._set_step("security", reason="state_missing")
            return "security"

        value = setting.value
        if value in _PERSISTED_STEPS:
            return cast(PersistedOnboardingStep, value)

        logger.warning("invalid_onboarding_step_state", value=value)
        await self._set_step("security", reason="state_invalid")
        return "security"

    async def _set_step(self, step: PersistedOnboardingStep, *, reason: str) -> None:
        """Persist onboarding step and emit a structured transition log."""
        _ = await self.app_setting_repo.upsert(ONBOARDING_STEP_KEY, step)
        logger.info("onboarding_step_updated", onboarding_step=step, reason=reason)
