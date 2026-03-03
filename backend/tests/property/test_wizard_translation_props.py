"""Property-based tests for wizard step multilingual translations.

Feature: wizard-multilingual
Properties: translation CRUD, backward compatibility, response schemas
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TestDB
from zondarr.core.languages import LANGUAGES
from zondarr.models import WizardStepTranslation

# Custom strategies
name_strategy = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=100,
).filter(lambda x: x.strip())

markdown_strategy = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=500,
)

language_code_strategy = st.sampled_from(list(LANGUAGES.keys()))


def _make_service(session: AsyncSession):
    """Create a WizardService with the given session."""
    from zondarr.repositories.step_interaction import StepInteractionRepository
    from zondarr.repositories.wizard import WizardRepository
    from zondarr.repositories.wizard_step import WizardStepRepository
    from zondarr.services.wizard import WizardService

    wizard_repo = WizardRepository(session)
    step_repo = WizardStepRepository(session)
    interaction_repo = StepInteractionRepository(session)
    return WizardService(wizard_repo, step_repo, interaction_repo)


class TestCreateStepWithTranslations:
    """
    Feature: wizard-multilingual
    Scenario 1: Create step with translations → translations stored correctly
    """

    @settings(max_examples=10)
    @given(
        title=name_strategy,
        content=markdown_strategy,
        trans_title=name_strategy,
        trans_content=markdown_strategy,
        lang=language_code_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_step_with_translations_stores_correctly(
        self,
        db: TestDB,
        title: str,
        content: str,
        trans_title: str,
        trans_content: str,
        lang: str,
    ) -> None:
        """Creating a step with translations stores them in the DB."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title=title,
                content_markdown=content,
                primary_language="en",
                translations=[
                    {
                        "language_code": lang,
                        "title": trans_title,
                        "content_markdown": trans_content,
                    }
                ],
            )
            await session.commit()

            assert step.primary_language == "en"
            assert len(step.translations) == 1
            assert step.translations[0].language_code == lang
            assert step.translations[0].title == trans_title
            assert step.translations[0].content_markdown == trans_content


class TestCreateStepWithoutTranslations:
    """
    Feature: wizard-multilingual
    Scenario 2: Create step without translations → backward compatible
    """

    @pytest.mark.asyncio
    async def test_create_step_without_translations_backward_compatible(
        self,
        db: TestDB,
    ) -> None:
        """Creating a step without translations still works (backward compatible)."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content",
            )
            await session.commit()

            assert step.primary_language == "en"
            assert step.translations == []

    @pytest.mark.asyncio
    async def test_create_step_with_empty_translations_list(
        self,
        db: TestDB,
    ) -> None:
        """Creating a step with empty translations list works."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content",
                translations=[],
            )
            await session.commit()

            assert step.translations == []


class TestUpdateStepAddTranslations:
    """
    Feature: wizard-multilingual
    Scenario 3: Update step to add translations → new translations created
    """

    @pytest.mark.asyncio
    async def test_update_step_adds_translations(
        self,
        db: TestDB,
    ) -> None:
        """Updating a step to add translations creates new translation records."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content",
            )
            await session.commit()
            assert step.translations == []

            updated = await service.update_step(
                wizard.id,
                step.id,
                translations=[
                    {
                        "language_code": "da",
                        "title": "Trin 1",
                        "content_markdown": "Indhold",
                    },
                    {
                        "language_code": "de",
                        "title": "Schritt 1",
                        "content_markdown": "Inhalt",
                    },
                ],
            )
            await session.commit()

            assert len(updated.translations) == 2
            langs = {t.language_code for t in updated.translations}
            assert langs == {"da", "de"}


class TestUpdateStepModifyTranslations:
    """
    Feature: wizard-multilingual
    Scenario 4: Update step to modify translations → existing translations updated
    """

    @pytest.mark.asyncio
    async def test_update_step_modifies_existing_translations(
        self,
        db: TestDB,
    ) -> None:
        """Updating a step with existing translations updates the content."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content",
                translations=[
                    {
                        "language_code": "da",
                        "title": "Trin 1",
                        "content_markdown": "Indhold",
                    }
                ],
            )
            await session.commit()

            # Update the existing Danish translation
            updated = await service.update_step(
                wizard.id,
                step.id,
                translations=[
                    {
                        "language_code": "da",
                        "title": "Trin 1 (opdateret)",
                        "content_markdown": "Nyt indhold",
                    }
                ],
            )
            await session.commit()

            assert len(updated.translations) == 1
            assert updated.translations[0].language_code == "da"
            assert updated.translations[0].title == "Trin 1 (opdateret)"
            assert updated.translations[0].content_markdown == "Nyt indhold"


