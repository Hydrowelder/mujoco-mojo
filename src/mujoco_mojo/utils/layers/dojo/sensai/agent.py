"""SensAI - Pydantic AI agent for the MuJoCo Mojo Dojo dashboard."""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models import Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from mujoco_mojo.settings import SensAISettings
from mujoco_mojo.utils.dataframe import ColumnManifest
from mujoco_mojo.utils.layers.dojo.plot_config import PlotConfig
from mujoco_mojo.utils.statusing import JobStatus

if TYPE_CHECKING:
    from mujoco_mojo.utils.statusing import StepStatus, TrialStatus

# ---------------------------------------------------------------------------
# deps - runtime context injected into the agent and its tools
# ---------------------------------------------------------------------------


@dataclass
class SensAIDeps:
    """Runtime context available to the SensAI agent and all its tools."""

    job_status: JobStatus | None
    """The current job, or None if no job is loaded."""

    column_manifest: ColumnManifest
    """Signal column names available in the current trial's telemetry data."""

    current_plot_config: PlotConfig | None
    """The plot config currently active in the trial viewer, or None if not set."""


# ---------------------------------------------------------------------------
# result types
# ---------------------------------------------------------------------------


class SensAIChatResult(BaseModel):
    """Output from the chat agent — conversational reply plus optional change intent."""

    message: str
    """The conversational reply to display in the chat panel."""

    plot_change_request: str | None = None
    """Plain-English description of the plot change to apply, or None."""


# ---------------------------------------------------------------------------
# agents
# ---------------------------------------------------------------------------

_CHAT_SYSTEM_PROMPT = """\
You are SensAI, an AI assistant inside the MuJoCo Mojo Dojo dashboard.
You help users understand simulation job status and configure trial viewer plots.

Each user message begins with a [Current dashboard state] block. \
It contains the live job status and the full plot config JSON. \
Use that data directly — do not call tools for information already in the state block.

TOOLS — only call these when the state block does not have what you need:
- get_job_summary / get_trial_breakdown / get_trial_details → detailed job or per-trial data
- get_available_signals / get_rotatable_signals / get_quat_signals → available signal column names

PLOT MODIFICATION:
When the user asks you to change the plot, set plot_change_request to a precise plain-English \
description of the change using the exact field names and values from the current config. \
A separate agent will apply the actual JSON edit — you do not produce any JSON yourself. \
Execute immediately; never ask for confirmation.

Good plot_change_request examples:
- "set yAxes['Lab/box_acc:y'].color to '#ef4444'"
- "set xAxis.col to 'Lab/time'"
- "set grid to 'all'"
- "remove the yAxes entry for 'Lab/box_acc:z'"

If no plot change is needed, set plot_change_request to null.

OUTPUT FORMAT — respond with exactly this JSON object and nothing else:
{"message": "<your reply>", "plot_change_request": "<description>" or null}

RULES:
- The outer response must be a single JSON object. No code fences around it, no text outside it.
- message may use markdown (bold, lists). Keep it to 1-3 sentences. Be direct and specific.
- Do NOT put JSON configs or code blocks in message.
- Never ask "shall I proceed?" — execute immediately.
- Never use JSON comments or placeholder values like "...".

Good: {"message": "Changed the :y line to red.", "plot_change_request": "set yAxes['Lab/box_acc:y'].color to '#ef4444'"}
Bad:  {"message": "I will now update the color. Shall I proceed?", "plot_change_request": null}
"""

_PLOT_SYSTEM_PROMPT = """\
You are a JSON transformation tool. You receive a current plot configuration as JSON and a \
plain-English description of a change to apply.

Output ONLY the complete modified configuration as valid JSON. \
No explanation, no markdown, no code fences, no text before or after the JSON object.
"""

# chat agent — handles conversation, tool calls, and change intent detection
sensai_agent: Agent[SensAIDeps, SensAIChatResult] = Agent(
    deps_type=SensAIDeps,
    output_type=SensAIChatResult,
    system_prompt=_CHAT_SYSTEM_PROMPT,
    retries={"output": 0},
)

# plot agent — pure JSON transformer, no tools, no deps
plot_agent: Agent[None, str] = Agent(
    output_type=str,
    system_prompt=_PLOT_SYSTEM_PROMPT,
    retries={"output": 0},
)


# ---------------------------------------------------------------------------
# model wrapper — normalizes local model output before pydantic-ai validates
# ---------------------------------------------------------------------------


