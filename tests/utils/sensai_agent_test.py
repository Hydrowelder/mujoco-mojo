"""
Tests for how the SensAI agents change the plot: the plot-config agent's tools, and the chat route that sends the browser an updated config only when the plot really changed.

No real model is called. A scripted `FunctionModel` plays the part of the model, calling the tools a model would, so these check what the server does with each call.
"""

import asyncio
import importlib
import itertools
import json
import logging
from collections.abc import AsyncIterator, Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai import ModelAPIError
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import (
    AgentInfo,
    DeltaToolCall,
    DeltaToolCalls,
    FunctionModel,
)

from mujoco_mojo.utils.dataframe import ColumnManifest
from mujoco_mojo.utils.layers.dojo.plot_config import PLOT_COLORS, PlotConfig
from mujoco_mojo.utils.layers.dojo.routers import mosaic
from mujoco_mojo.utils.layers.dojo.routers import sensai as sensai_router
from mujoco_mojo.utils.layers.dojo.sensai import (
    MAX_MODEL_REQUESTS,
    SensAIDeps,
    chat_agent,
    column_manifest_agent,
    guide_agent,
    job_status_agent,
    plot_config_agent,
)
from mujoco_mojo.utils.statusing import (
    Completion,
    ExecutionMode,
    JobStatus,
    JobType,
    RequirementResult,
    StepStatus,
    TrialStatus,
)

job_report = importlib.import_module("mujoco_mojo.utils.layers.dojo.sensai.job_report")
# the package re-exports the agent under the module's own name, so the module has to be imported by path
plot_agent_module = importlib.import_module(
    "mujoco_mojo.utils.layers.dojo.sensai.plot_config_agent"
)

COLUMNS = [
    "time",
    "Bodies/box1/xpos:x",
    "Bodies/box1/xvelr:y",
    "Bodies/box2/xpos:x",
    "Bodies/box2/xvelr:y",
]
SIGNAL = "Bodies/box1/xvelr:y"
UNIT_FILTER = {
    "type": "unit",
    "enabled": True,
    "fromUnit": "rad/s",
    "toUnit": "deg/s",
}

Step = Callable[[list[ModelMessage]], ModelResponse]


def call(tool: str, **args: Any) -> Step:
    """A model step that calls one tool."""
    return lambda _messages: ModelResponse(parts=[ToolCallPart(tool, args)])


def say(text: str) -> Step:
    """A model step that answers in text."""
    return lambda _messages: ModelResponse(parts=[TextPart(text)])


def make_config() -> PlotConfig:
    return PlotConfig.model_validate(
        {
            "yAxes": {SIGNAL: {"color": "#00bc7d", "filters": [UNIT_FILTER]}},
            "title": "Velocity",
        }
    )


def make_two() -> PlotConfig:
    """The config with a second signal plotted next to the first."""
    return PlotConfig.model_validate(
        {
            "yAxes": {
                SIGNAL: {"color": "#00bc7d", "filters": [UNIT_FILTER]},
                "Bodies/box1/xpos:x": {"color": "#3080ff"},
            },
            "title": "Velocity",
        }
    )


def instructions(messages: list[ModelMessage]) -> str:
    """The instructions the model was sent with its latest request, which is where the plot agent shows it the plot."""
    last = messages[-1]
    assert isinstance(last, ModelRequest)
    return last.instructions or ""


def plot_shown(messages: list[ModelMessage]) -> dict[str, Any]:
    """The plot the model was shown with its latest request."""
    text = instructions(messages)
    assert text.startswith("The plot right now:\n"), text
    return json.loads(text.split("\n", 1)[1])


def make_job(
    workdir: Path,
    trials: dict[int, tuple[float, Completion]],
    n_trial: int | None = None,
) -> JobStatus:
    """A job whose finished trials took the given seconds and ended as given, with `n_trial` expected in all."""
    job = JobStatus(
        job_type=JobType.MONTE_CARLO,
        execution_mode=ExecutionMode.LOCAL,
        workdir=workdir,
        n_proc=1,
        padding_style="02",
        seed=0,
        generator=("generate", None, None),
        runtime=("runtime", None, None),
        objective=("objective", None, None),
        trial_nums=list(range(len(trials) if n_trial is None else n_trial)),
    )
    for trial_num, (seconds, completion) in trials.items():
        job.update_trial(
            TrialStatus(
                trial_num=trial_num,
                completion=completion,
                solving=StepStatus(elapsed=seconds),
            ),
            save=False,
        )
    return job


def make_deps(
    config: PlotConfig | None,
    columns: list[str] | None = None,
    job: JobStatus | None = None,
) -> SensAIDeps:
    manifest: ColumnManifest = {
        "all": COLUMNS if columns is None else columns,
        "rotatable_vectors": [],
        "available_quats": [],
        "column_metadata": {},
    }
    return SensAIDeps(
        job_status=job, column_manifest=manifest, current_plot_config=config
    )


def tool_results(messages: list[ModelMessage]) -> list[Any]:
    """The tool results and retry notes the model was just sent, in order."""
    last = messages[-1]
    assert isinstance(last, ModelRequest)
    # a refusal reaches the model as a "retry-prompt" part in older pydantic-ai and as a
    # tool return marked retried in newer, so the part kind is read instead of a class
    return [
        part.content
        for part in last.parts
        if isinstance(part, ToolReturnPart) or part.part_kind == "retry-prompt"
    ]


