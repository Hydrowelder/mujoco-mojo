"""SensAI domain agent for the trial viewer plot - full CRUD over saved plot config profiles."""

from __future__ import annotations

import json

from pydantic import ValidationError
from pydantic_ai import (  # pyright: ignore[reportMissingImports]
    Agent,
    ModelRetry,
    RunContext,
)

from mujoco_mojo.utils.layers.dojo.plot_config import (
    PlotConfig,
)
from mujoco_mojo.utils.layers.dojo.routers.mosaic import (
    _get_profiles_dir,
    _parse_profile,
    _resolve_profile_path,
)

from .deps import SensAIDeps

_SYSTEM_PROMPT = """\
You are the plot-config agent inside the MuJoCo Mojo Dojo dashboard. You manage the trial \
viewer's plot configuration: reading it, editing it, and saving/loading/deleting it as \
named profiles, using your tools.

When asked to change the plot, look up its current state first, then finish by outputting \
the complete modified config - every field from the original, with only the requested \
change applied. Use the exact field names and values already there. Never invent field \
names, never drop fields you weren't asked to change, never leave placeholder values. \
Execute immediately; never ask for confirmation.

When just answering a question rather than editing, finish with the exact config a tool \
already gave you - don't retype it from memory. If there's nothing loaded to describe, \
edit, or act on, finish with null.
"""

plot_config_agent: Agent[SensAIDeps, PlotConfig | None] = Agent(
    deps_type=SensAIDeps,
    output_type=PlotConfig | None,
    system_prompt=_SYSTEM_PROMPT,
)


@plot_config_agent.tool
async def get_current_plot_config(ctx: RunContext[SensAIDeps]) -> str:
    """Returns the full trial viewer plot configuration as JSON. Call this before proposing any config update."""
    if ctx.deps.current_plot_config is None:
        return "No plot config is currently loaded."
    return ctx.deps.current_plot_config.model_dump_json(indent=2)


@plot_config_agent.tool
async def get_plotted_signals(ctx: RunContext[SensAIDeps]) -> list[str]:
    """Returns the y-axis signal column names currently displayed in the trial viewer plot."""
    config = ctx.deps.current_plot_config
    if config is None:
        return []
    return list(config.y_axes.keys())


@plot_config_agent.tool
async def get_x_axis_signal(ctx: RunContext[SensAIDeps]) -> str:
    """Returns the column name used as the x-axis in the trial viewer plot."""
    config = ctx.deps.current_plot_config
    if config is None:
        return "No plot config is currently loaded."
    return config.x_axis.col if config.x_axis else "time"


@plot_config_agent.tool_plain
def list_saved_plot_configs() -> list[str]:
    """
    List the names of every saved plot config profile.

    Returns:
        Every saved profile's name (including sub-folder paths, e.g. 'robotics/baseline'), most recently modified first.

    """
    d = _get_profiles_dir()
    return [
        f.relative_to(d).with_suffix("").as_posix()
        for f in sorted(
            d.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )
    ]


@plot_config_agent.tool_plain
def load_plot_config(name: str) -> PlotConfig:
    """
    Load a previously saved plot config profile by name.

    Args:
        name: The profile name to load, e.g. 'robotics/baseline'.

    Returns:
        The profile's active tab's plot config.

    Raises:
        ModelRetry: If no profile with this name exists, so the caller can retry with a corrected name.

    """
    path = _resolve_profile_path(name)
    if not path.exists():
        raise ModelRetry(f"No saved profile named {name!r} found.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        profile = _parse_profile(data, name)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ModelRetry(
            f"Profile {name!r} failed validation and cannot be loaded: {exc}"
        ) from exc
    return profile.tabs[profile.active_tab_index].config
