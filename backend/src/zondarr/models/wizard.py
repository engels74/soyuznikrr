"""Wizard and WizardStep models for configurable onboarding flows.

Provides:
- InteractionType: StrEnum for supported wizard step interaction types
- Wizard: Model representing a configurable wizard flow
- WizardStep: Model representing a single step within a wizard

Uses SQLAlchemy 2.0 patterns with mapped_column and Mapped types.
Relationships use cascade delete for steps when wizard is deleted.
"""

from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InteractionType(StrEnum):
    """Supported wizard step interaction types.

    Each type defines a different user interaction pattern:
    - CLICK: Simple button confirmation
    - TIMER: Timed delay before proceeding
    - TOS: Terms of service acceptance with checkbox
    - TEXT_INPUT: Free-form text input collection
    - QUIZ: Multiple choice question with correct answer
    """

    CLICK = "click"
    TIMER = "timer"
    TOS = "tos"
    TEXT_INPUT = "text_input"
    QUIZ = "quiz"


class Wizard(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A configurable wizard flow for invitation redemption.

    Represents a sequence of steps that users must complete during
    invitation redemption. Wizards can be associated with invitations
    to run before and/or after account creation.

    Attributes:
        id: UUID primary key
        name: Human-readable name for the wizard
        description: Optional detailed description
        enabled: Whether the wizard is currently active
        created_at: Timestamp when the wizard was created
        updated_at: Timestamp of last modification
        steps: List of wizard steps in order
    """

    __tablename__: str = "wizards"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships - cascade delete for steps when wizard is deleted
    steps: Mapped[list[WizardStep]] = relationship(
        back_populates="wizard",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WizardStep.step_order",
    )


class WizardStep(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single step within a wizard.

    Represents one step in a wizard flow with a specific interaction type.
    Steps are ordered within their parent wizard and must have unique
    step_order values per wizard.

    Attributes:
        id: UUID primary key
        wizard_id: Foreign key to the parent wizard
        step_order: Position in the wizard sequence (0-indexed)
        interaction_type: Type of user interaction required
        title: Display title for the step
        content_markdown: Markdown content to display
        config: JSON configuration specific to the interaction type
        created_at: Timestamp when the step was created
        updated_at: Timestamp of last modification
        wizard: Reference to the parent wizard
    """

    __tablename__: str = "wizard_steps"

    wizard_id: Mapped[UUID] = mapped_column(
        ForeignKey("wizards.id", ondelete="CASCADE"),
    )
    step_order: Mapped[int] = mapped_column(Integer)
    interaction_type: Mapped[InteractionType] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(255))
    content_markdown: Mapped[str] = mapped_column(Text)
    config: Mapped[dict[str, str | int | bool | list[str] | None]] = mapped_column(
        JSON, default=dict
    )

    # Relationships - use joined for single relations
    wizard: Mapped[Wizard] = relationship(
        back_populates="steps",
        lazy="joined",
    )

    # Table constraints - unique step_order per wizard
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("wizard_id", "step_order", name="uq_wizard_step_order"),
    )