def scripted(*steps: Step) -> FunctionModel:
    remaining = iter(steps)

    def function(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return next(remaining)(messages)

    return FunctionModel(function)


def run_plot_agent(model: FunctionModel, deps: SensAIDeps) -> str:
    # asyncio.run closes its loop; the agent's run_sync leaves one open, whose
    # warning then lands in whichever test is running when it is collected
    return asyncio.run(plot_config_agent.run("do it", model=model, deps=deps)).output


def run_job_agent(model: FunctionModel, deps: SensAIDeps) -> str:
    return asyncio.run(job_status_agent.run("do it", model=model, deps=deps)).output


JOB_TOOLS = (
    "get_job_summary",
    "get_running_trials",
    "get_recent_trials",
    "get_trials_by_duration",
    "get_duration_statistics",
    "get_completion_timeline",
    "get_requirement_results",
    "get_errored_trials",
    "get_trial_log",
    "get_trial_breakdown",
    "get_trial_details",
    "compare_trials",
    "get_job_configuration",
)
NO_JOB = "No job is currently loaded."
NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
"""The clock the job agent's tools read in these tests."""


class TestJobAgent:
    """The job agent answers from what its tools work out, and says it in words: the chat agent sees only the agent's output, so its tool results have to be in it."""

    @staticmethod
    def ask(deps: SensAIDeps, tool: str, **args: Any) -> str:
        """What one tool returned to the model."""
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return say("done")(messages)

        run_job_agent(scripted(call(tool, **args), finish), deps)
        return str(seen[0])

    @pytest.fixture(autouse=True)
    def clock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(job_report, "now", lambda: NOW)

    def job(self, tmp_path: Path) -> JobStatus:
        return make_job(
            tmp_path,
            {
                0: (4.0, Completion.SUCCESS),
                1: (9.5, Completion.ERROR),
                2: (1.25, Completion.FAILURE),
            },
            n_trial=5,
        )

    def running_job(self, tmp_path: Path) -> JobStatus:
        """Trial 0 finished, trial 3 began generating 90 seconds ago, trial 4 is solving, 1 and 2 wait."""
        job = make_job(tmp_path, {0: (4.0, Completion.SUCCESS)}, n_trial=5)
        job.update_trial(
            TrialStatus(
                trial_num=3,
                generating=StepStatus(started=NOW - timedelta(seconds=90)),
            ),
            save=False,
        )
        job.update_trial(
            TrialStatus(
                trial_num=4,
                step="solving",
                generating=StepStatus(
                    started=NOW - timedelta(seconds=40), elapsed=10.0
                ),
                solving=StepStatus(started=NOW - timedelta(seconds=30)),
            ),
            save=False,
        )
        return job

    def test_it_offers_a_tool_for_each_question_and_no_other(self) -> None:
        tools, _prompt = self.offered()

        assert set(tools) == set(JOB_TOOLS)

    @pytest.mark.parametrize(
        ("tool", "args"),
        [
            ("get_job_summary", {}),
            ("get_running_trials", {}),
            ("get_recent_trials", {"count": 3}),
            ("get_trials_by_duration", {"count": 3}),
            ("get_duration_statistics", {}),
            ("get_completion_timeline", {}),
            ("get_requirement_results", {"requirement": "x"}),
            ("get_errored_trials", {}),
            ("get_trial_log", {"trial_num": 1}),
            ("get_trial_breakdown", {}),
            ("get_trial_details", {"trial_num": 1}),
            ("compare_trials", {"trial_nums": [1, 2]}),
            ("get_job_configuration", {}),
        ],
    )
    def test_every_tool_says_so_when_no_job_is_loaded(
        self, tool: str, args: dict[str, Any]
    ) -> None:
        assert self.ask(make_deps(None), tool, **args) == NO_JOB

    def test_the_answer_is_the_text_the_model_wrote(self, tmp_path: Path) -> None:
        output = run_job_agent(
            scripted(call("get_job_summary"), say("Trial 1 was slowest at 9.50s.")),
            make_deps(None, job=self.job(tmp_path)),
        )

        assert output == "Trial 1 was slowest at 9.50s."

    def test_the_chat_agent_is_handed_that_answer_and_not_the_job_status(
        self, tmp_path: Path
    ) -> None:
        """The job agent's output used to be the whole `JobStatus`, so what its tools found (the ranking, say) never reached the chat agent, which then asked again until the request limit."""
        handed: list[Any] = []

        def look(messages: list[ModelMessage]) -> ModelResponse:
            handed.extend(tool_results(messages))
            return say("Trial 0 was the slowest.")(messages)

        model = TestChatRoute.router_model(
            [call("ask_job_status_agent", request="which trial took longest?"), look],
            [
                call("get_trials_by_duration", count=1),
                say("Trial 0 took the longest: 4.00s."),
            ],
        )

        asyncio.run(
            chat_agent.run(
                "which trial took longest?",
                model=model,
                deps=make_deps(None, job=self.job(tmp_path)),
            )
        )

        assert handed == ["Trial 0 took the longest: 4.00s."]

    def test_the_model_gets_the_tools_result_to_write_its_answer_from(
        self, tmp_path: Path
    ) -> None:
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return say("done")(messages)

        run_job_agent(
            scripted(call("get_errored_trials"), finish),
            make_deps(None, job=self.job(tmp_path)),
        )

        assert "1 trials errored: 1." in seen[0]

    class TestDurations:
        """The question that ran the model into the request limit was which trial took the longest: the only per-trial tool took one trial number at a time, so it would have had to look at all of them."""

        @staticmethod
        def ranked(job: JobStatus, **args: Any) -> list[str]:
            return TestJobAgent.ask(
                make_deps(None, job=job), "get_trials_by_duration", **args
            ).splitlines()

        def test_the_longest_completed_trials_come_first(self, tmp_path: Path) -> None:
            job = TestJobAgent().job(tmp_path)

            assert self.ranked(job, count=2) == [
                "Longest 2 of 2 completed trials:",
                "  Trial 0: 4.00s (success)",
                "  Trial 2: 1.25s (failure)",
            ]

        def test_an_errored_trial_is_left_out_unless_it_is_asked_for(
            self, tmp_path: Path
        ) -> None:
            job = TestJobAgent().job(tmp_path)

            assert "Trial 1" not in "\n".join(self.ranked(job, count=10))
            assert self.ranked(job, outcome="error") == [
                "Longest 1 of 1 errored trials:",
                "  Trial 1: 9.50s (error)",
            ]

        def test_the_shortest_can_be_asked_for_instead(self, tmp_path: Path) -> None:
            job = TestJobAgent().job(tmp_path)

            assert self.ranked(job, count=1, longest=False) == [
                "Shortest 1 of 2 completed trials:",
                "  Trial 2: 1.25s (failure)",
            ]

        def test_an_outcome_that_is_not_one_of_the_four_is_sent_back_to_the_model(
            self, tmp_path: Path
        ) -> None:
            """The model is told which values there are and asked again, and no ranking is made."""
            job = TestJobAgent().job(tmp_path)

            note = TestJobAgent.ask(
                make_deps(None, job=job), "get_trials_by_duration", outcome="slowest"
            )

            assert "outcome" in note
            assert "Trial" not in note
            for allowed in ("completed", "success", "failure", "error"):
                assert allowed in note

        def test_a_running_trial_is_not_ranked_even_with_time_logged(
            self, tmp_path: Path
        ) -> None:
            """A running trial has some time recorded but has not taken that long yet, so ranking it would name the wrong trial as the slowest."""
            job = make_job(
                tmp_path,
                {0: (3.0, Completion.SUCCESS), 1: (99.0, Completion.INCOMPLETE)},
            )

            assert self.ranked(job, count=5) == [
                "Longest 1 of 1 completed trials:",
                "  Trial 0: 3.00s (success)",
            ]

        def test_it_says_so_when_nothing_has_finished(self, tmp_path: Path) -> None:
            job = make_job(tmp_path, {}, n_trial=3)

            assert "No completed trial has finished yet" in "\n".join(self.ranked(job))

    def test_the_running_trials_are_told_with_their_step_and_how_long(
        self, tmp_path: Path
    ) -> None:
        text = self.ask(
            make_deps(None, job=self.running_job(tmp_path)), "get_running_trials"
        )

        assert text.splitlines() == [
            "Running now: 2 of 5 trials (2 waiting to start, 1 finished). Longest running first:",
            "  Trial 3: generating for 90.00s (1m 30s), running 90.00s (1m 30s) in all",
            "  Trial 4: solving for 30.00s, running 40.00s in all",
        ]

    def test_one_trial_is_told_with_how_long_it_has_run(self, tmp_path: Path) -> None:
        text = self.ask(
            make_deps(None, job=self.running_job(tmp_path)),
            "get_trial_details",
            trial_num=4,
        )

        assert "  running for 40.00s so far, in solving for 30.00s" in text

    def test_the_breakdown_separates_running_from_waiting(self, tmp_path: Path) -> None:
        text = self.ask(
            make_deps(None, job=self.running_job(tmp_path)), "get_trial_breakdown"
        )

        assert "Running (2): 3-4" in text
        assert "Waiting to start (2): 1-2" in text

    def test_the_summary_counts_the_running_trials(self, tmp_path: Path) -> None:
        text = self.ask(
            make_deps(None, job=self.running_job(tmp_path)), "get_job_summary"
        )

        assert "Running now: 2" in text
        assert "Waiting to start: 2" in text

    def test_a_requirement_can_be_looked_into_by_name(self, tmp_path: Path) -> None:
        job = make_job(tmp_path, {}, n_trial=2)
        job.update_trial(
            TrialStatus(
                trial_num=0,
                completion=Completion.FAILURE,
                requirements=[
                    RequirementResult(name="speed", passed=False, message="too fast")
                ],
            ),
            save=False,
        )

        everything = self.ask(make_deps(None, job=job), "get_requirement_results")
        one = self.ask(
            make_deps(None, job=job), "get_requirement_results", requirement="speed"
        )

        assert "speed: failed in 1 of 1 trials" in everything
        assert "  too fast" in one

    def test_the_configuration_is_told(self, tmp_path: Path) -> None:
        text = self.ask(
            make_deps(None, job=self.job(tmp_path)), "get_job_configuration"
        )

        assert "Seed: 0" in text
        assert f"Working folder: {tmp_path}" in text

    def test_the_statistics_are_told(self, tmp_path: Path) -> None:
        text = self.ask(
            make_deps(None, job=self.job(tmp_path)), "get_duration_statistics"
        )

        assert text.startswith("2 completed trials")

    def logged_job(self, tmp_path: Path) -> JobStatus:
        """Three finished trials: 0 succeeded, 1 errored (with a log that says why), 2 missed a requirement."""
        job = make_job(tmp_path, {}, n_trial=4)
        job.start_time = NOW - timedelta(seconds=100)
        for trial_num, began, took, completion, requirements in (
            (0, 100, 40.0, Completion.SUCCESS, []),
            (1, 80, 30.0, Completion.ERROR, []),
            (
                2,
                60,
                3.0,
                Completion.FAILURE,
                [RequirementResult(name="speed", passed=False, message="too fast")],
            ),
        ):
            job.update_trial(
                TrialStatus(
                    trial_num=trial_num,
                    completion=completion,
                    step="solving",
                    solving=StepStatus(
                        started=NOW - timedelta(seconds=began), elapsed=took
                    ),
                    requirements=requirements,
                ),
                save=False,
            )
        folder = job.trial_num_to_path(1)
        folder.mkdir(parents=True)
        entry = {
            "timestamp": (NOW - timedelta(seconds=55)).timestamp() * 1000,
            "level": "ERROR",
            "message": "Trial 1 failed with the following error: bad mass\n"
            "Traceback (most recent call last):\n"
            "ValueError: bad mass",
        }
        (folder / "mojo.log").write_text(json.dumps(entry) + "\n")
        return job

    def test_the_most_recent_trials_are_told_with_why_they_failed(
        self, tmp_path: Path
    ) -> None:
        text = self.ask(
            make_deps(None, job=self.logged_job(tmp_path)), "get_recent_trials", count=3
        )

        assert text.splitlines() == [
            "Most recent 3 of 3 trials, newest first:",
            "  Trial 1: error, finished 50.00s ago, took 30.00s, ValueError: bad mass",
            "  Trial 2: failure, finished 57.00s ago, took 3.00s, missed speed",
            "  Trial 0: success, finished 60.00s (1m 0s) ago, took 40.00s",
        ]

    def test_only_the_recent_errors_can_be_asked_for(self, tmp_path: Path) -> None:
        text = self.ask(
            make_deps(None, job=self.logged_job(tmp_path)),
            "get_recent_trials",
            outcome="error",
        )

        assert (
            text.splitlines()[0] == "Most recent 1 of 1 errored trials, newest first:"
        )

    def test_the_timeline_is_told(self, tmp_path: Path) -> None:
        text = self.ask(
            make_deps(None, job=self.logged_job(tmp_path)), "get_completion_timeline"
        )

        assert text.splitlines()[0] == (
            "3 trials finished in the 50.00s the job has run, in 8 slices of 6s:"
        )

    def test_a_trials_log_is_told(self, tmp_path: Path) -> None:
        text = self.ask(
            make_deps(None, job=self.logged_job(tmp_path)),
            "get_trial_log",
            trial_num=1,
            level="error",
        )

        assert text.splitlines()[0] == (
            "Last 1 of 1 error-or-worse log entries of trial 1, oldest first:"
        )
        assert "ValueError: bad mass" in text

    def test_trials_are_compared(self, tmp_path: Path) -> None:
        text = self.ask(
            make_deps(None, job=self.logged_job(tmp_path)),
            "compare_trials",
            trial_nums=[0, 2],
        )

        assert text.splitlines()[:2] == [
            "Comparing trials 0, 2:",
            "  outcome: trial 0 success, trial 2 failure",
        ]

    def test_the_errored_trials_and_one_errored_trial_give_what_the_log_says(
        self, tmp_path: Path
    ) -> None:
        deps = make_deps(None, job=self.logged_job(tmp_path))

        errored = self.ask(deps, "get_errored_trials")
        details = self.ask(deps, "get_trial_details", trial_num=1)

        assert "  ValueError: bad mass: trial 1, broke while solving" in errored
        assert "  broke while solving: ValueError: bad mass" in details

    @staticmethod
    def offered() -> tuple[dict[str, Any], str]:
        """The tools the model is offered, each with its parameters' schemas, and the system prompt."""
        tools: dict[str, Any] = {}
        prompt: list[str] = []

        def look(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            for tool in info.function_tools:
                tools[tool.name] = tool.parameters_json_schema["properties"]
            first = messages[0]
            assert isinstance(first, ModelRequest)
            prompt.extend(
                str(part.content)
                for part in first.parts
                if part.part_kind == "system-prompt"
            )
            return ModelResponse(parts=[TextPart("ok")])

        run_job_agent(FunctionModel(look), make_deps(None))
        return tools, "\n".join(prompt)

    def test_every_parameter_says_what_to_send_and_a_text_or_number_one_gives_an_example(
        self,
    ) -> None:
        tools, _prompt = self.offered()

        for name, parameters in tools.items():
            for parameter, schema in parameters.items():
                assert schema.get("description"), (name, parameter)
                if schema.get("type") != "boolean":
                    assert "such as" in schema["description"], (name, parameter)

    def test_the_outcome_parameters_offer_the_five_outcomes(self) -> None:
        tools, _prompt = self.offered()

        for tool in ("get_trials_by_duration", "get_recent_trials"):
            schema = tools[tool]["outcome"]
            assert set(schema["enum"]) == {
                "any",
                "completed",
                "success",
                "failure",
                "error",
            }, tool

    def test_the_log_level_parameter_offers_its_three_levels(self) -> None:
        tools, _prompt = self.offered()

        assert set(tools["get_trial_log"]["level"]["enum"]) == {
            "any",
            "warning",
            "error",
        }

    def test_the_prompt_shows_a_call_of_every_tool(self) -> None:
        _tools, prompt = self.offered()

        for name in JOB_TOOLS:
            assert f"{name}(" in prompt, name

    def test_the_prompt_points_at_the_ranking_for_slowest_and_fastest(self) -> None:
        _tools, prompt = self.offered()

        assert "call get_trials_by_duration once" in prompt
        assert "do not look at trials one at a time" in prompt

    def test_the_prompt_sends_the_model_to_the_logs_for_why_a_trial_errored(
        self,
    ) -> None:
        """The status files keep that a trial errored, not the exception, but the trial's log has it, so the model is told to read that and not to make a cause up when there is none."""
        _tools, prompt = self.offered()

        assert "use get_errored_trials, which reads each trial's log" in prompt
        assert "get_trial_log for the log of one trial" in prompt
        assert "do not invent a cause" in prompt

    def test_the_prompt_says_to_compare_chosen_trials_with_one_call(self) -> None:
        _tools, prompt = self.offered()

        assert "call compare_trials once with all their numbers" in prompt

    def test_the_prompt_is_one_paragraph_per_rule_without_stray_backslashes(
        self,
    ) -> None:
        """The prompt's line continuations are written in a Python string, where a doubled backslash would be sent to the model as one."""
        _tools, prompt = self.offered()

        assert "\\" not in prompt


def run_guide_agent(model: FunctionModel) -> str:
    return asyncio.run(
        guide_agent.run("do it", model=model, deps=make_deps(None))
    ).output


class TestGuideAgent:
    """The agent that answers "how do I use Mojo" from the user guides that ship with the package."""

    @staticmethod
    def results(*calls: Step) -> list[Any]:
        """What each of the tool calls returned, in order."""
        seen: list[Any] = []

        def collecting(step: Step) -> Step:
            def run(messages: list[ModelMessage]) -> ModelResponse:
                seen.extend(tool_results(messages))
                return step(messages)

            return run

        run_guide_agent(
            scripted(
                calls[0], *[collecting(c) for c in calls[1:]], collecting(say("done"))
            )
        )
        return seen

    def test_a_search_lists_the_matches_with_their_path_section_and_link(self) -> None:
        seen = self.results(call("search_guides", query="submit a job to SLURM"))

        text = str(seen[0])
        assert text.startswith(
            "1. workflow/running-jobs/running-jobs.md | Running Jobs"
        )
        assert (
            "https://hydrowelder.github.io/mujoco-mojo/user-guides/workflow/running-jobs/running-jobs/"
            in text
        )

    def test_a_search_that_matches_nothing_says_so_and_points_at_the_list(self) -> None:
        seen = self.results(call("search_guides", query="zzzqqq"))

        assert "Nothing in the guides matches" in str(seen[0])

    def test_a_guide_is_read_with_its_link_on_top(self) -> None:
        seen = self.results(call("read_guide", path="features/pose-context.md"))

        assert str(seen[0]).startswith(
            "Pose Context (https://hydrowelder.github.io/mujoco-mojo/user-guides/features/pose-context/)"
        )

    def test_a_section_of_a_guide_can_be_read(self) -> None:
        seen = self.results(
            call(
                "read_guide",
                path="workflow/runtime-script.md",
                section="Video Recording",
            )
        )

        assert str(seen[0]).startswith("Runtime Script > Video Recording (")

    def test_a_path_that_is_not_a_guide_is_answered_with_the_guides_not_an_error(
        self,
    ) -> None:
        seen = self.results(call("read_guide", path="workflow/nope.md"))

        assert "There is no guide at 'workflow/nope.md'" in str(seen[0])
        assert "workflow/getting-started.md" in str(seen[0])

    def test_the_instructions_list_the_guides_and_say_to_answer_only_from_them(
        self,
    ) -> None:
        prompts: list[str] = []

        def look(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            first = messages[0]
            assert isinstance(first, ModelRequest)
            prompts.extend(
                str(part.content)
                for part in first.parts
                if part.part_kind == "system-prompt"
            )
            return ModelResponse(parts=[TextPart("ok")])

        run_guide_agent(FunctionModel(look))

        prompt = prompts[0]
        assert "- workflow/getting-started.md: Getting Started" in prompt
        assert "- features/requirements.md: Requirements Checker" in prompt
        assert "from the Mojo user guides, and only from them" in prompt
        assert "Do not answer from memory" in prompt
        assert 'search_guides(query="submit a job to SLURM")' in prompt
        assert "See [Title](link)" in prompt

    def test_every_parameter_of_a_tool_says_what_to_send_with_an_example(self) -> None:
        tools: dict[str, Any] = {}

        def look(_messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            for tool in info.function_tools:
                tools[tool.name] = tool.parameters_json_schema["properties"]
            return ModelResponse(parts=[TextPart("ok")])

        run_guide_agent(FunctionModel(look))

        assert set(tools) == {"search_guides", "read_guide"}
        for name, parameters in tools.items():
            for parameter, schema in parameters.items():
                assert "such as" in schema.get("description", ""), (name, parameter)

    def test_what_it_searched_for_and_read_is_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO)

        run_guide_agent(
            scripted(
                call("search_guides", query="submit a job to SLURM"),
                call("read_guide", path="workflow/init.md", section="Generated Files"),
                say("done"),
            )
        )

        assert "SensAI search_guides 'submit a job to SLURM':" in caplog.text
        assert "SensAI read_guide: workflow/init.md Generated Files" in caplog.text


class TestEditingThePlot:
    def test_an_edit_changes_what_was_asked_and_nothing_else(self) -> None:
        config = make_config()
        deps = make_deps(config)

        output = run_plot_agent(
            scripted(
                call("edit_plot_config", changes={"title": "hello"}),
                say("Renamed the plot."),
            ),
            deps,
        )

        expected = config.model_dump(mode="json")
        expected["title"] = "hello"
        assert deps.current_plot_config is not None
        assert deps.current_plot_config.model_dump(mode="json") == expected
        assert output == "Renamed the plot."

    def test_the_tool_says_which_parts_changed(self) -> None:
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("ok")])

        run_plot_agent(
            scripted(
                call("edit_plot_config", changes={"title": "a", "grid": "none"}), finish
            ),
            make_deps(make_config()),
        )

        assert seen == ["Done. Changed: grid, title."]

    def test_the_config_it_started_from_is_not_edited_in_place(self) -> None:
        config = make_config()
        before = config.model_dump(mode="json")
        deps = make_deps(config)

        run_plot_agent(
            scripted(call("edit_plot_config", changes={"title": "x"}), say("ok")), deps
        )

        assert config.model_dump(mode="json") == before

    def test_a_signal_is_recolored_without_losing_its_filter(self) -> None:
        deps = make_deps(make_config())

        run_plot_agent(
            scripted(
                call(
                    "edit_plot_config",
                    changes={"yAxes": {SIGNAL: {"color": "#ff0000"}}},
                ),
                say("ok"),
            ),
            deps,
        )

        assert deps.current_plot_config is not None
        signal = deps.current_plot_config.y_axes[SIGNAL]
        assert signal.color == "#ff0000"
        assert [f.type for f in signal.filters] == ["unit"]

    def test_a_refused_edit_goes_back_to_the_model_with_the_reason(self) -> None:
        deps = make_deps(make_config())
        reasons: list[Any] = []

        def correct(messages: list[ModelMessage]) -> ModelResponse:
            reasons.extend(tool_results(messages))
            return ModelResponse(
                parts=[
                    ToolCallPart("edit_plot_config", {"changes": {"title": "fixed"}})
                ]
            )

        run_plot_agent(
            scripted(
                call("edit_plot_config", changes={"titel": "typo"}), correct, say("ok")
            ),
            deps,
        )

        assert len(reasons) == 1
        assert 'has no field "titel"' in str(reasons[0])
        assert "Did you mean: title" in str(reasons[0])
        assert deps.current_plot_config is not None
        assert deps.current_plot_config.title == "fixed"

    def test_a_refused_edit_leaves_the_plot_as_it_was(self) -> None:
        config = make_config()
        deps = make_deps(config)

        # the model gives up after the refusal, so the retry limit ends the run
        with pytest.raises(Exception, match="retries"):
            run_plot_agent(
                scripted(*[call("edit_plot_config", changes={"bogus": 1})] * 6), deps
            )

        assert deps.current_plot_config == config

    def test_a_mangled_signal_name_is_refused_with_the_real_names(self) -> None:
        deps = make_deps(make_config())
        reasons: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            reasons.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("could not")])

        run_plot_agent(
            scripted(
                call("edit_plot_config", changes={"yAxes": {"Bodies": {}}}), finish
            ),
            deps,
        )

        assert "not a signal of this trial" in str(reasons[0])
        assert deps.current_plot_config is not None
        assert list(deps.current_plot_config.y_axes) == [SIGNAL]

    def test_nothing_is_changed_when_no_config_is_loaded(self) -> None:
        deps = make_deps(None)
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("nothing loaded")])

        run_plot_agent(
            scripted(call("edit_plot_config", changes={"title": "x"}), finish), deps
        )

        assert deps.current_plot_config is None
        assert "No plot config is currently loaded" in seen[0]

    def test_a_refusal_is_remembered_so_the_user_can_be_told(self) -> None:
        deps = make_deps(make_config())

        run_plot_agent(
            scripted(call("edit_plot_config", changes={"bogus": 1}), say("gave up")),
            deps,
        )

        assert deps.plot_edit_refusal is not None
        assert 'has no field "bogus"' in deps.plot_edit_refusal

    def test_a_good_edit_clears_the_remembered_refusal(self) -> None:
        deps = make_deps(make_config())

        run_plot_agent(
            scripted(
                call("edit_plot_config", changes={"bogus": 1}),
                call("edit_plot_config", changes={"title": "fixed"}),
                say("ok"),
            ),
            deps,
        )

        assert deps.plot_edit_refusal is None

    def test_setting_a_value_it_already_has_reports_no_change(self) -> None:
        deps = make_deps(make_config())
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("already")])

        run_plot_agent(
            scripted(call("edit_plot_config", changes={"title": "Velocity"}), finish),
            deps,
        )

        assert seen == ["Nothing changed: the plot already has those values."]

    def test_null_for_every_signal_is_refused_and_the_model_can_add_instead(
        self,
    ) -> None:
        """The incident: asked to add a signal, a model sent `{"yAxes": null}` and the plot lost its signals. It is refused with a reason that lets the model send the right edit."""
        deps = make_deps(make_config())
        reasons: list[Any] = []

        def add(messages: list[ModelMessage]) -> ModelResponse:
            reasons.extend(tool_results(messages))
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "edit_plot_config",
                        {"changes": {"yAxes": {"Bodies/box2/xpos:x": {}}}},
                    )
                ]
            )

        run_plot_agent(
            scripted(call("edit_plot_config", changes={"yAxes": None}), add, say("ok")),
            deps,
        )

        assert "yAxes cannot be null" in str(reasons[0])
        assert "remove_signals" in str(reasons[0])
        assert deps.current_plot_config is not None
        assert list(deps.current_plot_config.y_axes) == [SIGNAL, "Bodies/box2/xpos:x"]

    def test_null_never_empties_the_plot_even_if_the_model_insists(self) -> None:
        config = make_config()
        deps = make_deps(config)

        run_plot_agent(
            scripted(
                *[call("edit_plot_config", changes={"yAxes": None})] * 2,
                say("could not"),
            ),
            deps,
        )

        assert deps.current_plot_config == config