class TestUpdateStepRemoveTranslation:
    """
    Feature: wizard-multilingual
    Scenario 5: Update step to remove a translation → translation deleted
    """

    @pytest.mark.asyncio
    async def test_update_step_removes_translation_not_in_set(
        self,
        db: TestDB,
    ) -> None:
        """Updating translations removes languages not in the incoming set."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content",
                translations=[
                    {
                        "language_code": "da",
                        "title": "Trin 1",
                        "content_markdown": "Indhold",
                    },
                    {
                        "language_code": "de",
                        "title": "Schritt 1",
                        "content_markdown": "Inhalt",
                    },
                ],
            )
            await session.commit()
            assert len(step.translations) == 2

            # Update with only Danish → German should be removed
            updated = await service.update_step(
                wizard.id,
                step.id,
                translations=[
                    {
                        "language_code": "da",
                        "title": "Trin 1",
                        "content_markdown": "Indhold",
                    }
                ],
            )
            await session.commit()

            assert len(updated.translations) == 1
            assert updated.translations[0].language_code == "da"

            # Verify the German translation is actually deleted from DB
            remaining = (
                await session.scalars(
                    select(WizardStepTranslation).where(
                        WizardStepTranslation.step_id == step.id,
                        WizardStepTranslation.language_code == "de",
                    )
                )
            ).all()
            assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_update_step_with_empty_translations_removes_all(
        self,
        db: TestDB,
    ) -> None:
        """Updating with empty translations list removes all translations."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content",
                translations=[
                    {
                        "language_code": "da",
                        "title": "Trin 1",
                        "content_markdown": "Indhold",
                    }
                ],
            )
            await session.commit()
            assert len(step.translations) == 1

            updated = await service.update_step(
                wizard.id,
                step.id,
                translations=[],
            )
            await session.commit()

            assert updated.translations == []


class TestStepResponseIncludesTranslations:
    """
    Feature: wizard-multilingual
    Scenario 6: Step response includes primary_language and translations
    """

    @pytest.mark.asyncio
    async def test_step_response_includes_primary_language_and_translations(
        self,
        db: TestDB,
    ) -> None:
        """wizard_step_to_response includes primary_language and translations."""
        await db.clean()

        from zondarr.api.converters import wizard_step_to_response

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Welcome",
                content_markdown="Hello!",
                primary_language="en",
                translations=[
                    {
                        "language_code": "da",
                        "title": "Velkommen",
                        "content_markdown": "Hej!",
                    }
                ],
            )
            await session.commit()

            response = wizard_step_to_response(step)

            assert response.primary_language == "en"
            assert len(response.translations) == 1
            assert response.translations[0].language_code == "da"
            assert response.translations[0].title == "Velkommen"
            assert response.translations[0].content_markdown == "Hej!"


class TestPublicStepResponseIncludesTranslations:
    """
    Feature: wizard-multilingual
    Scenario 7: Public step response includes translations (no sensitive data)
    """

    @pytest.mark.asyncio
    async def test_public_step_response_includes_translations(
        self,
        db: TestDB,
    ) -> None:
        """public_wizard_step_to_response includes translations safely."""
        await db.clean()

        from zondarr.api.converters import public_wizard_step_to_response

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Welcome",
                content_markdown="Hello!",
                primary_language="en",
                translations=[
                    {
                        "language_code": "fr",
                        "title": "Bienvenue",
                        "content_markdown": "Bonjour!",
                    }
                ],
            )

            # Add a quiz interaction to verify sensitive data is stripped
            step = await service.add_interaction(
                wizard.id,
                step.id,
                interaction_type="quiz",
                config={
                    "question": "What is 2+2?",
                    "options": ["3", "4", "5"],
                    "correct_answer_index": 1,
                },
            )
            await session.commit()

            # Refresh the step with interactions loaded
            refreshed_step = await service.step_repo.get_by_id(step.step_id)
            assert refreshed_step is not None
            await session.refresh(refreshed_step, ["interactions", "translations"])

            response = public_wizard_step_to_response(refreshed_step)

            # Translations should be present
            assert response.primary_language == "en"
            assert len(response.translations) == 1
            assert response.translations[0].language_code == "fr"
            assert response.translations[0].title == "Bienvenue"

            # Quiz correct_answer_index should be stripped
            assert len(response.interactions) == 1
            assert "correct_answer_index" not in response.interactions[0].config


