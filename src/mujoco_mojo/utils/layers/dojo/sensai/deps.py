"""Runtime context shared by the SensAI chat agent and its domain agents."""

from __future__ import annotations

from dataclasses import dataclass

from mujoco_mojo.settings import DEFAULT_MAX_REQUESTS, DEFAULT_MAX_VERSUS_TRIALS
from mujoco_mojo.utils.dataframe import ColumnManifest
from mujoco_mojo.utils.layers.dojo.plot_config import PlotConfig, VersusState
from mujoco_mojo.utils.statusing import JobStatus

from .tool_trace import ToolTrace


@dataclass
class SensAIDeps:
    """Runtime context available to the SensAI chat agent and every domain agent it delegates to."""

    job_status: JobStatus | None
    """The current job, or None if no job is loaded."""

    column_manifest: ColumnManifest
    """Signal column names available in the current trial's telemetry data."""

    current_plot_config: PlotConfig | None
    """The plot config currently active in the trial viewer, or None if not set."""

    plot_edit_refusal: str | None = None
    """Why the plot agent's latest edit or profile load was refused, or None if it was not. When the model keeps repeating a refused call until it runs out of tries, the chat agent tells the user this instead of the turn failing."""

    trace: ToolTrace | None = None
    """Where the tool calls of this message are recorded for the chat to show, or None when nothing is watching. The chat agent hands it to each specialist's run, which is how a specialist's own tool calls are seen."""

    versus: VersusState | None = None
    """Versus mode as the trial viewer has it, or None when the message did not come from a trial viewer. `set_versus` replaces it, and the router sends the browser the new one if it differs."""

    versus_trials_added: int = 0
    """Trials this message has added to versus mode so far, which `max_versus_trials` is checked against."""

    max_requests: int = DEFAULT_MAX_REQUESTS
    """`dojo.sensai.max_requests`. The specialists' runs are given it too, since they share the message's count."""

    max_versus_trials: int = DEFAULT_MAX_VERSUS_TRIALS
    """`dojo.sensai.max_versus_trials`."""