class TestRemovingSignals:
    def test_the_named_signal_stops_being_plotted_and_the_rest_stays(self) -> None:
        deps = make_deps(make_two())

        run_plot_agent(
            scripted(call("remove_signals", names=["Bodies/box1/xpos:x"]), say("ok")),
            deps,
        )

        assert deps.current_plot_config is not None
        assert list(deps.current_plot_config.y_axes) == [SIGNAL]
        assert deps.current_plot_config.title == "Velocity"

    def test_the_tool_says_which_part_changed(self) -> None:
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("ok")])

        run_plot_agent(
            scripted(call("remove_signals", names=[SIGNAL]), finish),
            make_deps(make_two()),
        )

        assert seen == ["Done. Changed: yAxes."]

    def test_a_signal_that_is_not_plotted_is_refused_with_what_is(self) -> None:
        config = make_two()
        deps = make_deps(config)
        reasons: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            reasons.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("it was not plotted")])

        run_plot_agent(
            scripted(call("remove_signals", names=["Bodies/box2/xpos:x"]), finish),
            deps,
        )

        assert "Not plotted" in str(reasons[0])
        assert SIGNAL in str(reasons[0])
        assert deps.current_plot_config == config
        assert deps.plot_edit_refusal is not None

    def test_a_good_removal_clears_the_remembered_refusal(self) -> None:
        deps = make_deps(make_two())

        run_plot_agent(
            scripted(
                call("remove_signals", names=["nope"]),
                call("remove_signals", names=[SIGNAL]),
                say("ok"),
            ),
            deps,
        )

        assert deps.plot_edit_refusal is None

    def test_nothing_is_changed_when_no_config_is_loaded(self) -> None:
        deps = make_deps(None)
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("nothing loaded")])

        run_plot_agent(scripted(call("remove_signals", names=[SIGNAL]), finish), deps)

        assert deps.current_plot_config is None
        assert "No plot config is currently loaded" in seen[0]