class TestDuplicateLanguageCodeConstraint:
    """
    Feature: wizard-multilingual
    Scenario 8: Creating step with duplicate language codes → constraint violation
    """

    @pytest.mark.asyncio
    async def test_duplicate_language_code_raises_integrity_error(
        self,
        db: TestDB,
    ) -> None:
        """Duplicate language codes on the same step violate the unique constraint."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content",
            )
            await session.flush()

            # Manually insert two translations with the same language
            t1 = WizardStepTranslation(
                step_id=step.id,
                language_code="da",
                title="Trin 1",
                content_markdown="Indhold",
            )
            session.add(t1)
            await session.flush()

            t2 = WizardStepTranslation(
                step_id=step.id,
                language_code="da",
                title="Trin 1 duplikat",
                content_markdown="Duplikat indhold",
            )
            session.add(t2)

            with pytest.raises(IntegrityError):
                await session.flush()

    @pytest.mark.asyncio
    async def test_same_language_on_different_steps_allowed(
        self,
        db: TestDB,
    ) -> None:
        """Same language code on different steps is allowed."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step1 = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content 1",
                translations=[
                    {
                        "language_code": "da",
                        "title": "Trin 1",
                        "content_markdown": "Indhold 1",
                    }
                ],
            )

            step2 = await service.create_step(
                wizard.id,
                title="Step 2",
                content_markdown="Content 2",
                translations=[
                    {
                        "language_code": "da",
                        "title": "Trin 2",
                        "content_markdown": "Indhold 2",
                    }
                ],
            )
            await session.commit()

            assert len(step1.translations) == 1
            assert len(step2.translations) == 1


class TestCascadeDeleteTranslations:
    """
    Feature: wizard-multilingual
    Scenario 9: Cascade delete — translations are removed when step is deleted
    """

    @pytest.mark.asyncio
    async def test_deleting_step_cascades_to_translations(
        self,
        db: TestDB,
    ) -> None:
        """Deleting a step cascade-deletes its translations."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content",
                translations=[
                    {
                        "language_code": "da",
                        "title": "Trin 1",
                        "content_markdown": "Indhold",
                    },
                    {
                        "language_code": "de",
                        "title": "Schritt 1",
                        "content_markdown": "Inhalt",
                    },
                ],
            )
            await session.commit()
            step_id = step.id

            # Verify translations exist
            translations_before = (
                await session.scalars(
                    select(WizardStepTranslation).where(
                        WizardStepTranslation.step_id == step_id
                    )
                )
            ).all()
            assert len(translations_before) == 2

            # Delete the step
            await service.delete_step(wizard.id, step_id)
            await session.commit()

            # Verify translations are gone
            translations_after = (
                await session.scalars(
                    select(WizardStepTranslation).where(
                        WizardStepTranslation.step_id == step_id
                    )
                )
            ).all()
            assert len(translations_after) == 0


class TestPrimaryLanguageDefault:
    """
    Feature: wizard-multilingual
    Scenario 10: Default primary_language is "en"
    """

    @pytest.mark.asyncio
    async def test_default_primary_language_is_en(
        self,
        db: TestDB,
    ) -> None:
        """Steps created without primary_language default to 'en'."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content",
            )
            await session.commit()

            assert step.primary_language == "en"

    @pytest.mark.asyncio
    async def test_custom_primary_language_stored(
        self,
        db: TestDB,
    ) -> None:
        """Steps created with explicit primary_language store the value."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Trin 1",
                content_markdown="Indhold",
                primary_language="da",
            )
            await session.commit()

            assert step.primary_language == "da"

    @pytest.mark.asyncio
    async def test_update_primary_language(
        self,
        db: TestDB,
    ) -> None:
        """Primary language can be updated."""
        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content",
            )
            await session.commit()
            assert step.primary_language == "en"

            updated = await service.update_step(
                wizard.id,
                step.id,
                primary_language="da",
            )
            await session.commit()

            assert updated.primary_language == "da"


class TestTranslationModelConstraints:
    """
    Feature: wizard-multilingual
    Additional: Translation model unique constraint and field validations
    """

    @settings(max_examples=10)
    @given(
        lang1=language_code_strategy,
        lang2=language_code_strategy,
    )
    @pytest.mark.asyncio
    async def test_different_languages_on_same_step_succeeds(
        self,
        db: TestDB,
        lang1: str,
        lang2: str,
    ) -> None:
        """Different languages on the same step can coexist."""
        if lang1 == lang2:
            return

        await db.clean()

        async with db.session_factory() as session:
            service = _make_service(session)
            wizard = await service.create_wizard(name="Test Wizard")

            step = await service.create_step(
                wizard.id,
                title="Step 1",
                content_markdown="Content",
                translations=[
                    {
                        "language_code": lang1,
                        "title": f"Title {lang1}",
                        "content_markdown": f"Content {lang1}",
                    },
                    {
                        "language_code": lang2,
                        "title": f"Title {lang2}",
                        "content_markdown": f"Content {lang2}",
                    },
                ],
            )
            await session.commit()

            assert len(step.translations) == 2
            stored_langs = {t.language_code for t in step.translations}
            assert stored_langs == {lang1, lang2}
