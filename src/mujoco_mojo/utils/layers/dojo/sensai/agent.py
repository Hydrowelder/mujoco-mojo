"""SensAI - Pydantic AI agent for the MuJoCo Mojo Dojo dashboard."""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import AsyncIterator
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
# result - structured output returned by every agent run
# ---------------------------------------------------------------------------


class SensAIResult(BaseModel):
    """Structured response from the SensAI agent."""

    message: str
    """The conversational reply to display in the chat panel."""

    plot_config_update: PlotConfig | None = None
    """A proposed replacement plot configuration. `None` if no change is suggested."""


# ---------------------------------------------------------------------------
# agent
# ---------------------------------------------------------------------------

_BASE_SYSTEM_PROMPT = """\
You are SensAI, an AI assistant inside the MuJoCo Mojo Dojo dashboard.
You help users understand simulation job status and configure trial viewer plots.

Each user message begins with a [Current dashboard state] block. \
It contains the live job status and the full plot config JSON. \
Use that data directly — do not call tools for information already in the state block.

TOOLS — only call these when the state block does not have what you need:
- get_job_summary / get_trial_breakdown / get_trial_details → detailed job or per-trial data
- get_available_signals / get_rotatable_signals / get_quat_signals → available signal column names

PLOT MODIFICATION — critical rules:
1. When the user asks you to change the plot, do it immediately. Never ask for confirmation.
2. The ONLY way to modify the plot is to populate `plot_config_update`. \
Writing JSON or config details in `message` does absolutely nothing — the plot will not change.
3. Copy the "Full plot config" JSON from the state block verbatim, apply only the requested \
changes, and return the complete modified object in `plot_config_update`. \
Do not omit any fields. Do not invent field names.

OUTPUT FORMAT — respond with exactly this JSON object and nothing else:
{"message": "<your reply>", "plot_config_update": <full modified PlotConfig or null>}

RULES:
- The outer response must be a single JSON object. No code fences around it, no text outside it.
- `message` may use markdown (bold, lists). Keep it to 1-3 sentences. Be direct and specific.
- Do NOT put JSON or config dumps inside `message` — that is what `plot_config_update` is for.
- `plot_config_update` must be the complete config object when making a change, or null otherwise.
- Never ask "shall I proceed?" or "would you like me to?". Execute the request directly.
- Never use JSON comments or placeholder values like "...".

Good example: {"message": "Changed the :y line color to red.", "plot_config_update": {<full config>}}
Bad example:  {"message": "I will now update the color. Shall I proceed?", "plot_config_update": null}
"""

sensai_agent: Agent[SensAIDeps, SensAIResult] = Agent(
    deps_type=SensAIDeps,
    output_type=SensAIResult,
    system_prompt=_BASE_SYSTEM_PROMPT,
    # local models produce worse output on retry (they fixate on the error message);
    # _LocalModelWrapper normalizes responses so retries are rarely needed anyway
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
    Coerce a local model's raw text into a JSON string that SensAIResult can validate.

    Handles, in order:
    - markdown code fences
    - JSON comments (// and /* */)
    - prose with an embedded JSON object (extract and parse the outermost {...})
    - missing required SensAIResult fields (patched with safe defaults)
    - pure prose with no valid JSON (wrapped as {"message": text, "plot_config_update": null})
    """
    text = text.strip()

    # strip markdown fences only when they wrap a JSON object — if the model
    # responded with a code block as part of its markdown content (not as a
    # JSON wrapper), stripping the opening fence corrupts the output
    if text.startswith("```"):
        candidate = re.sub(r"^```[a-z]*\n?", "", text)
        candidate = re.sub(r"\n?```\s*$", "", candidate).strip()
        if candidate.lstrip().startswith("{"):
            text = candidate

    # strip JSON comments
    text = _strip_json_comments(text).strip()

    # find the first top-level { ... } block by brace-matching, then try to parse it
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
                        # patch missing required fields rather than letting pydantic fail
                        data.setdefault("message", "")
                        pcu = data.get("plot_config_update")
                        if isinstance(pcu, dict):
                            # discard malformed plot configs rather than letting pydantic fail
                            try:
                                PlotConfig.model_validate(pcu)
                            except Exception:
                                pcu = None
                        elif not isinstance(pcu, type(None)):
                            pcu = None
                        data["plot_config_update"] = pcu
                        return json.dumps(data)
                except (json.JSONDecodeError, ValueError):
                    pass
                break  # found closing brace but JSON is invalid — fall through

    # no valid JSON found — wrap the prose as the message
    return json.dumps({"message": text, "plot_config_update": None})


class _LocalModelWrapper(Model[Any]):
    """
    Wraps any pydantic-ai Model and normalizes TextPart responses from local models
    before pydantic-ai validates them as structured output.
    """

    _provider = None  # type: ignore[assignment]

    def __init__(self, inner: Model[Any]) -> None:
        self._inner = inner

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
            dataclasses.replace(p, content=_normalize_text_output(p.content))
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


def build_model(config: SensAISettings) -> _LocalModelWrapper:
    """Construct a model pointed at the configured endpoint, wrapped to strip JSON comments."""
    inner = OpenAIChatModel(
        config.model_name,
        provider=OpenAIProvider(
            base_url=config.base_url,
            api_key=config.api_key.get_secret_value(),
        ),
    )
    return _LocalModelWrapper(inner)