class TestAddingSignals:
    BOX2 = "Bodies/box2/xvelr:y"

    def test_a_signal_is_added_and_the_plotted_ones_stay(self) -> None:
        deps = make_deps(make_config())

        run_plot_agent(
            scripted(call("add_signals", names=[self.BOX2]), say("ok")), deps
        )

        assert deps.current_plot_config is not None
        assert list(deps.current_plot_config.y_axes) == [SIGNAL, self.BOX2]
        assert deps.current_plot_config.y_axes[SIGNAL] == make_config().y_axes[SIGNAL]

    def test_several_signals_each_get_their_own_color(self) -> None:
        deps = make_deps(make_config())

        run_plot_agent(
            scripted(
                call("add_signals", names=[self.BOX2, "Bodies/box2/xpos:x"]), say("ok")
            ),
            deps,
        )

        assert deps.current_plot_config is not None
        colors = [y.color for y in deps.current_plot_config.y_axes.values()]
        assert len(colors) == 3
        assert len(set(colors)) == 3

    def test_the_tool_says_which_part_changed(self) -> None:
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("ok")])

        run_plot_agent(
            scripted(call("add_signals", names=[self.BOX2]), finish),
            make_deps(make_config()),
        )

        assert seen == ["Done. Changed: yAxes."]

    def test_a_signal_that_is_already_plotted_changes_nothing(self) -> None:
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("ok")])

        config = make_config()
        deps = make_deps(config)

        run_plot_agent(scripted(call("add_signals", names=[SIGNAL]), finish), deps)

        assert deps.current_plot_config == config
        assert seen[0].startswith("Nothing changed")

    def test_a_name_with_its_slashes_turned_to_underscores_is_refused_with_the_real_one(
        self,
    ) -> None:
        """The names the model sent in the incident, `Bodies_box2_xvelr_y`, which is not a signal, and the refusal points at the real name."""
        deps = make_deps(make_config())
        reasons: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            reasons.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("could not")])

        run_plot_agent(
            scripted(call("add_signals", names=["Bodies_box2_xvelr_y"]), finish), deps
        )

        assert "not a signal of this trial" in str(reasons[0])
        assert self.BOX2 in str(reasons[0])
        assert deps.current_plot_config == make_config()

    def test_no_names_is_refused(self) -> None:
        reasons: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            reasons.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("could not")])

        run_plot_agent(
            scripted(call("add_signals", names=[]), finish), make_deps(make_config())
        )

        assert "at least one signal" in str(reasons[0])

    def test_nothing_is_changed_when_no_config_is_loaded(self) -> None:
        deps = make_deps(None)
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("nothing loaded")])

        run_plot_agent(scripted(call("add_signals", names=[self.BOX2]), finish), deps)

        assert deps.current_plot_config is None
        assert "No plot config is currently loaded" in seen[0]

    def test_the_incident_every_malformed_edit_is_refused_and_the_plot_survives(
        self,
    ) -> None:
        """The edits a real model sent, in order, from `mojo.log` (the `...` values are the model's own). None may change the plot, each reason has to say what is wrong, and the call that works is accepted."""
        config = make_config()
        deps = make_deps(config)
        reasons: list[str] = []

        def note(messages: list[ModelMessage]) -> None:
            reasons.extend(str(r) for r in tool_results(messages))

        def then(step: Step) -> Step:
            def run(messages: list[ModelMessage]) -> ModelResponse:
                note(messages)
                return step(messages)

            return run

        run_plot_agent(
            scripted(
                call(
                    "edit_plot_config",
                    changes={"yAxes_add": [self.BOX2], "yAxes": {}},
                ),
                then(
                    call(
                        "edit_plot_config",
                        changes={
                            "yAxes": {"Bodies": "...", "Bodies_box2_xvelr_y": "..."}
                        },
                    )
                ),
                then(
                    call(
                        "edit_plot_config",
                        changes={
                            "yAxes": {
                                "Bodies_box2_xvelr_y": None,
                                "Bodies_box1_xvelr_y": None,
                                "Bodies": None,
                            }
                        },
                    )
                ),
                then(call("add_signals", names=[self.BOX2])),
                then(say("Added.")),
            ),
            deps,
        )

        assert 'has no field "yAxes_add"' in reasons[0]
        assert 'yAxes["Bodies"] must be an object' in reasons[1]
        assert "cannot be null" in reasons[2]
        assert reasons[3] == "Done. Changed: yAxes."
        assert deps.current_plot_config is not None
        assert list(deps.current_plot_config.y_axes) == [SIGNAL, self.BOX2]


