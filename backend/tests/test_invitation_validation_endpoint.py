"""Regression tests for public invitation validation endpoint.

Asserts that sensitive fields (server url/id, quiz correct_answer_index)
are NOT exposed in the GET /api/v1/invitations/validate/{code} response.
"""

from collections.abc import AsyncGenerator
from typing import cast

import msgspec
import pytest
from litestar import Litestar
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.errors import not_found_handler, validation_error_handler
from zondarr.api.invitations import InvitationController
from zondarr.core.exceptions import NotFoundError, ValidationError
from zondarr.media.providers import register_all_providers
from zondarr.models.invitation import Invitation, invitation_servers
from zondarr.models.media_server import MediaServer
from zondarr.models.wizard import InteractionType, StepInteraction, Wizard, WizardStep

# Type-safe JSON response types for pyright.
_Json = dict[str, object]
_JsonList = list[_Json]


def _decode(response: object) -> _Json:
    """Decode a TestClient response body into a typed dict."""
    body = cast(bytes, response.content)
    return msgspec.json.decode(body, type=_Json)


def _as_dict(obj: object) -> _Json:
    """Narrow an object from a JSON list element to a dict."""
    assert isinstance(obj, dict)
    return cast(_Json, obj)


def _as_list(obj: object) -> _JsonList:
    """Narrow an object from a JSON dict value to a list of dicts."""
    assert isinstance(obj, list)
    return cast(_JsonList, obj)


def _make_test_app(
    session_factory: async_sessionmaker[AsyncSession],
) -> Litestar:
    """Create a Litestar test app with the InvitationController."""

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return Litestar(
        route_handlers=[InvitationController],
        dependencies={
            "session": Provide(provide_session),
        },
        exception_handlers={
            ValidationError: validation_error_handler,
            NotFoundError: not_found_handler,
        },
    )


class TestPublicValidationEndpointDataLeakage:
    """Regression tests: sensitive fields must not appear in public responses."""

    @pytest.fixture(autouse=True)
    def _register_providers(self) -> None:
        register_all_providers()

    @pytest.mark.asyncio
    async def test_server_url_and_id_not_exposed(self) -> None:
        """Target server url, id, enabled, and timestamps must be absent."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                server = MediaServer()
                server.name = "Test Jellyfin"
                server.server_type = "jellyfin"
                server.url = "http://internal.local:8096"
                server.api_key = "secret-api-key-1234"
                server.enabled = True
                session.add(server)
                await session.flush()

                invitation = Invitation()
                invitation.code = "TESTCODE001"
                invitation.enabled = True
                session.add(invitation)
                await session.flush()

                _ = await session.execute(
                    invitation_servers.insert().values(
                        invitation_id=invitation.id,
                        media_server_id=server.id,
                    )
                )
                await session.commit()

            app = _make_test_app(session_factory)

            with TestClient(app) as client:
                data = _decode(client.get("/api/v1/invitations/validate/TESTCODE001"))
                assert data["valid"] is True

                servers = _as_list(data["target_servers"])
                assert len(servers) == 1

                server_data = _as_dict(servers[0])
                # Allowed fields
                assert server_data["name"] == "Test Jellyfin"
                assert server_data["server_type"] == "jellyfin"

                # Sensitive fields must be absent
                assert "id" not in server_data
                assert "url" not in server_data
                assert "api_key" not in server_data
                assert "enabled" not in server_data
                assert "created_at" not in server_data
                assert "updated_at" not in server_data
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_quiz_correct_answer_index_not_exposed(self) -> None:
        """Quiz correct_answer_index must be stripped from public wizard configs."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                server = MediaServer()
                server.name = "Test Plex"
                server.server_type = "plex"
                server.url = "http://plex.local:32400"
                server.api_key = "plex-token-xyz"
                server.enabled = True
                session.add(server)
                await session.flush()

                wizard = Wizard()
                wizard.name = "Quiz Wizard"
                wizard.enabled = True
                session.add(wizard)
                await session.flush()

                step = WizardStep()
                step.wizard_id = wizard.id
                step.step_order = 0
                step.title = "Quiz Step"
                step.content_markdown = "Answer this quiz"
                session.add(step)
                await session.flush()

                interaction = StepInteraction()
                interaction.step_id = step.id
                interaction.interaction_type = InteractionType.QUIZ
                interaction.config = {
                    "question": "What is 2+2?",
                    "options": ["3", "4", "5"],
                    "correct_answer_index": 1,
                }
                interaction.display_order = 0
                session.add(interaction)
                await session.flush()

                invitation = Invitation()
                invitation.code = "QUIZTEST001"
                invitation.enabled = True
                invitation.pre_wizard_id = wizard.id
                session.add(invitation)
                await session.flush()

                _ = await session.execute(
                    invitation_servers.insert().values(
                        invitation_id=invitation.id,
                        media_server_id=server.id,
                    )
                )
                await session.commit()

            app = _make_test_app(session_factory)

            with TestClient(app) as client:
                data = _decode(client.get("/api/v1/invitations/validate/QUIZTEST001"))
                assert data["valid"] is True

                # Navigate to quiz interaction config
                pre_wizard = _as_dict(data["pre_wizard"])
                steps = _as_list(pre_wizard["steps"])
                assert len(steps) == 1

                step_data = _as_dict(steps[0])
                interactions_list = _as_list(step_data["interactions"])
                assert len(interactions_list) == 1

                interaction_data = _as_dict(interactions_list[0])
                config = _as_dict(interaction_data["config"])

                # Question and options must be present
                assert config["question"] == "What is 2+2?"
                assert config["options"] == ["3", "4", "5"]

                # Correct answer must be stripped
                assert "correct_answer_index" not in config
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_non_quiz_interactions_unaffected(self) -> None:
        """Non-quiz interaction configs should pass through unchanged."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                server = MediaServer()
                server.name = "Test Server"
                server.server_type = "jellyfin"
                server.url = "http://jf.local:8096"
                server.api_key = "key-abc"
                server.enabled = True
                session.add(server)
                await session.flush()

                wizard = Wizard()
                wizard.name = "Timer Wizard"
                wizard.enabled = True
                session.add(wizard)
                await session.flush()

                step = WizardStep()
                step.wizard_id = wizard.id
                step.step_order = 0
                step.title = "Timer Step"
                step.content_markdown = "Please wait"
                session.add(step)
                await session.flush()

                interaction = StepInteraction()
                interaction.step_id = step.id
                interaction.interaction_type = InteractionType.TIMER
                interaction.config = {"duration_seconds": 10}
                interaction.display_order = 0
                session.add(interaction)
                await session.flush()

                invitation = Invitation()
                invitation.code = "TIMERTEST01"
                invitation.enabled = True
                invitation.post_wizard_id = wizard.id
                session.add(invitation)
                await session.flush()

                _ = await session.execute(
                    invitation_servers.insert().values(
                        invitation_id=invitation.id,
                        media_server_id=server.id,
                    )
                )
                await session.commit()

            app = _make_test_app(session_factory)

            with TestClient(app) as client:
                data = _decode(client.get("/api/v1/invitations/validate/TIMERTEST01"))
                assert data["valid"] is True

                post_wizard = _as_dict(data["post_wizard"])
                steps = _as_list(post_wizard["steps"])

                step_data = _as_dict(steps[0])
                interactions_list = _as_list(step_data["interactions"])

                interaction_data = _as_dict(interactions_list[0])
                config = _as_dict(interaction_data["config"])
                assert config["duration_seconds"] == 10
        finally:
            await engine.dispose()
