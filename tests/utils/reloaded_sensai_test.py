"""
Tests for Reloaded's `sensai` command: how the controller reads it and logs the answer, and how `ask` puts a question to the docs agent.

No real model is called. The controller's tests replace `ask`, and `ask`'s own tests give the docs agent a scripted `FunctionModel`.
"""

import re
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from reloaded_fakes import EventLog, FakeBackend, FakeSession, wait_idle

from mujoco_mojo.settings import SensAIFeatures, SensAISettings
from mujoco_mojo.utils.layers.reloaded import sensai
from mujoco_mojo.utils.layers.reloaded.controller import (
    COMMAND_SUGGESTIONS,
    LogEvent,
    ReloadedController,
    RunState,
)


@pytest.fixture
def session() -> FakeSession:
    return FakeSession(seed=1)


@pytest.fixture
def log() -> EventLog:
    return EventLog()


@pytest.fixture
def controller(
    session: FakeSession, log: EventLog, tmp_path: Path
) -> Iterator[ReloadedController]:
    controller = ReloadedController(
        session, FakeBackend(), watch_path=tmp_path, sink=log
    )
    controller.start()
    yield controller
    controller.shutdown()


class Asked(BaseModel):
    """Stands in for `sensai.ask`: records each question and answers it, after `release` is set when one is given."""

    model_config = {"arbitrary_types_allowed": True}

    questions: list[str] = []
    release: threading.Event | None = None
    answer: sensai.Answer = sensai.Answer(text="Use `pause`.", model="model-b")

    def __call__(self, question: str) -> sensai.Answer:
        self.questions.append(question)
        if self.release is not None:
            assert self.release.wait(5)
        return self.answer


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> Asked:
    fake = Asked()
    monkeypatch.setattr(sensai, "ask", fake)
    return fake


def wait_for_answer(log: EventLog, text: str) -> None:
    assert log.wait_for(lambda _events: any(text in m for m in log.messages()))