class TestEditingOneSignal:
    def test_the_color_changes_and_the_filter_stays(self) -> None:
        deps = make_deps(make_config())

        run_plot_agent(
            scripted(
                call("edit_signal", name=SIGNAL, changes={"color": "#ff0000"}),
                say("ok"),
            ),
            deps,
        )

        assert deps.current_plot_config is not None
        signal = deps.current_plot_config.y_axes[SIGNAL]
        assert signal.color == "#ff0000"
        assert [f.type for f in signal.filters] == ["unit"]

    def test_the_other_signals_are_left_alone(self) -> None:
        config = make_two()
        deps = make_deps(config)

        run_plot_agent(
            scripted(call("edit_signal", name=SIGNAL, changes={"width": 6}), say("ok")),
            deps,
        )

        assert deps.current_plot_config is not None
        assert (
            deps.current_plot_config.y_axes["Bodies/box1/xpos:x"]
            == (config.y_axes["Bodies/box1/xpos:x"])
        )
        assert deps.current_plot_config.y_axes[SIGNAL].width == 6

    def test_a_signal_that_is_not_plotted_is_refused_and_add_signals_is_suggested(
        self,
    ) -> None:
        deps = make_deps(make_config())
        reasons: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            reasons.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("could not")])

        run_plot_agent(
            scripted(
                call(
                    "edit_signal",
                    name="Bodies/box2/xvelr:y",
                    changes={"color": "#ff0000"},
                ),
                finish,
            ),
            deps,
        )

        assert "is not plotted" in str(reasons[0])
        assert "add_signals" in str(reasons[0])
        assert SIGNAL in str(reasons[0])
        assert deps.current_plot_config == make_config()

    def test_a_field_a_signal_does_not_have_is_refused(self) -> None:
        reasons: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            reasons.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("could not")])

        run_plot_agent(
            scripted(
                call("edit_signal", name=SIGNAL, changes={"colour": "#ff0000"}), finish
            ),
            make_deps(make_config()),
        )

        assert 'has no field "colour"' in str(reasons[0])

    def test_null_is_refused(self) -> None:
        config = make_config()
        deps = make_deps(config)

        run_plot_agent(
            scripted(
                call("edit_signal", name=SIGNAL, changes={"label": None}), say("no")
            ),
            deps,
        )

        assert deps.plot_edit_refusal is not None
        assert "cannot be null" in deps.plot_edit_refusal
        assert deps.current_plot_config == config

    def test_nothing_is_changed_when_no_config_is_loaded(self) -> None:
        deps = make_deps(None)
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("nothing loaded")])

        run_plot_agent(
            scripted(call("edit_signal", name=SIGNAL, changes={"width": 5}), finish),
            deps,
        )

        assert "No plot config is currently loaded" in seen[0]


class TestWhatTheModelIsTold:
    """The model only sees what pydantic-ai passes on: a tool's summary and each parameter's description. A docstring's `Examples:` section is dropped, which is how a model once had no idea what shape to send."""

    EDITING_TOOLS = frozenset(
        {"add_signals", "remove_signals", "edit_signal", "edit_plot_config"}
    )

    @staticmethod
    def offered_tools_and_prompt() -> tuple[dict[str, Any], str]:
        tools: dict[str, Any] = {}
        prompt: list[str] = []

        def look(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            for tool in info.function_tools:
                tools[tool.name] = tool.parameters_json_schema["properties"]
            first = messages[0]
            assert isinstance(first, ModelRequest)
            prompt.extend(
                str(part.content)
                for part in first.parts
                if part.part_kind == "system-prompt"
            )
            return ModelResponse(parts=[TextPart("ok")])

        asyncio.run(
            plot_config_agent.run(
                "do it", model=FunctionModel(look), deps=make_deps(make_config())
            )
        )
        return tools, "\n".join(prompt)

    def test_every_parameter_of_an_editing_tool_says_what_to_send_with_an_example(
        self,
    ) -> None:
        tools, _prompt = self.offered_tools_and_prompt()

        assert self.EDITING_TOOLS <= set(tools)
        for name in self.EDITING_TOOLS:
            for parameter, schema in tools[name].items():
                assert "such as" in schema.get("description", ""), (name, parameter)

    def test_the_prompt_shows_a_call_of_each_editing_tool(self) -> None:
        _tools, prompt = self.offered_tools_and_prompt()

        for name in self.EDITING_TOOLS | {"find_signals"}:
            assert f"{name}(" in prompt, name

    def test_the_prompt_lists_the_palette_in_order(self) -> None:
        _tools, prompt = self.offered_tools_and_prompt()

        assert ", ".join(PLOT_COLORS) in prompt

    def test_the_prompt_says_to_use_the_palettes_color_for_a_named_color(
        self,
    ) -> None:
        """A user who asks for cyan should get the palette's cyan and not `#00ffff`."""
        _tools, prompt = self.offered_tools_and_prompt()

        assert "send the palette color closest to it" in prompt
        assert "#00ffff" in prompt

    def test_the_prompt_leaves_the_color_of_a_new_signal_to_the_server(self) -> None:
        _tools, prompt = self.offered_tools_and_prompt()

        assert "do not send a color for one unless the user asked for it" in prompt

    def test_the_prompt_says_how_to_plot_the_same_signal_for_another_body(
        self,
    ) -> None:
        _tools, prompt = self.offered_tools_and_prompt()

        assert "swap the body" in prompt
        assert "add_signals" in prompt

    def test_the_prompt_names_the_tool_that_changes_each_part_of_the_plot(
        self,
    ) -> None:
        _tools, prompt = self.offered_tools_and_prompt()

        assert "Plot-wide fields (change them with edit_plot_config)" in prompt
        assert "Signal fields (" in prompt
        assert "edit_signal" in prompt


class TestReadingThePlot:
    def test_a_question_leaves_the_plot_alone(self) -> None:
        config = make_config()
        deps = make_deps(config)

        output = run_plot_agent(scripted(say("You plot one signal.")), deps)

        assert deps.current_plot_config == config
        assert output == "You plot one signal."

    def test_the_current_config_is_given_without_its_defaults(self) -> None:
        seen: list[dict[str, Any]] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.append(plot_shown(messages))
            return ModelResponse(parts=[TextPart("ok")])

        run_plot_agent(scripted(finish), make_deps(make_config()))

        assert seen[0]["title"] == "Velocity"
        assert seen[0]["yAxes"][SIGNAL]["filters"] == [UNIT_FILTER]
        assert "legendPos" not in seen[0]

    def test_it_says_so_when_nothing_is_loaded(self) -> None:
        seen: list[str] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.append(instructions(messages))
            return ModelResponse(parts=[TextPart("ok")])

        run_plot_agent(scripted(finish), make_deps(None))

        assert seen == ["No plot config is currently loaded."]

    def test_the_plot_the_model_sees_follows_each_edit(self) -> None:
        """The model reads the plot from every request it makes, so after an edit it sees the new plot and does not have to look it up again."""
        seen: list[Any] = []

        def after_edit(messages: list[ModelMessage]) -> ModelResponse:
            seen.append(plot_shown(messages)["title"])
            return ModelResponse(parts=[TextPart("ok")])

        def first(messages: list[ModelMessage]) -> ModelResponse:
            seen.append(plot_shown(messages)["title"])
            return call("edit_plot_config", changes={"title": "Renamed"})(messages)

        run_plot_agent(scripted(first, after_edit), make_deps(make_config()))

        assert seen == ["Velocity", "Renamed"]

    def test_no_lookup_tool_is_offered_because_the_plot_is_already_shown(
        self,
    ) -> None:
        names: set[str] = set()

        def finish(_messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            names.update(t.name for t in info.function_tools)
            return ModelResponse(parts=[TextPart("ok")])

        asyncio.run(
            plot_config_agent.run(
                "do it", model=FunctionModel(finish), deps=make_deps(make_config())
            )
        )

        assert "get_current_plot_config" not in names
        assert {
            "edit_plot_config",
            "add_signals",
            "edit_signal",
            "remove_signals",
            "find_signals",
        } <= names

    def test_signals_are_found_by_words(self) -> None:
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("ok")])

        run_plot_agent(
            scripted(call("find_signals", query="box1 xvelr"), finish),
            make_deps(make_config()),
        )

        assert seen == [[SIGNAL]]

    def test_the_signal_search_says_so_when_the_trial_is_unknown(self) -> None:
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("ok")])

        run_plot_agent(
            scripted(call("find_signals", query="box1"), finish),
            make_deps(make_config(), columns=[]),
        )

        assert "No signal list is available" in seen[0]

    def test_filters_are_described_on_request(self) -> None:
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("ok")])

        run_plot_agent(
            scripted(
                call("describe_filters"),
                lambda m: (
                    seen.extend(tool_results(m)),
                    call("describe_filters", filter_type="unit")(m),
                )[1],
                finish,
            ),
            make_deps(make_config()),
        )

        assert "- unit:" in seen[0]
        assert "fromUnit" in seen[1]
        assert "toUnit" in seen[1]


