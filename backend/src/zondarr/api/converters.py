"""Shared entity-to-response converters for API controllers.

Provides reusable conversion functions for transforming ORM model
entities into msgspec response schemas. Used by both WizardController
and InvitationController to avoid duplicated conversion logic.
"""

from zondarr.models.wizard import StepInteraction, WizardStep

from .schemas import StepInteractionResponse, WizardStepResponse


def step_interaction_to_response(
    interaction: StepInteraction, /
) -> StepInteractionResponse:
    """Convert a StepInteraction entity to StepInteractionResponse.

    Args:
        interaction: The StepInteraction entity (positional-only).

    Returns:
        StepInteractionResponse.
    """
    return StepInteractionResponse(
        id=interaction.id,
        step_id=interaction.step_id,
        interaction_type=interaction.interaction_type.value,
        config=interaction.config,
        display_order=interaction.display_order,
        created_at=interaction.created_at,
        updated_at=interaction.updated_at,
    )


def wizard_step_to_response(step: WizardStep, /) -> WizardStepResponse:
    """Convert a WizardStep entity to WizardStepResponse.

    Args:
        step: The WizardStep entity (positional-only).

    Returns:
        WizardStepResponse with interactions.
    """
    interactions = [
        step_interaction_to_response(i)
        for i in (step.interactions if step.interactions else [])
    ]
    return WizardStepResponse(
        id=step.id,
        wizard_id=step.wizard_id,
        step_order=step.step_order,
        title=step.title,
        content_markdown=step.content_markdown,
        interactions=interactions,
        created_at=step.created_at,
        updated_at=step.updated_at,
    )
