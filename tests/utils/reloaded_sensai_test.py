"""
Tests for Reloaded's `sensai` command: how the controller reads it and reports the conversation, and how `ask` puts a question to the docs agent.

No real model is called. The controller's tests replace `ask`, and `ask`'s own tests give the docs agent a scripted `FunctionModel`.
"""

import re
import threading
import time
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.profiles import ModelProfile
from pydantic_ai.usage import RequestUsage
from reloaded_fakes import EventLog, FakeBackend, FakeSession, wait_idle

from mujoco_mojo.settings import SensAIFeatures, SensAIModelEntry, SensAISettings
from mujoco_mojo.typing import ModelProvider
from mujoco_mojo.utils.sensai.compaction import (
    ContextGauge,
    context_gauge,
    message_texts,
)
from mujoco_mojo.utils.layers.reloaded import sensai
from mujoco_mojo.utils.layers.reloaded.controller import (
    COMMAND_SUGGESTIONS,
    ControllerEvent,
    ReloadedController,
    RunState,
    SensAIClearedEvent,
    SensAIContextEvent,
    SensAIEvent,
    ShowPaneEvent,
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
    """Stands in for `sensai.ask`: records each question and the conversation it came with, and answers it once `release` is set, when one is given."""

    model_config = {"arbitrary_types_allowed": True}

    questions: list[str] = []
    histories: list[list[str]] = []
    """The text of the conversation each question came with."""
    release: threading.Event | None = None
    text: str = "Use `pause`."
    compacted_to: list[ModelMessage] | None = None
    """When set, what the conversation becomes with the next answer, as a summary would leave it."""

    def __call__(
        self, question: str, history: Sequence[ModelMessage] = ()
    ) -> sensai.Answer:
        self.questions.append(question)
        self.histories.append(message_texts(history))
        if self.release is not None:
            assert self.release.wait(5)
        before = list(history) if self.compacted_to is None else self.compacted_to
        return sensai.Answer(
            text=self.text,
            model="model-b",
            history=[*before, *exchange(question, self.text)],
            context=GAUGE,
            compacted=self.compacted_to is not None,
        )


GAUGE = ContextGauge(used_tokens=1_250, window_tokens=10_000, known_window=True)
"""How full every fake answer leaves the context: 12.5%."""


def exchange(question: str, answer: str) -> list[ModelMessage]:
    return [
        ModelRequest(parts=[UserPromptPart(question)]),
        ModelResponse(parts=[TextPart(answer)]),
    ]


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> Asked:
    fake = Asked()
    monkeypatch.setattr(sensai, "ask", fake)
    return fake


def said(events: list[ControllerEvent]) -> list[SensAIEvent]:
    """What went to SensAI's pane, in order."""
    return [event for event in events if isinstance(event, SensAIEvent)]


def wait_for_said(log: EventLog, text: str) -> None:
    assert log.wait_for(lambda events: any(text in e.message for e in said(events)))


def wait_until_answered(controller: ReloadedController) -> None:
    """Until SensAI takes a question again, which is once the last answer is in and its thread is done."""
    deadline = time.monotonic() + 5
    while controller.describe("sensai x") == "SensAI is still on the last question.":
        assert time.monotonic() < deadline, "SensAI did not finish"
        time.sleep(0.01)


def ask_and_wait(controller: ReloadedController, question: str) -> None:
    controller.submit(f"sensai {question}")
    wait_until_answered(controller)


class TestTheCommand:
    def test_a_question_ending_in_a_question_mark_is_asked_and_not_explained(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        controller.submit("sensai How do I PAUSE a run?")
        wait_for_said(log, "Use `pause`.")

        assert asked.questions == ["How do I PAUSE a run?"]
        assert any("model-b" in e.message for e in said(log.events))

    def test_the_conversation_goes_to_the_sensai_pane_and_not_the_log(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        controller.submit("sensai how do I pause?")
        wait_for_said(log, "Use `pause`.")

        assert ShowPaneEvent("sensai") in log.events
        question, *_rest, answer = said(log.events)
        assert question == SensAIEvent("how do I pause?", question=True)
        assert answer == SensAIEvent("Use `pause`.", markdown=True)
        assert not any("pause" in m for m in log.messages())

    def test_sensai_alone_shows_its_pane_and_asks_nothing(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        controller.submit("sensai")

        assert log.events[-1] == ShowPaneEvent("sensai")
        assert asked.questions == []

    def test_log_shows_the_log_again(
        self, controller: ReloadedController, log: EventLog
    ) -> None:
        controller.submit("log")

        assert log.events[-1] == ShowPaneEvent("log")

    def test_a_follow_up_question_carries_the_conversation(
        self, controller: ReloadedController, asked: Asked
    ) -> None:
        ask_and_wait(controller, "how do I pause?")
        ask_and_wait(controller, "and step?")
        ask_and_wait(controller, "and in the Dojo?")

        assert asked.histories == [
            [],
            ["how do I pause?", "Use `pause`."],
            ["how do I pause?", "Use `pause`.", "and step?", "Use `pause`."],
        ]

    def test_a_summary_the_answer_came_back_with_is_what_the_next_question_gets(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        ask_and_wait(controller, "how do I pause?")
        asked.compacted_to = [ModelRequest(parts=[UserPromptPart("summary")])]
        ask_and_wait(controller, "and step?")
        asked.compacted_to = None
        ask_and_wait(controller, "and in the Dojo?")

        assert asked.histories[-1] == ["summary", "and step?", "Use `pause`."]
        wait_for_said(log, "SensAI summarized its earlier part")

    def test_sensai_compact_summarizes_and_the_next_question_goes_on_from_it(
        self,
        controller: ReloadedController,
        log: EventLog,
        asked: Asked,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        compacted: list[list[str]] = []

        def compact(history: Sequence[ModelMessage]) -> sensai.Compacted:
            compacted.append(message_texts(history))
            return sensai.Compacted(
                history=[ModelRequest(parts=[UserPromptPart("summary")])],
                context=ContextGauge(
                    used_tokens=1, window_tokens=1_000, known_window=False
                ),
            )

        monkeypatch.setattr(sensai, "compact", compact)
        ask_and_wait(controller, "how do I pause?")
        ask_and_wait(controller, "and step?")
        controller.submit("sensai compact")
        wait_for_said(log, "Summarized the conversation so far.")
        wait_until_answered(controller)
        ask_and_wait(controller, "and in the Dojo?")

        assert SensAIContextEvent(0.001, estimated=True) in log.events
        assert compacted == [
            ["how do I pause?", "Use `pause`.", "and step?", "Use `pause`."]
        ]
        assert asked.histories[-1] == ["summary"]
        assert "compact" not in asked.questions

    def test_an_answer_reports_how_full_the_context_is(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        ask_and_wait(controller, "how do I pause?")

        assert SensAIContextEvent(0.125, estimated=False) in log.events

    def test_starting_over_empties_the_context(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        ask_and_wait(controller, "how do I pause?")
        controller.submit("sensai clear")

        # nothing is measured until SensAI answers again
        assert log.events[-1] == SensAIContextEvent(None)

    def test_sensai_compact_with_nothing_said_yet_says_so(
        self, controller: ReloadedController, log: EventLog
    ) -> None:
        controller.submit("sensai compact")

        wait_for_said(log, "Nothing to summarize yet.")

    def test_sensai_compact_that_shortens_nothing_leaves_the_conversation(
        self,
        controller: ReloadedController,
        log: EventLog,
        asked: Asked,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            sensai,
            "compact",
            lambda history: sensai.Compacted(history=list(history), context=GAUGE),
        )
        ask_and_wait(controller, "how do I pause?")
        controller.submit("sensai compact")
        wait_for_said(log, "only its first and latest questions")
        wait_until_answered(controller)
        ask_and_wait(controller, "and step?")

        assert asked.histories[-1] == ["how do I pause?", "Use `pause`."]

    def test_a_question_with_no_answer_is_not_remembered(
        self, controller: ReloadedController, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        histories: list[list[str]] = []

        def refuse(
            question: str, history: Sequence[ModelMessage] = ()
        ) -> sensai.Answer:
            histories.append(message_texts(history))
            raise sensai.NoAnswer("no model")

        monkeypatch.setattr(sensai, "ask", refuse)
        ask_and_wait(controller, "first")
        ask_and_wait(controller, "second")

        assert histories == [[], []]

    def test_sensai_clear_starts_a_new_conversation(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        ask_and_wait(controller, "how do I pause?")
        controller.submit("sensai clear")
        ask_and_wait(controller, "how do I step?")

        assert SensAIClearedEvent() in log.events
        assert asked.histories[-1] == []
        assert "clear" not in asked.questions

    def test_the_conversation_is_not_cleared_while_an_answer_is_coming(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        asked.release = threading.Event()
        controller.submit("sensai how do I pause?")
        controller.submit("sensai clear")

        wait_for_said(log, "Start over once the answer is in.")
        assert SensAIClearedEvent() not in log.events
        asked.release.set()
        wait_until_answered(controller)
        ask_and_wait(controller, "and step?")
        assert asked.histories[-1] == ["how do I pause?", "Use `pause`."]

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
        wait_for_said(log, "Use `pause`.")

        assert controller.status().state is RunState.RUNNING
        release.set()
        wait_idle(controller)

    def test_one_question_is_answered_at_a_time(
        self, controller: ReloadedController, log: EventLog, asked: Asked
    ) -> None:
        asked.release = threading.Event()
        controller.submit("sensai first")
        controller.submit("sensai second")

        wait_for_said(log, "still answering")
        assert (
            controller.describe("sensai third")
            == "SensAI is still on the last question."
        )
        asked.release.set()
        wait_for_said(log, "Use `pause`.")
        assert asked.questions == ["first"]

    def test_no_answer_is_said_with_its_reason(
        self,
        controller: ReloadedController,
        log: EventLog,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def refuse(
            question: str, history: Sequence[ModelMessage] = ()
        ) -> sensai.Answer:
            raise sensai.NoAnswer("SensAI is off [really].")

        monkeypatch.setattr(sensai, "ask", refuse)
        controller.submit("sensai hi")

        wait_for_said(log, "SensAI is off \\[really].")

    def test_an_unexpected_error_is_said_and_the_command_still_works(
        self,
        controller: ReloadedController,
        log: EventLog,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def broken(
            question: str, history: Sequence[ModelMessage] = ()
        ) -> sensai.Answer:
            raise RuntimeError("settings file is broken")

        monkeypatch.setattr(sensai, "ask", broken)
        controller.submit("sensai hi")
        wait_for_said(log, "SensAI failed:")
        wait_until_answered(controller)

        fake = Asked()
        monkeypatch.setattr(sensai, "ask", fake)
        controller.submit("sensai again")
        wait_for_said(log, "Use `pause`.")

    def test_explain_points_to_sensai_only_the_first_time(
        self, controller: ReloadedController, log: EventLog
    ) -> None:
        controller.submit("explain gen")
        controller.submit("explain seed 4")
        controller.submit("explain sensai")

        pointers = [m for m in log.messages() if "For an answer from AI" in m]
        assert len(pointers) == 1
        assert any("Sets the seed to 4." in m for m in log.messages())

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("sensai", "Shows SensAI's pane."),
            ("sensai how do I pause?", "Asks SensAI. It answers from the docs."),
            ("SensAI how?", "Asks SensAI. It answers from the docs."),
            ("sensai clear", "Starts a new conversation."),
            ("sensai compact", "Summarizes the conversation so far."),
            ("log", "Shows the log."),
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

    @pytest.mark.parametrize(
        "text",
        [
            "gen",
            "g",
            "run 0.5",
            "run until step 5",
            "seed abc",
            "explain gen",
            "sensai hi",
            "log",
            "?",
            "help",
            "step 5",
            "  quit  ",
        ],
    )
    def test_a_command_is_known_as_one(self, text: str) -> None:
        assert ReloadedController.is_command(text)

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "how do I pause?",
            "help me find the seed",
            "gen now",
            "what is a seed",
            "sens",
            "log the forces",
        ],
    )
    def test_a_question_is_not_a_command(self, text: str) -> None:
        """While SensAI's pane shows, a line that is not a command is a question for it."""
        assert not ReloadedController.is_command(text)

    def test_it_is_in_the_help_and_the_completions(
        self, controller: ReloadedController
    ) -> None:
        names = [name for name, _ in controller.help_entries()]
        for name in (
            "sensai <question>",
            "sensai",
            "sensai compact",
            "sensai clear",
            "log",
        ):
            assert name in names
        assert "sensai " in COMMAND_SUGGESTIONS
        assert "log" in COMMAND_SUGGESTIONS


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

        assert (answer.text, answer.model, answer.compacted) == (
            "Type pause.",
            "m1",
            False,
        )
        # the model knows no window, so the gauge is measured against Harness's default
        assert answer.context.used_tokens > 0
        assert not answer.context.known_window
        # the search the answer took is not carried on with the conversation
        assert message_texts(answer.history) == ["how do I pause?", "Type pause."]

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

    def test_the_conversation_so_far_is_sent_with_the_question(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The docs agent's instructions go with it too: pydantic-ai leaves a system prompt out of a run that has history."""
        sent: list[list[ModelMessage]] = []

        def reply(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            sent.append(messages)
            return ModelResponse(parts=[TextPart("Type step.")])

        use(monkeypatch, SensAISettings(enabled=True), FunctionModel(reply))

        sensai.ask("and step?", exchange("how do I pause?", "Type pause."))

        messages = sent[0]
        prompts = [
            part.content
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, UserPromptPart)
        ]
        replies = [
            part.content
            for message in messages
            if isinstance(message, ModelResponse)
            for part in message.parts
            if isinstance(part, TextPart)
        ]
        assert prompts == ["how do I pause?", "and step?"]
        assert replies == ["Type pause."]
        last = messages[-1]
        assert isinstance(last, ModelRequest)
        assert "docs agent of SensAI" in (last.instructions or "")

    @staticmethod
    def summarizing(sent: list[str], window: int = 400) -> FunctionModel:
        """A model with a context window of `window` tokens, which answers a summary request with "summary" (and records it) and anything else with "Type step."."""

        def reply(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            last = messages[-1]
            asked_for = last.instructions if isinstance(last, ModelRequest) else None
            if asked_for and "summarization" in asked_for:
                sent.append("summary")
                return ModelResponse(parts=[TextPart("summary")])
            sent.append("answer")
            return ModelResponse(parts=[TextPart("Type step.")])

        return FunctionModel(reply, profile=ModelProfile(context_window=window))

    def test_a_conversation_that_fills_the_context_window_is_summarized_first(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sent: list[str] = []
        use(
            monkeypatch,
            SensAISettings(enabled=True, compact_at=0.5),
            self.summarizing(sent),
        )
        history = [
            message
            for number in range(12)
            for message in exchange(
                f"question {number} " + "word " * 20, f"answer {number}"
            )
        ]

        answer = sensai.ask("and step?", history)

        assert sent == ["summary", "answer"]
        assert answer.compacted
        texts = message_texts(answer.history)
        assert "summary" in texts
        assert texts[-2:] == ["and step?", "Type step."]
        assert len(answer.history) < len(history)
        # measured against the model's own window, and smaller than before the summary
        assert (answer.context.window_tokens, answer.context.known_window) == (
            400,
            True,
        )
        assert answer.context.fraction < context_gauge(history, 400).fraction

    def test_a_context_window_set_on_the_model_entry_is_what_the_conversation_must_fit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The model knows no window of its own (as with most Ollama models), so without the entry's it would be measured against Harness's 200K default and never summarized."""
        sent: list[str] = []

        def reply(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            last = messages[-1]
            asked_for = last.instructions if isinstance(last, ModelRequest) else None
            sent.append(
                "summary" if asked_for and "summarization" in asked_for else "answer"
            )
            return ModelResponse(parts=[TextPart(sent[-1])])

        entry = SensAIModelEntry(
            provider=ModelProvider.OLLAMA,
            model_name="llama3.1",
            base_url="http://localhost:11434/v1",
            context_window=400,
        )
        use(
            monkeypatch,
            SensAISettings(enabled=True, compact_at=0.5, models=[entry]),
            FunctionModel(reply),
        )
        history = [
            message
            for number in range(12)
            for message in exchange(
                f"question {number} " + "word " * 20, f"answer {number}"
            )
        ]

        answer = sensai.ask("and step?", history)

        assert sent == ["summary", "answer"]
        assert answer.compacted

    def test_what_goes_with_every_request_counts_toward_the_summary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The conversation and the docs agent's instructions (about 1,100 tokens, which the estimate of a request's text does count) are under half of a 3,000-token window, but the provider counted 2,000 for the request the last answer came from, the tool definitions included, which no estimate of text sees."""

        def ask_after(usage: RequestUsage) -> list[str]:
            sent: list[str] = []
            use(
                monkeypatch,
                SensAISettings(enabled=True, compact_at=0.5),
                self.summarizing(sent, window=3_000),
            )
            # more than the latest ten messages a summary keeps, so there is something to summarize
            history = [
                *[
                    message
                    for number in range(6)
                    for message in exchange(f"question {number}", f"answer {number}")
                ],
                ModelRequest(parts=[UserPromptPart("how do I pause?")]),
                ModelResponse(parts=[TextPart("Type pause.")], usage=usage),
            ]
            sensai.ask("and step?", history)
            return sent

        assert ask_after(RequestUsage(input_tokens=2_000, output_tokens=5)) == [
            "summary",
            "answer",
        ]
        # the same conversation with no count of what goes with it is not summarized
        assert ask_after(RequestUsage()) == ["answer"]

    def test_the_last_answer_carries_the_providers_count_and_the_gauge_reads_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sent: list[str] = []
        use(monkeypatch, SensAISettings(enabled=True), self.summarizing(sent))

        answer = sensai.ask("how do I pause?")

        last = answer.history[-1]
        assert isinstance(last, ModelResponse)
        assert last.usage.input_tokens > 0
        assert answer.context.used_tokens >= last.usage.input_tokens

    def test_a_short_conversation_is_not_summarized(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sent: list[str] = []
        use(
            monkeypatch,
            SensAISettings(enabled=True, compact_at=0.9),
            self.summarizing(sent),
        )

        answer = sensai.ask("and step?", exchange("how do I pause?", "Type pause."))

        assert sent == ["answer"]
        assert not answer.compacted

    def test_compact_summarizes_all_but_the_first_and_latest_questions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sent: list[str] = []
        use(monkeypatch, SensAISettings(enabled=True), self.summarizing(sent))
        history = [
            message
            for number in range(4)
            for message in exchange(f"question {number}", f"answer {number}")
        ]

        compacted = sensai.compact(history)

        assert sent == ["summary"]
        assert compacted.context.window_tokens == 400
        texts = message_texts(compacted.history)
        assert texts[0] == "question 0"
        assert "summary" in texts
        assert texts[-2:] == ["question 3", "answer 3"]
        assert "question 1" not in texts

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