def _strip_json_comments(s: str) -> str:
    """Strip // line and /* block */ comments, respecting string literals."""
    result: list[str] = []
    i = 0
    n = len(s)
    in_string = False
    escape_next = False
    while i < n:
        c = s[i]
        if escape_next:
            result.append(c)
            escape_next = False
            i += 1
            continue
        if c == "\\" and in_string:
            result.append(c)
            escape_next = True
            i += 1
            continue
        if c == '"':
            in_string = not in_string
            result.append(c)
            i += 1
            continue
        if not in_string and c == "/" and i + 1 < n:
            if s[i + 1] == "/":
                while i < n and s[i] != "\n":
                    i += 1
                continue
            if s[i + 1] == "*":
                i += 2
                while i < n - 1 and not (s[i] == "*" and s[i + 1] == "/"):
                    i += 1
                i += 2
                continue
        result.append(c)
        i += 1
    return "".join(result)


def _normalize_text_output(text: str) -> str:
    """
    Coerce a local model's raw text into a JSON string matching SensAIChatResult.

    Handles, in order:
    - markdown code fences wrapping a JSON object
    - JSON comments (// and /* */)
    - prose with an embedded JSON object (extracts the outermost {...})
    - missing required fields (patched with safe defaults)
    - pure prose with no valid JSON (wrapped as a message with null plot_change_request)
    """
    text = text.strip()

    # strip markdown fences only when they wrap a JSON object
    if text.startswith("```"):
        candidate = re.sub(r"^```[a-z]*\n?", "", text)
        candidate = re.sub(r"\n?```\s*$", "", candidate).strip()
        if candidate.lstrip().startswith("{"):
            text = candidate

    text = _strip_json_comments(text).strip()

    start = text.find("{")
    if start != -1:
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            if depth == 0:
                candidate = _strip_json_comments(text[start : i + 1]).strip()
                try:
                    data = json.loads(candidate)
                    if isinstance(data, dict):
                        data.setdefault("message", "")
                        pcr = data.get("plot_change_request")
                        if not isinstance(pcr, (str, type(None))):
                            pcr = None
                        data["plot_change_request"] = pcr
                        return json.dumps(data)
                except (json.JSONDecodeError, ValueError):
                    pass
                break

    # fallback: model output labeled markdown instead of JSON
    # e.g. "**plot_change_request:** set yAxes[...].color to '#ef4444'"
    pcr_match = re.search(
        r"(?i)(?:^|\n)\s*\*{0,2}plot[_\s-]change[_\s-]request\*{0,2}\s*:?\s*(.+?)(?:\n|$)",
        text,
    )
    if pcr_match:
        pcr: str | None = pcr_match.group(1).strip() or None
        msg = text[: pcr_match.start()].strip()
        # strip **Message:** label if the model added one
        msg = re.sub(r"(?i)^\s*\*{0,2}message\*{0,2}\s*:?\s*", "", msg).strip()
        return json.dumps({"message": msg or text.strip(), "plot_change_request": pcr})

    return json.dumps({"message": text, "plot_change_request": None})


def _normalize_plot_output(text: str) -> str:
    """Extract the first valid JSON object from a local model's plot config response."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text).strip()
    text = _strip_json_comments(text).strip()
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    end = start
    for i, c in enumerate(text[start:], start):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if depth == 0:
            end = i
            break
    return _strip_json_comments(text[start : end + 1]).strip()


class _LocalModelWrapper(Model[Any]):
    """
    Wraps any pydantic-ai Model and normalizes TextPart responses from local models
    before pydantic-ai validates them as structured output.
    """

    _provider = None  # type: ignore[assignment]

    def __init__(
        self,
        inner: Model[Any],
        normalize: Callable[[str], str] = _normalize_text_output,
    ) -> None:
        self._inner = inner
        self._normalize = normalize

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def system(self) -> str:
        return self._inner.system

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        response = await self._inner.request(
            messages, model_settings, model_request_parameters
        )
        cleaned = [
            dataclasses.replace(p, content=self._normalize(p.content))
            if isinstance(p, TextPart)
            else p
            for p in response.parts
        ]
        return dataclasses.replace(response, parts=cleaned)

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: Any = None,
    ) -> AsyncIterator[StreamedResponse]:
        async with self._inner.request_stream(
            messages, model_settings, model_request_parameters, run_context
        ) as stream:
            yield stream

    async def __aenter__(self) -> _LocalModelWrapper:
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool | None:
        return await self._inner.__aexit__(exc_type, exc_val, exc_tb)


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------


@sensai_agent.tool
async def get_job_summary(ctx: RunContext[SensAIDeps]) -> str:
    """Returns a high-level summary of the current job's status and progress."""
    job = ctx.deps.job_status
    if job is None:
        return "No job is currently loaded."

    lines = [
        f"Job type: {job.job_type}",
        f"Started by: {job.started_by}",
        f"Execution mode: {job.execution_mode}",
        f"Total trials: {job.n_trial}",
        f"Completed: {job.n_done} ({job.n_success} succeeded, {job.n_failed} failed)",
        f"Remaining: {job.n_remaining}",
        f"Progress: {job.progress:.1%}",
        f"Progress bar: {job.progress_bar}",
        f"Elapsed: {job.elapsed}",
        f"Average trial duration: {job.average_trial_duration}",
        f"Estimated time remaining: {job.time_remaining_average_success}",
        f"Complete: {job.is_done}",
    ]
    if job.n_done > 0:
        lines.append(f"Success rate: {job.success_rate:.1%}")
        lines.append(f"Failure rate: {job.failure_rate:.1%}")

    return "\n".join(lines)