class TestProfiles:
    @pytest.fixture(autouse=True)
    def profiles(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        directory = tmp_path / "profiles"
        directory.mkdir()
        monkeypatch.setattr(mosaic, "_get_profiles_dir", lambda: directory)
        monkeypatch.setattr(plot_agent_module, "_get_profiles_dir", lambda: directory)
        return directory

    def save(self, directory: Path, name: str, config: PlotConfig) -> None:
        profile = {"version": 2, "tabs": [{"config": config.model_dump(mode="json")}]}
        path = directory / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile), encoding="utf-8")

    def test_loading_a_profile_replaces_the_plot(self, profiles: Path) -> None:
        saved = PlotConfig.model_validate(
            {"yAxes": {"Bodies/box2/xpos:x": {"color": "#3080ff"}}, "title": "Saved"}
        )
        self.save(profiles, "robotics/baseline", saved)
        deps = make_deps(make_config())

        run_plot_agent(
            scripted(call("load_plot_config", name="robotics/baseline"), say("ok")),
            deps,
        )

        assert deps.current_plot_config == saved

    def test_a_missing_profile_is_a_retry_and_changes_nothing(
        self, profiles: Path
    ) -> None:
        config = make_config()
        deps = make_deps(config)
        reasons: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            reasons.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("no such profile")])

        run_plot_agent(scripted(call("load_plot_config", name="nope"), finish), deps)

        assert "No saved profile named 'nope'" in str(reasons[0])
        assert deps.current_plot_config == config

    def test_a_good_load_clears_the_remembered_refusal(self, profiles: Path) -> None:
        self.save(profiles, "real", make_config())
        deps = make_deps(None)

        run_plot_agent(
            scripted(
                call("load_plot_config", name="nope"),
                call("load_plot_config", name="real"),
                say("ok"),
            ),
            deps,
        )

        assert deps.plot_edit_refusal is None
        assert deps.current_plot_config == make_config()

    def test_saved_profiles_are_listed(self, profiles: Path) -> None:
        self.save(profiles, "a", make_config())
        self.save(profiles, "folder/b", make_config())
        seen: list[Any] = []

        def finish(messages: list[ModelMessage]) -> ModelResponse:
            seen.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("ok")])

        run_plot_agent(
            scripted(call("list_saved_plot_configs"), finish), make_deps(make_config())
        )

        assert sorted(seen[0]) == ["a", "folder/b"]


class _Sensai(BaseModel):
    enabled: bool = True


class _Dojo(BaseModel):
    sensai: _Sensai = _Sensai()


class _Settings(BaseModel):
    dojo: _Dojo = _Dojo()