class TestTheCommand:
    def test_a_question_ending_in_a_question_mark_is_asked_and_not_explained(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        controller.submit("sensai How do I PAUSE a run?")
        wait_for_answer(log, "Use `pause`.")

        assert asked.questions == ["How do I PAUSE a run?"]
        assert any("SensAI" in m and "model-b" in m for m in log.messages())

    def test_the_answer_is_logged_as_markdown(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        """The log pane draws it as formatted text. Read as rich markup, its links' square brackets would be taken for tags."""
        asked.answer = sensai.Answer(
            text="See [Reloaded](https://x/reloaded/)", model=None
        )

        controller.submit("sensai where are the docs")
        wait_for_answer(log, "See [Reloaded]")

        event = next(
            e for e in log.events if getattr(e, "message", "").startswith("See")
        )
        assert isinstance(event, LogEvent)
        assert event.markdown

    def test_sensai_alone_says_how_to_ask(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        controller.submit("sensai")

        assert asked.questions == []
        assert "sensai how do I add a requirement?" in log.messages()[-1]

    def test_a_question_can_be_asked_during_a_run(
        self,
        controller: ReloadedController,
        session: FakeSession,
        log: EventLog,
        asked: Asked,
    ) -> None:
        release = threading.Event()
        session.generation_behavior = lambda s: release.wait(5)
        controller.submit("gen")
        assert session.started.wait(5)

        controller.submit("sensai what does gen do")
        wait_for_answer(log, "Use `pause`.")

        assert controller.status().state is RunState.RUNNING
        release.set()
        wait_idle(controller)

    def test_one_question_is_answered_at_a_time(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        asked.release = threading.Event()
        controller.submit("sensai first")
        controller.submit("sensai second")

        assert any("still answering" in m for m in log.messages())
        assert (
            controller.describe("sensai third")
            == "SensAI is still on the last question."
        )
        asked.release.set()
        wait_for_answer(log, "Use `pause`.")
        assert asked.questions == ["first"]

    def test_no_answer_is_logged_with_its_reason(
        self,
        controller: ReloadedController,
        log: EventLog,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def refuse(_question: str) -> sensai.Answer:
            raise sensai.NoAnswer("SensAI is off [really].")

        monkeypatch.setattr(sensai, "ask", refuse)
        controller.submit("sensai hi")

        wait_for_answer(log, "SensAI is off \\[really].")

    def test_an_unexpected_error_is_logged_and_the_command_still_works(
        self,
        controller: ReloadedController,
        log: EventLog,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def broken(_question: str) -> sensai.Answer:
            raise RuntimeError("settings file is broken")

        monkeypatch.setattr(sensai, "ask", broken)
        controller.submit("sensai hi")
        wait_for_answer(log, "SensAI failed:")

        fake = Asked()
        monkeypatch.setattr(sensai, "ask", fake)
        controller.submit("sensai again")
        wait_for_answer(log, "Use `pause`.")

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("sensai", "Asks SensAI, e.g. sensai how do I pause?"),
            ("sensai how do I pause?", "Asks SensAI. It answers from the docs."),
            ("SensAI how?", "Asks SensAI. It answers from the docs."),
            ("explain sensai how?", "Prints what that would do."),
            ("sensai?", "Not a command. Try help."),
            ("sens", "Press Tab to complete sensai."),
        ],
    )
    def test_describe(
        self, controller: ReloadedController, text: str, expected: str
    ) -> None:
        sentence = controller.describe(text)

        assert sentence == expected
        assert len(sentence) <= 45

    def test_explain_points_to_sensai_only_the_first_time(
        self, controller: ReloadedController, log: EventLog
    ) -> None:
        controller.submit("explain gen")
        controller.submit("explain seed 4")
        controller.submit("explain sensai")

        pointers = [m for m in log.messages() if "For an answer from AI" in m]
        assert len(pointers) == 1
        assert any("Sets the seed to 4." in m for m in log.messages())

    def test_it_is_in_the_help_and_the_completions(
        self, controller: ReloadedController
    ) -> None:
        assert "sensai " in COMMAND_SUGGESTIONS
        assert "sensai <question>" in [name for name, _ in controller.help_entries()]


class _Settings(BaseModel):
    sensai: SensAISettings


def use(
    monkeypatch: pytest.MonkeyPatch, settings: SensAISettings, model: FunctionModel
) -> None:
    monkeypatch.setattr(
        sensai, "MujocoMojoSettings", lambda: _Settings(sensai=settings)
    )
    monkeypatch.setattr(sensai, "build_fallback_model", lambda: model)


class TestAsk:
    def test_the_docs_agent_answers_and_the_model_is_named(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def reply(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            if len(messages) == 1:
                return ModelResponse(
                    parts=[ToolCallPart("search_docs", {"query": "pause a run"})]
                )
            return ModelResponse(parts=[TextPart("Type pause.")])

        use(
            monkeypatch,
            SensAISettings(enabled=True),
            FunctionModel(reply, model_name="m1"),
        )

        answer = sensai.ask("how do I pause?")

        assert answer == sensai.Answer(text="Type pause.", model="m1")

    def test_off_is_said_and_no_model_is_asked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        use(
            monkeypatch,
            SensAISettings(enabled=False),
            FunctionModel(lambda *_: pytest.fail("asked")),
        )

        with pytest.raises(sensai.NoAnswer, match=re.escape("sensai.enabled true")):
            sensai.ask("hi")

    def test_the_docs_feature_off_is_said(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = SensAISettings(enabled=True, features=SensAIFeatures(docs=False))
        use(monkeypatch, settings, FunctionModel(lambda *_: pytest.fail("asked")))

        with pytest.raises(
            sensai.NoAnswer, match=re.escape("sensai.features.docs true")
        ):
            sensai.ask("hi")

    def test_running_out_of_requests_names_the_setting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def loop(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            return ModelResponse(parts=[ToolCallPart("search_docs", {"query": "x"})])

        use(
            monkeypatch,
            SensAISettings(enabled=True, max_requests=2),
            FunctionModel(loop),
        )

        with pytest.raises(
            sensai.NoAnswer, match=r"after 2 model requests.*sensai\.max_requests"
        ):
            sensai.ask("hi")

    def test_a_model_that_fails_is_reported_in_one_line(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            raise RuntimeError("503 overloaded")

        use(monkeypatch, SensAISettings(enabled=True), FunctionModel(fail))

        with pytest.raises(
            sensai.NoAnswer, match="No answer from the model: 503 overloaded"
        ):
            sensai.ask("hi")