@sensai_agent.tool
async def get_trial_breakdown(ctx: RunContext[SensAIDeps]) -> str:
    """Returns per-trial completion status. Use this when the user asks about specific trials."""
    job = ctx.deps.job_status
    if job is None:
        return "No job is currently loaded."

    success = job.success_trial_nums
    failed = job.failed_trial_nums
    pending = job.pending_trial_nums

    lines = [
        f"Succeeded ({len(success)}): {success[:50]}{'...' if len(success) > 50 else ''}",
        f"Failed ({len(failed)}): {failed[:50]}{'...' if len(failed) > 50 else ''}",
        f"Pending ({len(pending)}): {pending[:50]}{'...' if len(pending) > 50 else ''}",
    ]
    return "\n".join(lines)


@sensai_agent.tool
async def get_trial_details(ctx: RunContext[SensAIDeps], trial_num: int) -> str:
    """Returns step-level timing details for a specific trial number. Use this when the user asks about a particular trial."""
    job = ctx.deps.job_status
    if job is None:
        return "No job is currently loaded."

    status: TrialStatus | None = job.get_trial_status(trial_num)
    if status is None:
        return f"Trial {trial_num} not found in cache (may still be pending)."

    def _fmt(step_name: str, step: StepStatus) -> str:
        if step.elapsed is not None:
            return f"  {step_name}: {step.elapsed:.3f}s"
        if step.started is not None:
            return f"  {step_name}: in progress"
        return f"  {step_name}: not started"

    lines = [
        f"Trial {trial_num}:",
        f"  Completion: {status.completion}",
        f"  Current step: {status.step}",
        _fmt("pending", status.pending),
        _fmt("generating", status.generating),
        _fmt("solving", status.solving),
        f"  Total elapsed: {status.td}",
    ]
    return "\n".join(lines)


@sensai_agent.tool
async def get_available_signals(ctx: RunContext[SensAIDeps]) -> list[str]:
    """Returns the list of signal column names available in the current trial's telemetry data."""
    return ctx.deps.column_manifest["all"]


@sensai_agent.tool
async def get_rotatable_signals(ctx: RunContext[SensAIDeps]) -> list[str]:
    """Returns the list of signal column names which can be rotated by get_available_quats."""
    return ctx.deps.column_manifest["rotatable_vectors"]


@sensai_agent.tool
async def get_quat_signals(ctx: RunContext[SensAIDeps]) -> list[str]:
    """Returns the list of signal column names which can be used to rotate get_rotatable_signals."""
    return ctx.deps.column_manifest["available_quats"]


@sensai_agent.tool
async def get_plotted_signals(ctx: RunContext[SensAIDeps]) -> list[str]:
    """Returns the y-axis signal column names currently displayed in the trial viewer plot."""
    config = ctx.deps.current_plot_config
    if config is None:
        return []
    return list(config.y_axes.keys())


@sensai_agent.tool
async def get_x_axis_signal(ctx: RunContext[SensAIDeps]) -> str:
    """Returns the column name used as the x-axis in the trial viewer plot."""
    config = ctx.deps.current_plot_config
    if config is None:
        return "No plot config is currently loaded."
    return config.x_axis.col if config.x_axis else "time"


@sensai_agent.tool
async def get_current_plot_config(ctx: RunContext[SensAIDeps]) -> str:
    """Returns the full trial viewer plot configuration as JSON. Call this before proposing any config update."""
    if ctx.deps.current_plot_config is None:
        return "No plot config is currently loaded."
    return ctx.deps.current_plot_config.model_dump_json(indent=2)


# ---------------------------------------------------------------------------
# model factory
# ---------------------------------------------------------------------------


def _make_openai_model(config: SensAISettings) -> OpenAIChatModel:
    return OpenAIChatModel(
        config.model_name,
        provider=OpenAIProvider(
            base_url=config.base_url,
            api_key=config.api_key.get_secret_value(),
        ),
    )


def build_model(config: SensAISettings) -> _LocalModelWrapper:
    """Chat model wrapped to normalize text output from local models."""
    return _LocalModelWrapper(_make_openai_model(config))


def build_plot_model(config: SensAISettings) -> _LocalModelWrapper:
    """Plot model wrapped to extract a bare JSON object from local model text output."""
    return _LocalModelWrapper(
        _make_openai_model(config), normalize=_normalize_plot_output
    )