class TestChatRoute:
    @pytest.fixture
    def client(self, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        monkeypatch.setattr(sensai_router, "MujocoMojoSettings", _Settings)
        app = FastAPI()
        app.include_router(sensai_router.router, prefix="/sensai")
        return TestClient(app)

    @staticmethod
    def router_model(
        chat: Iterable[Step], specialist: Iterable[Step], name: str | None = None
    ) -> FunctionModel:
        """One model for all the agents: the chat agent routes to a specialist (the plot agent unless a test asks another), whose steps are scripted separately."""
        chat_steps, specialist_steps = iter(chat), iter(specialist)

        def function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            is_chat_agent = "ask_plot_config_agent" in {
                t.name for t in info.function_tools
            }
            return next(chat_steps if is_chat_agent else specialist_steps)(messages)

        async def stream(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | DeltaToolCalls]:
            for part in function(messages, info).parts:
                if isinstance(part, TextPart):
                    yield part.content
                elif isinstance(part, ToolCallPart):
                    yield {
                        0: DeltaToolCall(
                            name=part.tool_name, json_args=json.dumps(part.args)
                        )
                    }

        return FunctionModel(function, stream_function=stream, model_name=name)

    @staticmethod
    def result(response_text: str) -> dict[str, Any]:
        """The data of the `result` event in an SSE response."""
        event = ""
        for line in response_text.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event == "result":
                return json.loads(line.split(":", 1)[1].strip())
        raise AssertionError(f"no result event in: {response_text[:300]}")

    @staticmethod
    def error(response_text: str) -> dict[str, Any]:
        """The data of the `error` event in an SSE response."""
        event = ""
        for line in response_text.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event == "error":
                return json.loads(line.split(":", 1)[1].strip())
        raise AssertionError(f"no error event in: {response_text[:300]}")

    def chat(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        model: Model,
        message: str = "do it",
        columns: list[str] | None = None,
    ) -> dict[str, Any]:
        monkeypatch.setattr(sensai_router, "build_fallback_model", lambda: model)
        response = client.post(
            "/sensai/chat",
            json={
                "message": message,
                "all_columns": COLUMNS if columns is None else columns,
                "current_plot_config_json": make_config().model_dump_json(),
            },
        )
        assert response.status_code == 200
        return self.result(response.text)

    def test_an_edit_sends_the_changed_plot(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model = self.router_model(
            [call("ask_plot_config_agent", request="rename"), say("Renamed it.")],
            [call("edit_plot_config", changes={"title": "hello"}), say("Renamed.")],
        )

        data = self.chat(client, monkeypatch, model)

        expected = make_config().model_dump(mode="json")
        expected["title"] = "hello"
        assert data["routed_to"] == "plot_config"
        assert data["message"] == "Renamed it."
        assert (
            PlotConfig.model_validate(data["plot_config_update"]).model_dump(
                mode="json"
            )
            == expected
        )

    def test_the_update_changes_only_what_was_asked(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The update is the user's own config with the edit applied, so nothing the model did not mention can be mangled."""
        model = self.router_model(
            [call("ask_plot_config_agent", request="rename"), say("ok")],
            [call("edit_plot_config", changes={"title": "hello"}), say("ok")],
        )

        update = self.chat(client, monkeypatch, model)["plot_config_update"]

        assert list(update["yAxes"]) == [SIGNAL]
        assert update["yAxes"][SIGNAL]["filters"][0]["toUnit"] == "deg/s"
        assert update["xAxisTitle"] == ""

    def test_a_question_sends_no_update(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model = self.router_model(
            [
                call("ask_plot_config_agent", request="what is plotted"),
                say("One signal."),
            ],
            [say("You plot one signal.")],
        )

        data = self.chat(client, monkeypatch, model)

        assert data["plot_config_update"] is None
        assert data["routed_to"] == "plot_config"

    def test_a_refused_edit_that_is_not_fixed_sends_no_update(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model = self.router_model(
            [call("ask_plot_config_agent", request="x"), say("That did not work.")],
            [call("edit_plot_config", changes={"bogus": 1}), say("I could not.")],
        )

        assert self.chat(client, monkeypatch, model)["plot_config_update"] is None

    def test_a_refused_edit_the_model_keeps_repeating_is_explained_not_raised(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A model that sends the same refused edit until it runs out of tries used to fail the whole reply with a library error."""
        model = self.router_model(
            [call("ask_plot_config_agent", request="add box2")],
            [call("edit_plot_config", changes={"yAxes": None})] * 4,
        )

        data = self.chat(client, monkeypatch, model)

        assert data["message"].startswith("The last change could not be applied:")
        assert "yAxes cannot be null" in data["message"]
        assert "remove_signals" in data["message"]
        assert data["plot_config_update"] is None
        assert data["routed_to"] == "plot_config"

    def test_a_missing_profile_the_model_keeps_asking_for_is_explained(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(mosaic, "_get_profiles_dir", lambda: tmp_path)
        model = self.router_model(
            [call("ask_plot_config_agent", request="load nope")],
            [call("load_plot_config", name="nope")] * 3,
        )

        data = self.chat(client, monkeypatch, model)

        assert "No saved profile named 'nope'" in data["message"]
        assert data["plot_config_update"] is None

    def test_a_model_that_cannot_use_its_tools_is_told_so_without_failing(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model = self.router_model(
            [call("ask_plot_config_agent", request="x")],
            [call("no_such_tool")] * 4,
        )

        data = self.chat(client, monkeypatch, model)

        assert data["message"] == (
            "The last change could not be applied: the plot-config agent could not finish."
        )

    def test_a_failed_plot_edit_is_the_reply_and_the_chat_model_is_not_asked_again(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The incident's loop: told the change failed, the chat model sent the same request to the plot agent again, each round costing the plot agent's four or more requests again, until the limit ended the message. Now the plot agent's reason is the reply and the chat model's one request is all it makes."""
        requests: list[int] = []

        def counted(step: Step) -> Step:
            def run(messages: list[ModelMessage]) -> ModelResponse:
                requests.append(1)
                return step(messages)

            return run

        model = self.router_model(
            [counted(call("ask_plot_config_agent", request="add box2"))],
            [counted(call("edit_plot_config", changes={"yAxes": None}))] * 4,
        )

        data = self.chat(client, monkeypatch, model)

        assert data["message"].startswith("The last change could not be applied:")
        assert data["routed_to"] == "plot_config"
        # the chat agent's one request and the plot agent's four, with none after
        assert len(requests) == 5

    def test_a_later_failure_is_not_blamed_on_an_earlier_refusal(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The first request was refused an edit and then answered in words, so its refusal is still on record. The second fails without being refused anything, so it must not repeat the first one's reason."""
        model = self.router_model(
            [
                call("ask_plot_config_agent", request="first"),
                call("ask_plot_config_agent", request="second"),
            ],
            [
                call("edit_plot_config", changes={"bogus": 1}),
                say("I could not."),
                *[call("no_such_tool")] * 4,
            ],
        )

        message = self.chat(client, monkeypatch, model)["message"]

        assert message == (
            "The last change could not be applied: the plot-config agent could not finish."
        )

    def test_the_edits_before_a_failure_still_reach_the_plot(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """What the plot agent got right before it gave up is kept: the rename is in the update, and the reason is the reply."""
        model = self.router_model(
            [call("ask_plot_config_agent", request="rename and add")],
            [
                call("edit_plot_config", changes={"title": "Renamed"}),
                *[call("edit_plot_config", changes={"bogus": 1})] * 4,
            ],
        )

        data = self.chat(client, monkeypatch, model)

        assert data["plot_config_update"]["title"] == "Renamed"
        assert "bogus" in data["message"]

    def test_the_same_signal_on_another_body_is_added_next_to_the_plotted_one(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The request from the incident, with the call it needed."""
        model = self.router_model(
            [
                call("ask_plot_config_agent", request="add box2's angular velocity"),
                say("Added box2's angular velocity."),
            ],
            [
                call("add_signals", names=["Bodies/box2/xvelr:y"]),
                say("Added."),
            ],
        )

        data = self.chat(client, monkeypatch, model)

        assert list(data["plot_config_update"]["yAxes"]) == [
            SIGNAL,
            "Bodies/box2/xvelr:y",
        ]
        assert data["message"] == "Added box2's angular velocity."

    def test_a_signal_the_trial_has_is_added(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model = self.router_model(
            [call("ask_plot_config_agent", request="add it"), say("Added.")],
            [
                call(
                    "edit_plot_config",
                    changes={"yAxes": {"Bodies/box2/xpos:x": {}}},
                ),
                say("Added."),
            ],
        )

        update = self.chat(client, monkeypatch, model)["plot_config_update"]

        assert list(update["yAxes"]) == [SIGNAL, "Bodies/box2/xpos:x"]

    def test_a_signal_is_added_after_a_null_edit_is_refused_and_the_plot_keeps_its_own(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The incident end to end: the model's first edit is the one that used to wipe the plot, and what the browser gets is the old signal plus the new one."""
        model = self.router_model(
            [call("ask_plot_config_agent", request="add box2"), say("Added box2.")],
            [
                call("edit_plot_config", changes={"yAxes": None}),
                call("edit_plot_config", changes={"yAxes": {"Bodies/box2/xpos:x": {}}}),
                say("Added."),
            ],
        )

        data = self.chat(client, monkeypatch, model)

        assert list(data["plot_config_update"]["yAxes"]) == [
            SIGNAL,
            "Bodies/box2/xpos:x",
        ]
        assert data["message"] == "Added box2."

    def test_a_signal_is_removed_with_remove_signals(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model = self.router_model(
            [call("ask_plot_config_agent", request="drop it"), say("Dropped.")],
            [call("remove_signals", names=[SIGNAL]), say("Dropped.")],
        )

        update = self.chat(client, monkeypatch, model)["plot_config_update"]

        assert update["yAxes"] == {}
        assert update["title"] == "Velocity"

    def test_a_normal_edit_stays_well_inside_the_request_limit(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Route, look a signal up, get one refusal, correct it, answer and reply: six requests, and the limit is higher so a message with a mistake or two still finishes."""
        requests = 0

        def counted(step: Step) -> Step:
            def run(messages: list[ModelMessage]) -> ModelResponse:
                nonlocal requests
                requests += 1
                return step(messages)

            return run

        model = self.router_model(
            [
                counted(call("ask_plot_config_agent", request="add box2")),
                counted(say("Added.")),
            ],
            [
                counted(call("find_signals", query="box2")),
                counted(call("edit_plot_config", changes={"yAxes": None})),
                counted(
                    call(
                        "edit_plot_config",
                        changes={"yAxes": {"Bodies/box2/xpos:x": {}}},
                    )
                ),
                counted(say("Added.")),
            ],
        )

        data = self.chat(client, monkeypatch, model)

        assert requests == 6
        assert requests < MAX_MODEL_REQUESTS
        assert data["message"] == "Added."

    def chat_error(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        model: Model,
    ) -> str:
        """The `detail` of the `error` event a message ends with, after checking that no `result` was sent."""
        monkeypatch.setattr(sensai_router, "build_fallback_model", lambda: model)
        response = client.post(
            "/sensai/chat",
            json={
                "message": "add box2",
                "all_columns": COLUMNS,
                "current_plot_config_json": make_config().model_dump_json(),
            },
        )
        assert response.status_code == 200
        assert "event: result" not in response.text
        detail = self.error(response.text)["detail"]
        assert isinstance(detail, str)
        return detail

    @pytest.mark.parametrize(
        ("ask", "tool", "args", "while_", "advice", "not_said"),
        [
            (
                "ask_plot_config_agent",
                "find_signals",
                {"query": "box"},
                "while changing the plot",
                "The plot was left as it was",
                "job",
            ),
            (
                "ask_job_status_agent",
                "get_job_summary",
                {},
                "while looking at the job",
                "a narrower question",
                "plot",
            ),
            (
                "ask_column_manifest_agent",
                "get_available_signals",
                {},
                "while looking up signals",
                "one kind of signal",
                "plot",
            ),
            (
                "ask_guide_agent",
                "search_guides",
                {"query": "slurm"},
                "while looking through the guides",
                "one thing at a time",
                "plot",
            ),
        ],
    )
    def test_a_specialist_that_never_stops_is_cut_off_with_the_plot_left_alone(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        ask: str,
        tool: str,
        args: dict[str, Any],
        while_: str,
        advice: str,
        not_said: str,
    ) -> None:
        """The incident made 43 model calls for one message. The specialists share the message's count, so the limit counts the chat agent and whichever specialist it asked together."""
        requests: list[int] = []

        def counted(step: Step) -> Step:
            def run(messages: list[ModelMessage]) -> ModelResponse:
                requests.append(1)
                return step(messages)

            return run

        model = self.router_model(
            itertools.repeat(counted(call(ask, request="add box2"))),
            itertools.repeat(counted(call(tool, **args))),
        )

        detail = self.chat_error(client, monkeypatch, model)

        assert f"stopped after {MAX_MODEL_REQUESTS} model requests" in detail
        assert while_ in detail
        assert advice in detail
        # the message must describe what was actually going on: a job question
        # was once told that "the plot was left as it was"
        assert not_said not in detail
        assert len(requests) <= MAX_MODEL_REQUESTS

    def test_a_chat_agent_that_never_stops_is_cut_off_by_its_own_limit(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Here the specialist answers at once each time, so it is the chat agent's own request that goes over the limit."""
        requests: list[int] = []

        def counted(step: Step) -> Step:
            def run(messages: list[ModelMessage]) -> ModelResponse:
                requests.append(1)
                return step(messages)

            return run

        model = self.router_model(
            itertools.repeat(counted(call("ask_plot_config_agent", request="again"))),
            itertools.repeat(counted(say("nothing to do"))),
        )

        detail = self.chat_error(client, monkeypatch, model)

        assert f"stopped after {MAX_MODEL_REQUESTS} model requests" in detail
        assert len(requests) == MAX_MODEL_REQUESTS

    def test_the_result_names_the_model_that_answered(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model = self.router_model(
            [call("ask_plot_config_agent", request="rename"), say("Renamed.")],
            [call("edit_plot_config", changes={"title": "x"}), say("Renamed.")],
            name="gemini-test-flash",
        )

        data = self.chat(client, monkeypatch, model)

        assert data["model"] == "gemini-test-flash"

    def test_the_model_is_the_one_of_the_chain_that_answered_not_the_chain(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The first model fails, so the second answers, and that is the name shown, which is what tells a reader a fallback was used."""

        def refuse(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            raise ModelAPIError("first-model", "rate limited")

        async def refuse_stream(
            _messages: list[ModelMessage], _info: AgentInfo
        ) -> AsyncIterator[str]:
            raise ModelAPIError("first-model", "rate limited")
            yield ""

        first = FunctionModel(
            refuse, stream_function=refuse_stream, model_name="first-model"
        )
        second = self.router_model(
            [call("ask_plot_config_agent", request="rename"), say("Renamed.")],
            [call("edit_plot_config", changes={"title": "x"}), say("Renamed.")],
            name="second-model",
        )

        data = self.chat(client, monkeypatch, FallbackModel(first, second))

        assert data["message"] == "Renamed."
        assert data["model"] == "second-model"

    def test_the_model_is_the_one_behind_the_final_reply_when_the_chain_switches_midway(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The first model routes the request and is then rate limited, so the second writes the reply. The name is the second's, not the one that answered first."""
        calls = 0
        route = {"request": "rename"}

        def flaky(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            nonlocal calls
            calls += 1
            raise ModelAPIError("first-model", "rate limited")

        async def flaky_stream(
            _messages: list[ModelMessage], _info: AgentInfo
        ) -> AsyncIterator[str | DeltaToolCalls]:
            nonlocal calls
            calls += 1
            if calls > 1:
                raise ModelAPIError("first-model", "rate limited")
            yield {
                0: DeltaToolCall(
                    name="ask_plot_config_agent", json_args=json.dumps(route)
                )
            }

        first = FunctionModel(
            flaky, stream_function=flaky_stream, model_name="first-model"
        )
        second = self.router_model(
            [say("Renamed.")],
            [call("edit_plot_config", changes={"title": "x"}), say("Renamed.")],
            name="second-model",
        )

        data = self.chat(client, monkeypatch, FallbackModel(first, second))

        assert data["message"] == "Renamed."
        assert data["model"] == "second-model"

    def test_a_reply_the_server_wrote_has_no_model(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the plot agent gives up its reason is the reply as it is, so no model wrote it and none is claimed."""
        model = self.router_model(
            [call("ask_plot_config_agent", request="x")],
            [call("edit_plot_config", changes={"bogus": 1})] * 4,
            name="gemini-test-flash",
        )

        data = self.chat(client, monkeypatch, model)

        assert data["message"].startswith("The last change could not be applied:")
        assert data["model"] is None

    def test_an_undo_has_no_model(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            raise AssertionError("the model must not be called for an undo")

        data = self.chat(
            client, monkeypatch, FunctionModel(refuse), message="undo that"
        )

        assert data.get("model") is None

    def test_a_how_to_question_is_answered_from_the_guides(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        answer = (
            "Submit it with `submit_slurm`. See [Running Jobs]"
            "(https://hydrowelder.github.io/mujoco-mojo/user-guides/workflow/running-jobs/running-jobs/)."
        )
        model = self.router_model(
            [call("ask_guide_agent", request="how do I submit to SLURM?"), say(answer)],
            [
                call("search_guides", query="submit a job to SLURM"),
                call("read_guide", path="workflow/running-jobs/running-jobs.md"),
                say(answer),
            ],
            name="gemini-test-flash",
        )

        data = self.chat(
            client, monkeypatch, model, message="how do I submit to SLURM?"
        )

        assert data["message"] == answer
        assert data["routed_to"] == "guide"
        assert data["plot_config_update"] is None
        assert data["model"] == "gemini-test-flash"

    def test_a_how_to_answer_reaches_the_chat_agent_whole(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """What the guide agent writes is what the chat agent is handed, code block and link included, for it to pass on."""
        answer = "Run it:\n\n```python\nrunner.run()\n```\n\nSee [Running Jobs](https://x.test/)."
        handed: list[Any] = []

        def relay(messages: list[ModelMessage]) -> ModelResponse:
            handed.extend(tool_results(messages))
            return ModelResponse(parts=[TextPart("relayed")])

        model = self.router_model(
            [call("ask_guide_agent", request="how do I run?"), relay], [say(answer)]
        )

        self.chat(client, monkeypatch, model)

        assert handed == [answer]

    def test_the_chat_agent_is_told_to_send_how_to_questions_to_the_guide_agent(
        self,
    ) -> None:
        prompts: list[str] = []
        tools: list[str] = []

        def look(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            first = messages[0]
            assert isinstance(first, ModelRequest)
            prompts.extend(
                str(part.content)
                for part in first.parts
                if part.part_kind == "system-prompt"
            )
            tools.extend(t.name for t in info.function_tools)
            return ModelResponse(parts=[TextPart("ok")])

        asyncio.run(
            chat_agent.run("hi", model=FunctionModel(look), deps=make_deps(None))
        )

        assert "ask_guide_agent" in tools
        assert "go to ask_guide_agent" in prompts[0]
        assert "pass it on as it is" in prompts[0]

    def test_a_signal_the_trial_lacks_is_refused_because_the_browser_sent_its_columns(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model = self.router_model(
            [call("ask_plot_config_agent", request="add it"), say("No.")],
            [
                call("edit_plot_config", changes={"yAxes": {"Bodies/box9/xpos:x": {}}}),
                say("There is no such signal."),
            ],
        )

        assert self.chat(client, monkeypatch, model)["plot_config_update"] is None

    def test_undo_makes_no_model_call(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            raise AssertionError("the model must not be called for an undo")

        data = self.chat(
            client, monkeypatch, FunctionModel(refuse), message="undo that"
        )

        assert data["routed_to"] == "undo"
        assert data["plot_config_update"] is None


class TestLogging:
    """A message that goes wrong has to be diagnosable from the log alone: what the model asked for and why it was refused."""

    def test_the_edit_the_model_sent_and_its_refusal_are_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO)

        run_plot_agent(
            scripted(call("edit_plot_config", changes={"yAxes": None}), say("gave up")),
            make_deps(make_config()),
        )

        assert '{"yAxes": null}' in caplog.text
        assert "refused: yAxes cannot be null" in caplog.text

    def test_a_removal_and_its_refusal_are_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO)

        run_plot_agent(
            scripted(call("remove_signals", names=["nope"]), say("gave up")),
            make_deps(make_config()),
        )

        assert "remove_signals: ['nope']" in caplog.text
        assert "remove_signals refused: Not plotted" in caplog.text

    def test_a_signal_search_and_what_it_found_are_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO)

        run_plot_agent(
            scripted(call("find_signals", query="box2 xvelr"), say("ok")),
            make_deps(make_config()),
        )

        assert "find_signals 'box2 xvelr': 1 match(es)" in caplog.text

    def test_an_added_signal_and_its_refusal_are_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO)

        run_plot_agent(
            scripted(call("add_signals", names=["nope"]), say("gave up")),
            make_deps(make_config()),
        )

        assert 'SensAI add_signals: {"yAxes": {"nope": {}}}' in caplog.text
        assert "SensAI add_signals refused:" in caplog.text

    def test_the_plot_agent_giving_up_is_logged_with_its_reason(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        caplog.set_level(logging.INFO)
        app = FastAPI()
        monkeypatch.setattr(sensai_router, "MujocoMojoSettings", _Settings)
        app.include_router(sensai_router.router, prefix="/sensai")
        model = TestChatRoute.router_model(
            [call("ask_plot_config_agent", request="x")],
            [call("edit_plot_config", changes={"bogus": 1})] * 4,
        )
        monkeypatch.setattr(sensai_router, "build_fallback_model", lambda: model)

        TestClient(app).post(
            "/sensai/chat",
            json={
                "message": "x",
                "all_columns": COLUMNS,
                "current_plot_config_json": make_config().model_dump_json(),
            },
        )

        assert 'SensAI plot agent gave up: The plot config has no field "bogus"' in (
            caplog.text
        )

    def test_what_the_job_agent_looked_up_is_logged(
        self, caplog: pytest.LogCaptureFixture, tmp_path: Path
    ) -> None:
        """Only the plot agent's tools used to log, so a message that ran out of requests on a job question left no trace of what it had tried."""
        caplog.set_level(logging.INFO)
        job = make_job(tmp_path, {0: (1.0, Completion.SUCCESS)})

        run_job_agent(
            scripted(
                call("get_job_summary"),
                call("get_running_trials"),
                call("get_trial_breakdown"),
                call("get_trial_details", trial_num=3),
                call("get_trials_by_duration", count=2, longest=False, outcome="error"),
                call("get_duration_statistics"),
                call("get_requirement_results", requirement="speed"),
                call("get_errored_trials"),
                call("get_job_configuration"),
                call("get_recent_trials", count=4, outcome="failure"),
                call("get_completion_timeline"),
                call("get_trial_log", trial_num=2, count=7, level="error"),
                call("compare_trials", trial_nums=[1, 2]),
                say("done"),
            ),
            make_deps(None, job=job),
        )

        assert "SensAI get_job_summary" in caplog.text
        assert "SensAI get_running_trials" in caplog.text
        assert "SensAI get_trial_breakdown" in caplog.text
        assert "SensAI get_trial_details: trial 3" in caplog.text
        assert (
            "SensAI get_trials_by_duration: count=2 longest=False outcome=error"
            in caplog.text
        )
        assert "SensAI get_duration_statistics" in caplog.text
        assert "SensAI get_requirement_results: 'speed'" in caplog.text
        assert "SensAI get_errored_trials" in caplog.text
        assert "SensAI get_job_configuration" in caplog.text
        assert "SensAI get_recent_trials: count=4 outcome=failure" in caplog.text
        assert "SensAI get_completion_timeline" in caplog.text
        assert "SensAI get_trial_log: trial 2 count=7 level=error" in caplog.text
        assert "SensAI compare_trials: [1, 2]" in caplog.text

    def test_what_the_signal_agent_looked_up_is_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO)

        asyncio.run(
            column_manifest_agent.run(
                "do it",
                model=scripted(
                    call("get_available_signals"),
                    call("get_rotatable_signals"),
                    call("get_quat_signals"),
                    call("final_result"),
                ),
                deps=make_deps(None),
            )
        )

        assert "SensAI get_available_signals" in caplog.text
        assert "SensAI get_rotatable_signals" in caplog.text
        assert "SensAI get_quat_signals" in caplog.text

    def test_the_request_the_chat_agent_hands_a_specialist_is_logged(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        caplog.set_level(logging.INFO)
        app = FastAPI()
        monkeypatch.setattr(sensai_router, "MujocoMojoSettings", _Settings)
        app.include_router(sensai_router.router, prefix="/sensai")
        model = TestChatRoute.router_model(
            [call("ask_plot_config_agent", request="rename"), say("Renamed.")],
            [call("edit_plot_config", changes={"title": "x"}), say("Renamed.")],
        )
        monkeypatch.setattr(sensai_router, "build_fallback_model", lambda: model)

        TestClient(app).post(
            "/sensai/chat",
            json={
                "message": "rename",
                "all_columns": COLUMNS,
                "current_plot_config_json": make_config().model_dump_json(),
            },
        )

        assert 'SensAI ask_plot_config_agent: {"request": "rename"}' in caplog.text

    def test_the_number_of_model_requests_a_message_made_is_logged(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        caplog.set_level(logging.INFO)
        app = FastAPI()
        monkeypatch.setattr(sensai_router, "MujocoMojoSettings", _Settings)
        app.include_router(sensai_router.router, prefix="/sensai")
        model = TestChatRoute.router_model(
            [call("ask_plot_config_agent", request="rename"), say("Renamed.")],
            [call("edit_plot_config", changes={"title": "x"}), say("Renamed.")],
        )
        monkeypatch.setattr(sensai_router, "build_fallback_model", lambda: model)

        TestClient(app).post(
            "/sensai/chat",
            json={
                "message": "rename",
                "all_columns": COLUMNS,
                "current_plot_config_json": make_config().model_dump_json(),
            },
        )

        assert "made 4 model request(s)" in caplog.text


class TestStoppedMessage:
    def test_a_message_with_no_specialist_at_work_says_to_rephrase(self) -> None:
        message = sensai_router._stopped_message(None)

        assert message == (
            f"SensAI stopped after {MAX_MODEL_REQUESTS} model requests without finishing."
            " Try rephrasing your request."
        )

    def test_a_tool_that_is_not_a_specialist_is_treated_as_none_at_work(self) -> None:
        assert sensai_router._stopped_message("something_else") == (
            sensai_router._stopped_message(None)
        )


class TestContextBlock:
    def test_the_plot_is_summarized_not_dumped(self) -> None:
        block = sensai_router._build_context_block(make_deps(make_config()))

        assert f"1 signal(s) plotted: {SIGNAL}" in block
        assert "x-axis time" in block
        assert "legendPos" not in block
        assert "fromUnit" not in block

    def test_a_long_list_of_signals_is_cut_short(self) -> None:
        signals = {f"s{i}": {"color": "#00bc7d"} for i in range(14)}
        config = PlotConfig.model_validate({"yAxes": signals})

        block = sensai_router._build_context_block(make_deps(config))

        assert "14 signal(s) plotted" in block
        assert "s9" in block
        assert "s10" not in block
        assert "and 4 more" in block

    def test_no_plot_is_said_plainly(self) -> None:
        block = sensai_router._build_context_block(make_deps(None))

        assert "Plot config: none loaded" in block

    def test_the_block_is_short(self) -> None:
        assert len(sensai_router._build_context_block(make_deps(make_config()))) < 400
