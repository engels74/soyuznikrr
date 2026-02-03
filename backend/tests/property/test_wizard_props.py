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
