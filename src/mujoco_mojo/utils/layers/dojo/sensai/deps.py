"""Runtime context shared by the SensAI chat agent and its domain agents."""

from __future__ import annotations

from dataclasses import dataclass

from mujoco_mojo.utils.dataframe import ColumnManifest
from mujoco_mojo.utils.layers.dojo.plot_config import PlotConfig
from mujoco_mojo.utils.statusing import JobStatus


@dataclass
class SensAIDeps:
    """Runtime context available to the SensAI chat agent and every domain agent it delegates to."""

    job_status: JobStatus | None
    """The current job, or None if no job is loaded."""

    column_manifest: ColumnManifest
    """Signal column names available in the current trial's telemetry data."""

    current_plot_config: PlotConfig | None
    """The plot config currently active in the trial viewer, or None if not set."""
