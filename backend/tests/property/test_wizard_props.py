"""Property-based tests for wizard model constraints.

Feature: wizard-system
Properties: 3, 4
Validates: Requirements 1.3, 1.4
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from tests.conftest import create_test_engine
from zondarr.models import InteractionType, Wizard, WizardStep

# Custom strategies for wizard fields
name_strategy = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=100,
).filter(lambda x: x.strip())

description_strategy = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(categories=("L", "N", "P", "S", "Z")),
        min_size=0,
        max_size=500,
    ),
)

interaction_type_strategy = st.sampled_from(list(InteractionType))

markdown_strategy = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=1000,
)

step_order_strategy = st.integers(min_value=0, max_value=100)


class TestCascadeDeleteIntegrity:
    """
    Feature: wizard-system
    Property 3: Cascade Delete Integrity

    *For any* wizard with N steps (where N >= 0), deleting the wizard
    SHALL result in all N associated steps being deleted from the database.

    **Validates: Requirements 1.3**
    """

    @settings(max_examples=10)
    @given(
        wizard_name=name_strategy,
        wizard_enabled=st.booleans(),
        num_steps=st.integers(min_value=0, max_value=5),
    )
    @pytest.mark.asyncio
    async def test_cascade_delete_removes_all_steps(
        self,
        wizard_name: str,
        wizard_enabled: bool,
        num_steps: int,
    ) -> None:
        """Deleting a wizard cascades to delete all associated steps."""
        # Create fresh engine for isolation
        engine = await create_test_engine()

        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker

            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                # Create wizard
                wizard = Wizard()
                wizard.name = wizard_name
                wizard.enabled = wizard_enabled
                wizard.created_at = datetime.now(UTC)
                session.add(wizard)
                await session.flush()

                wizard_id = wizard.id

                # Create N steps
                for i in range(num_steps):
                    step = WizardStep()
                    step.wizard_id = wizard_id
                    step.step_order = i
                    step.interaction_type = InteractionType.CLICK
                    step.title = f"Step {i}"
                    step.content_markdown = f"Content for step {i}"
                    step.config = {}
                    step.created_at = datetime.now(UTC)
                    session.add(step)

                await session.commit()

                # Verify steps were created
                steps_before = (
                    await session.scalars(
                        select(WizardStep).where(WizardStep.wizard_id == wizard_id)
                    )
                ).all()
                assert len(steps_before) == num_steps

                # Delete wizard
                await session.delete(wizard)
                await session.commit()

                # Verify all steps were cascade deleted
                steps_after = (
                    await session.scalars(
                        select(WizardStep).where(WizardStep.wizard_id == wizard_id)
                    )
                ).all()
                assert len(steps_after) == 0

                # Verify wizard is gone
                wizard_after = await session.get(Wizard, wizard_id)
                assert wizard_after is None
        finally:
            await engine.dispose()


class TestStepOrderUniqueness:
    """
    Feature: wizard-system
    Property 4: Step Order Uniqueness

    *For any* wizard, attempting to create two steps with the same step_order
    SHALL fail with a constraint violation error.

    **Validates: Requirements 1.4**
    """

    @settings(max_examples=10)
    @given(
        wizard_name=name_strategy,
        step_order=step_order_strategy,
        title1=name_strategy,
        title2=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_duplicate_step_order_raises_integrity_error(
        self,
        wizard_name: str,
        step_order: int,
        title1: str,
        title2: str,
    ) -> None:
        """Creating two steps with same step_order raises IntegrityError."""
        # Create fresh engine for isolation
        engine = await create_test_engine()

        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker

            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                # Create wizard
                wizard = Wizard()
                wizard.name = wizard_name
                wizard.enabled = True
                wizard.created_at = datetime.now(UTC)
                session.add(wizard)
                await session.flush()

                wizard_id = wizard.id

                # Create first step
                step1 = WizardStep()
                step1.wizard_id = wizard_id
                step1.step_order = step_order
                step1.interaction_type = InteractionType.CLICK
                step1.title = title1
                step1.content_markdown = "Content 1"
                step1.config = {}
                step1.created_at = datetime.now(UTC)
                session.add(step1)
                await session.flush()

                # Create second step with same step_order - should fail
                step2 = WizardStep()
                step2.wizard_id = wizard_id
                step2.step_order = step_order  # Same order!
                step2.interaction_type = InteractionType.TIMER
                step2.title = title2
                step2.content_markdown = "Content 2"
                step2.config = {}
                step2.created_at = datetime.now(UTC)
                session.add(step2)

                with pytest.raises(IntegrityError):
                    await session.flush()
        finally:
            await engine.dispose()

    @settings(max_examples=10)
    @given(
        wizard_name=name_strategy,
        step_order1=step_order_strategy,
        step_order2=step_order_strategy,
    )
    @pytest.mark.asyncio
    async def test_different_step_orders_succeed(
        self,
        wizard_name: str,
        step_order1: int,
        step_order2: int,
    ) -> None:
        """Creating steps with different step_orders succeeds."""
        # Skip if orders are the same
        if step_order1 == step_order2:
            return

        # Create fresh engine for isolation
        engine = await create_test_engine()

        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker

            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                # Create wizard
                wizard = Wizard()
                wizard.name = wizard_name
                wizard.enabled = True
                wizard.created_at = datetime.now(UTC)
                session.add(wizard)
                await session.flush()

                wizard_id = wizard.id

                # Create first step
                step1 = WizardStep()
                step1.wizard_id = wizard_id
                step1.step_order = step_order1
                step1.interaction_type = InteractionType.CLICK
                step1.title = "Step 1"
                step1.content_markdown = "Content 1"
                step1.config = {}
                step1.created_at = datetime.now(UTC)
                session.add(step1)

                # Create second step with different step_order
                step2 = WizardStep()
                step2.wizard_id = wizard_id
                step2.step_order = step_order2
                step2.interaction_type = InteractionType.TIMER
                step2.title = "Step 2"
                step2.content_markdown = "Content 2"
                step2.config = {}
                step2.created_at = datetime.now(UTC)
                session.add(step2)

                # Should succeed
                await session.commit()

                # Verify both steps exist
                steps = (
                    await session.scalars(
                        select(WizardStep).where(WizardStep.wizard_id == wizard_id)
                    )
                ).all()
                assert len(steps) == 2
        finally:
            await engine.dispose()


class TestInteractionTypeValidation:
    """
    Feature: wizard-system
    Property 5: Interaction Type Validation

    *For any* step creation request, the interaction_type field SHALL only accept
    values from the set {click, timer, tos, text_input, quiz}. Any other value
    SHALL be rejected with a validation error.

    **Validates: Requirements 1.5**
    """

    @settings(max_examples=10)
    @given(
        interaction_type=st.sampled_from(
            ["click", "timer", "tos", "text_input", "quiz"]
        ),
    )
    def test_valid_interaction_types_accepted(
        self,
        interaction_type: str,
    ) -> None:
        """Valid interaction types are accepted by the service."""
        from zondarr.services.wizard import WizardService

        # Create a mock service (we only need the validation method)
        service = WizardService.__new__(WizardService)

        # Should not raise
        result = service._validate_interaction_type(interaction_type)  # pyright: ignore[reportPrivateUsage]
        assert result.value == interaction_type

    @settings(max_examples=10)
    @given(
        invalid_type=st.text(min_size=1, max_size=50).filter(
            lambda x: x not in ["click", "timer", "tos", "text_input", "quiz"]
        ),
    )
    def test_invalid_interaction_types_rejected(
        self,
        invalid_type: str,
    ) -> None:
        """Invalid interaction types are rejected with ValidationError."""
        from zondarr.core.exceptions import ValidationError
        from zondarr.services.wizard import WizardService

        # Create a mock service (we only need the validation method)
        service = WizardService.__new__(WizardService)

        # Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            _ = service._validate_interaction_type(invalid_type)  # pyright: ignore[reportPrivateUsage]

        assert "interaction_type" in exc_info.value.field_errors


class TestStepOrderContiguity:
    """
    Feature: wizard-system
    Property 6: Step Order Contiguity

    *For any* wizard with steps, after any step deletion or reorder operation,
    the step_order values SHALL form a contiguous sequence starting from 0
    (i.e., 0, 1, 2, ..., N-1 for N steps).

    **Validates: Requirements 3.4, 3.5**
    """

    @settings(max_examples=10)
    @given(
        wizard_name=name_strategy,
        num_steps=st.integers(min_value=2, max_value=5),
        delete_index=st.integers(min_value=0, max_value=4),
    )
    @pytest.mark.asyncio
    async def test_step_deletion_maintains_contiguity(
        self,
        wizard_name: str,
        num_steps: int,
        delete_index: int,
    ) -> None:
        """After deleting a step, remaining steps have contiguous order."""
        # Skip if delete_index is out of range
        if delete_index >= num_steps:
            return

        # Create fresh engine for isolation
        engine = await create_test_engine()

        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker

            from zondarr.repositories.wizard import WizardRepository
            from zondarr.repositories.wizard_step import WizardStepRepository
            from zondarr.services.wizard import WizardService

            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                wizard_repo = WizardRepository(session)
                step_repo = WizardStepRepository(session)
                service = WizardService(wizard_repo, step_repo)

                # Create wizard
                wizard = await service.create_wizard(name=wizard_name)

                # Create N steps
                step_ids: list[str] = []
                for i in range(num_steps):
                    step = await service.create_step(
                        wizard.id,
                        interaction_type="click",
                        title=f"Step {i}",
                        content_markdown=f"Content {i}",
                    )
                    step_ids.append(str(step.id))

                await session.commit()

                # Delete a step
                from uuid import UUID

                await service.delete_step(wizard.id, UUID(step_ids[delete_index]))
                await session.commit()

                # Verify contiguity
                steps = await step_repo.get_by_wizard_id(wizard.id)
                orders = [s.step_order for s in steps]

                # Should be contiguous starting from 0
                expected = list(range(len(steps)))
                assert orders == expected
        finally:
            await engine.dispose()


class TestTimerDurationBounds:
    """
    Feature: wizard-system
    Property 7: Timer Duration Bounds

    *For any* timer step configuration, the duration_seconds field SHALL be
    validated to be within the range [1, 300]. Values outside this range
    SHALL be rejected.

    **Validates: Requirements 5.4**
    """

    @settings(max_examples=10)
    @given(
        duration=st.integers(min_value=1, max_value=300),
    )
    def test_valid_timer_durations_accepted(
        self,
        duration: int,
    ) -> None:
        """Timer durations within [1, 300] are accepted."""
        from zondarr.services.wizard import WizardService

        service = WizardService.__new__(WizardService)

        config = {"duration_seconds": duration}
        result = service._validate_timer_config(config)  # pyright: ignore[reportPrivateUsage]

        assert result["duration_seconds"] == duration

    @settings(max_examples=10)
    @given(
        duration=st.one_of(
            st.integers(max_value=0),  # Too low
            st.integers(min_value=301),  # Too high
        ),
    )
    def test_invalid_timer_durations_rejected(
        self,
        duration: int,
    ) -> None:
        """Timer durations outside [1, 300] are rejected."""
        from zondarr.core.exceptions import ValidationError
        from zondarr.services.wizard import WizardService

        service = WizardService.__new__(WizardService)

        config = {"duration_seconds": duration}

        with pytest.raises(ValidationError) as exc_info:
            _ = service._validate_timer_config(config)  # pyright: ignore[reportPrivateUsage]

        assert "duration_seconds" in str(exc_info.value.field_errors)

    def test_missing_timer_duration_rejected(self) -> None:
        """Missing duration_seconds is rejected."""
        from zondarr.core.exceptions import ValidationError
        from zondarr.services.wizard import WizardService

        service = WizardService.__new__(WizardService)

        config: dict[str, object] = {}

        with pytest.raises(ValidationError) as exc_info:
            _ = service._validate_timer_config(config)  # pyright: ignore[reportPrivateUsage]

        assert "duration_seconds" in str(exc_info.value.field_errors)


class TestQuizConfigurationCompleteness:
    """
    Feature: wizard-system
    Property 8: Quiz Configuration Completeness

    *For any* quiz step configuration, the config SHALL require: a non-empty
    question string, an options array with at least 2 elements, and a
    correct_answer_index that is a valid index into the options array.

    **Validates: Requirements 8.2, 8.3**
    """

    @settings(max_examples=10)
    @given(
        question=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        num_options=st.integers(min_value=2, max_value=10),
        correct_index=st.integers(min_value=0, max_value=9),
    )
    def test_valid_quiz_config_accepted(
        self,
        question: str,
        num_options: int,
        correct_index: int,
    ) -> None:
        """Valid quiz configurations are accepted."""
        # Ensure correct_index is valid for the number of options
        if correct_index >= num_options:
            correct_index = num_options - 1

        from zondarr.services.wizard import WizardService

        service = WizardService.__new__(WizardService)

        options = [f"Option {i}" for i in range(num_options)]
        config = {
            "question": question,
            "options": options,
            "correct_answer_index": correct_index,
        }

        result = service._validate_quiz_config(config)  # pyright: ignore[reportPrivateUsage]

        assert result["question"] == question
        assert result["correct_answer_index"] == correct_index
        assert len(result["options"]) == num_options  # pyright: ignore[reportArgumentType]

    def test_missing_question_rejected(self) -> None:
        """Missing question is rejected."""
        from zondarr.core.exceptions import ValidationError
        from zondarr.services.wizard import WizardService

        service = WizardService.__new__(WizardService)

        config = {
            "options": ["A", "B"],
            "correct_answer_index": 0,
        }

        with pytest.raises(ValidationError) as exc_info:
            _ = service._validate_quiz_config(config)  # pyright: ignore[reportPrivateUsage]

        assert "question" in str(exc_info.value.field_errors)

    def test_too_few_options_rejected(self) -> None:
        """Quiz with fewer than 2 options is rejected."""
        from zondarr.core.exceptions import ValidationError
        from zondarr.services.wizard import WizardService

        service = WizardService.__new__(WizardService)

        config = {
            "question": "What is 2+2?",
            "options": ["4"],  # Only 1 option
            "correct_answer_index": 0,
        }

        with pytest.raises(ValidationError) as exc_info:
            _ = service._validate_quiz_config(config)  # pyright: ignore[reportPrivateUsage]

        assert "options" in str(exc_info.value.field_errors)

    @settings(max_examples=10)
    @given(
        correct_index=st.integers(min_value=2, max_value=100),
    )
    def test_invalid_correct_answer_index_rejected(
        self,
        correct_index: int,
    ) -> None:
        """correct_answer_index outside options range is rejected."""
        from zondarr.core.exceptions import ValidationError
        from zondarr.services.wizard import WizardService

        service = WizardService.__new__(WizardService)

        config = {
            "question": "What is 2+2?",
            "options": ["3", "4"],  # 2 options, indices 0-1
            "correct_answer_index": correct_index,  # Out of range
        }

        with pytest.raises(ValidationError) as exc_info:
            _ = service._validate_quiz_config(config)  # pyright: ignore[reportPrivateUsage]

        assert "correct_answer_index" in str(exc_info.value.field_errors)

    def test_missing_correct_answer_index_rejected(self) -> None:
        """Missing correct_answer_index is rejected."""
        from zondarr.core.exceptions import ValidationError
        from zondarr.services.wizard import WizardService

        service = WizardService.__new__(WizardService)

        config = {
            "question": "What is 2+2?",
            "options": ["3", "4"],
        }

        with pytest.raises(ValidationError) as exc_info:
            _ = service._validate_quiz_config(config)  # pyright: ignore[reportPrivateUsage]

        assert "correct_answer_index" in str(exc_info.value.field_errors)
