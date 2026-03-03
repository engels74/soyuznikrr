"""Shared entity-to-response converters for API controllers.

Provides reusable conversion functions for transforming ORM model
entities into msgspec response schemas. Used by both WizardController
and InvitationController to avoid duplicated conversion logic.
"""

from zondarr.models.wizard import StepInteraction, WizardStep

from .schemas import StepInteractionResponse, TranslationResponse, WizardStepResponse


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
        interaction_type=str(interaction.interaction_type),
        config=interaction.config,
        display_order=interaction.display_order,
        created_at=interaction.created_at,
        updated_at=interaction.updated_at,
    )


def public_step_interaction_to_response(
    interaction: StepInteraction, /
) -> StepInteractionResponse:
    """Convert a StepInteraction entity to a public-safe StepInteractionResponse.

    Strips ``correct_answer_index`` from quiz interaction configs so that
    correct answers are not leaked to unauthenticated users.

    Args:
        interaction: The StepInteraction entity (positional-only).

    Returns:
        StepInteractionResponse with sensitive config fields removed.
    """
    config = interaction.config
    if str(interaction.interaction_type) == "quiz":
        config = {k: v for k, v in config.items() if k != "correct_answer_index"}
    return StepInteractionResponse(
        id=interaction.id,
        step_id=interaction.step_id,
        interaction_type=str(interaction.interaction_type),
        config=config,
        display_order=interaction.display_order,
        created_at=interaction.created_at,
        updated_at=interaction.updated_at,
    )


def public_wizard_step_to_response(step: WizardStep, /) -> WizardStepResponse:
    """Convert a WizardStep entity to a public-safe WizardStepResponse.

    Uses :func:`public_step_interaction_to_response` so quiz answers are
    stripped from interaction configs.

    Args:
        step: The WizardStep entity (positional-only).

    Returns:
        WizardStepResponse with sanitised interactions.
    """
    interactions = [public_step_interaction_to_response(i) for i in step.interactions]
    translations = [
        TranslationResponse(
            language_code=t.language_code,
            title=t.title,
            content_markdown=t.content_markdown,
        )
        for t in step.translations
    ]
    return WizardStepResponse(
        id=step.id,
        wizard_id=step.wizard_id,
        step_order=step.step_order,
        title=step.title,
        content_markdown=step.content_markdown,
        primary_language=step.primary_language,
        interactions=interactions,
        translations=translations,
        created_at=step.created_at,
        updated_at=step.updated_at,
    )


def wizard_step_to_response(step: WizardStep, /) -> WizardStepResponse:
    """Convert a WizardStep entity to WizardStepResponse.

    Args:
        step: The WizardStep entity (positional-only).

    Returns:
        WizardStepResponse with interactions.
    """
    interactions = [step_interaction_to_response(i) for i in step.interactions]
    translations = [
        TranslationResponse(
            language_code=t.language_code,
            title=t.title,
            content_markdown=t.content_markdown,
        )
        for t in step.translations
    ]
    return WizardStepResponse(
        id=step.id,
        wizard_id=step.wizard_id,
        step_order=step.step_order,
        title=step.title,
        content_markdown=step.content_markdown,
        primary_language=step.primary_language,
        interactions=interactions,
        translations=translations,
        created_at=step.created_at,
        updated_at=step.updated_at,
    )
