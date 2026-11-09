"""SensAI domain agent for the trial viewer plot: reads the plot config, changes it with small edits, and loads saved profiles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError
from pydantic_ai import Agent, ModelRetry, RunContext

from mujoco_mojo.utils.layers.dojo.plot_config import PLOT_COLORS, PlotConfig
from mujoco_mojo.utils.layers.dojo.routers.mosaic import (
    _get_profiles_dir,
    _parse_profile,
    _resolve_profile_path,
    get_filter_schema,
)

from mujoco_mojo.utils.log import get_logger

from .deps import SensAIDeps
from .job_report import trials_that_missed
from .plot_config_catalog import filter_catalog, plot_config_catalog
from .plot_config_catalog import find_signals as _find_signals
from .plot_config_delta import (
    PlotConfigDeltaError,
    apply_plot_config_delta,
    compact_plot_config,
    remove_plot_signals,
)
from .versus import VersusError, change_versus, describe_versus

logger = get_logger(__name__)

_PALETTE = ", ".join(PLOT_COLORS)
_EXAMPLE_COLOR = PLOT_COLORS[-1]

_INSTRUCTIONS = f"""\
You are the plot-config agent inside the MuJoCo Mojo Dojo dashboard. You change the trial \
viewer's plot with small, exact tool calls, and you change only what the user asked for.

The plot as it is right now is given below, after these instructions, and is kept up to date \
after every call, so there is no need to look it up. It lists only the values that differ \
from the defaults; every other field has its default, shown in the field lists below.

Your tools, each with an example call:
- add_signals: plot more signals; the ones already plotted stay. \
add_signals(names=["Bodies/box2/xvelr:y"])
- remove_signals: stop plotting signals. remove_signals(names=["Bodies/box2/xvelr:y"])
- edit_signal: change how one plotted signal is drawn. \
edit_signal(name="Bodies/box1/xvelr:y", changes={{"color": "{_EXAMPLE_COLOR}", "width": 4}})
- edit_plot_config: change plot-wide fields, never signals. \
edit_plot_config(changes={{"title": "Wheel speed", "grid": "none", "rangeX": [0, 5]}})
- find_signals: look up exact signal names from words. find_signals(query="box2 xvelr")
- describe_filters: how to write a filter. Call it before adding or changing a filter.
- set_versus: versus mode, which draws other trials behind this one. Pinning trials, setting a \
range or naming a requirement turns it on. \
set_versus(failed_requirement="touchdown_speed") shows the trials that missed that requirement \
("any" for trials that missed any requirement, "error" for trials that crashed). \
set_versus(trial_range=[3, 9]). set_versus(pin=[12, 15]). set_versus(enabled=false) turns it off.

Rules:
- A signal name must be exact: a column name of this trial. To plot "the same" signal for \
another body or site, take the name of a signal that is already plotted and swap the body \
name (Bodies/box1/xvelr:y becomes Bodies/box2/xvelr:y), then call add_signals. A name that \
is not in the trial is refused with the closest real ones. When you do not know a name, \
call find_signals. Never shorten, guess or invent one.
- Colors come from the plot's palette, in this order: {_PALETTE}. A new signal takes the \
first palette color no signal uses, automatically, so do not send a color for one unless \
the user asked for it. When the user names a color, send the palette color closest to it, \
never the pure web color (for cyan, the palette's cyan, not #00ffff). Send another hex only \
when the user gives one or no palette color is near what they asked for.
- Send only what changes. Never send null, except null for rangeX or rangeY to make a range \
automatic again.
- Versus mode draws its range and its pinned trials together. To compare only some trials, such \
as only the ones that failed a requirement, also send no_range=true. To show other trials \
instead of the ones shown now, also send clear_pins=true. Never write out trial numbers you \
looked up: failed_requirement finds them. When set_versus says trials were left out, tell the \
user how many and that asking again adds the next batch.
- If the request is a question, answer it and call no tool that changes the plot.
- Execute immediately; never ask for confirmation. If a call is refused, read the reason, \
fix that and call again. Never repeat a call that was refused.
- Finish with one or two sentences saying what you changed or found.
"""

_SYSTEM_PROMPT = _INSTRUCTIONS + "\n" + plot_config_catalog()


def _refusal(ctx: RunContext[SensAIDeps], reason: str) -> ModelRetry:
    """The retry that sends `reason` back to the model, with the reason kept in the deps so the user can be told it if the model runs out of tries."""
    ctx.deps.plot_edit_refusal = reason
    return ModelRetry(reason)


def _commit(ctx: RunContext[SensAIDeps], before: PlotConfig, after: PlotConfig) -> str:
    """Makes `after` the plot and says which fields of it differ from `before`."""
    if after == before:
        return "Nothing changed: the plot already has those values."
    was = before.model_dump(mode="json")
    now = after.model_dump(mode="json")
    changed = [key for key in now if now[key] != was[key]]
    ctx.deps.current_plot_config = after
    return f"Done. Changed: {', '.join(changed)}."


def _edit(
    ctx: RunContext[SensAIDeps],
    tool: str,
    config: PlotConfig,
    changes: Mapping[str, Any],
) -> str:
    """Applies `changes` to `config` as the plot. A refusal goes back to the model as a retry with its reason, so it can send the corrected call."""
    logger.info("SensAI %s: %s", tool, json.dumps(changes, default=str)[:500])
    try:
        edited = apply_plot_config_delta(
            config, changes, ctx.deps.column_manifest["all"]
        )
    except PlotConfigDeltaError as exc:
        logger.info("SensAI %s refused: %s", tool, exc)
        raise _refusal(ctx, str(exc)) from exc
    ctx.deps.plot_edit_refusal = None
    return _commit(ctx, config, edited)


plot_config_agent: Agent[SensAIDeps, str] = Agent(
    deps_type=SensAIDeps,
    output_type=str,
    system_prompt=_SYSTEM_PROMPT,
)


@plot_config_agent.instructions
async def current_plot(ctx: RunContext[SensAIDeps]) -> str:
    """The plot as it is now, as JSON with every default value left out, so it is short. It is built for every request to the model, so it already shows an edit made a moment ago."""
    config = ctx.deps.current_plot_config
    if config is None:
        return "No plot config is currently loaded."
    return "The plot right now:\n" + json.dumps(compact_plot_config(config))


@plot_config_agent.tool
async def find_signals(ctx: RunContext[SensAIDeps], query: str) -> list[str] | str:
    """
    Searches the names of this trial's signals, so a signal can be named exactly.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        query: Words from the name, such as 'box1 xpos'. Case and separators (spaces, `/`, `:`, `_`) do not matter.

    Returns:
        Up to 25 exact signal names containing every word, shortest first; the closest spellings if none contain them all.

    """
    columns = ctx.deps.column_manifest["all"]
    if not columns:
        return "No signal list is available, so signal names cannot be checked."
    found = _find_signals(columns, query)
    logger.info("SensAI find_signals %r: %d match(es)", query, len(found))
    return found


@plot_config_agent.tool(retries=3)
async def add_signals(ctx: RunContext[SensAIDeps], names: list[str]) -> str:
    """
    Plots more signals, each in an automatic color. The signals already plotted stay plotted.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        names: The exact names of the signals to plot, such as ["Bodies/box2/xvelr:y"]. One that is not a signal of this trial is refused, with the closest real names.

    Returns:
        Which parts of the plot changed.

    """
    config = ctx.deps.current_plot_config
    if config is None:
        return "No plot config is currently loaded, so nothing was changed."
    wanted = list(dict.fromkeys(names))
    if not wanted:
        raise _refusal(ctx, "Name at least one signal to add.")
    return _edit(ctx, "add_signals", config, {"yAxes": {name: {} for name in wanted}})


@plot_config_agent.tool(retries=3)
async def edit_signal(
    ctx: RunContext[SensAIDeps], name: str, changes: dict[str, Any]
) -> str:
    """
    Changes how one plotted signal is drawn. Whatever you leave out of `changes` stays as it is.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        name: The exact name of a signal that is plotted now, such as "Bodies/box1/xvelr:y". To plot one that is not, call add_signals first.
        changes: Only the signal's fields to change, such as {"color": "#ff2056", "width": 4} or {"label": "spin", "dash": "dot"}. The fields are listed under "Signal fields". A color is one from the palette in your instructions. Never null.

    Returns:
        Which parts of the plot changed.

    """
    config = ctx.deps.current_plot_config
    if config is None:
        return "No plot config is currently loaded, so nothing was changed."
    if name not in config.y_axes:
        plotted = ", ".join(config.y_axes) or "none"
        raise _refusal(
            ctx,
            f'"{name}" is not plotted, so there is nothing to edit. Plotted signals: '
            f"{plotted}. To plot it, call add_signals.",
        )
    return _edit(ctx, "edit_signal", config, {"yAxes": {name: changes}})


@plot_config_agent.tool(retries=3)
async def edit_plot_config(ctx: RunContext[SensAIDeps], changes: dict[str, Any]) -> str:
    """
    Changes plot-wide fields such as the title, grid, axis ranges, legend or x-axis column. Whatever you leave out stays as it is. To add, remove or restyle signals use add_signals, remove_signals and edit_signal instead.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        changes: Only the fields to change, such as {"title": "Wheel speed", "grid": "none", "rangeX": [0, 5]} or {"xAxis": {"col": "time"}}. The fields are listed under "Plot-wide fields". Never null, except null for rangeX or rangeY to make a range automatic. A field that does not exist or a value that is not allowed is refused with the reason.

    Returns:
        Which parts of the plot changed.

    """
    config = ctx.deps.current_plot_config
    if config is None:
        return "No plot config is currently loaded, so nothing was changed."
    return _edit(ctx, "edit_plot_config", config, changes)


@plot_config_agent.tool(retries=3)
async def remove_signals(ctx: RunContext[SensAIDeps], names: list[str]) -> str:
    """
    Stops plotting signals. The signals that are not named stay plotted.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        names: The exact names of the plotted signals to stop plotting, such as ["Bodies/box2/xvelr:y"].

    Returns:
        Which parts of the plot changed.

    """
    config = ctx.deps.current_plot_config
    if config is None:
        return "No plot config is currently loaded, so nothing was changed."
    logger.info("SensAI remove_signals: %s", names)
    try:
        edited = remove_plot_signals(config, names)
    except PlotConfigDeltaError as exc:
        logger.info("SensAI remove_signals refused: %s", exc)
        raise _refusal(ctx, str(exc)) from exc
    ctx.deps.plot_edit_refusal = None
    return _commit(ctx, config, edited)


@plot_config_agent.instructions
async def current_versus(ctx: RunContext[SensAIDeps]) -> str | None:
    """Versus mode as it is now, rebuilt for every request so it shows a change made a moment ago. Nothing when there is no trial viewer to change it."""
    if ctx.deps.versus is None:
        return None
    job = ctx.deps.job_status
    return describe_versus(
        ctx.deps.versus, list(job.trial_nums) if job is not None else None
    )


@plot_config_agent.tool(retries=3)
async def set_versus(
    ctx: RunContext[SensAIDeps],
    enabled: bool | None = None,
    trial_range: list[int] | None = None,
    no_range: bool = False,
    pin: list[int] | None = None,
    unpin: list[int] | None = None,
    failed_requirement: str | None = None,
    clear_pins: bool = False,
) -> str:
    """
    Changes versus mode, which draws other trials' traces behind the open trial's. What you leave out stays as it is, and pinned trials are added to the ones pinned already.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        enabled: True to show the comparison traces and false to turn versus mode off, such as true. Leave it out to keep it as it is: pinning trials or setting a range turns it on by itself.
        trial_range: The first and last trial number to compare, such as [3, 9]. It replaces the range from before. Leave it out to keep the range.
        no_range: True to compare only the pinned trials, with no range, such as true. Use it with pin or failed_requirement when the user wants only those trials.
        pin: Trial numbers the user named, to add to the pinned ones, such as [12, 15]. For the trials that failed a requirement use failed_requirement and never write those numbers yourself.
        unpin: Trial numbers to stop comparing, such as [12].
        failed_requirement: Pins the trials that missed a requirement, found by the server. A requirement's name or part of it, such as "touchdown_speed", or "any" for the trials that missed any requirement, or "error" for the trials that crashed.
        clear_pins: True to drop every pinned trial first, such as true, when the user wants other trials instead of the ones shown now.

    Returns:
        What versus mode is set to now, and how many trials were left out if there were too many to add in one message.

    """
    state = ctx.deps.versus
    if state is None:
        return "Versus mode cannot be changed now: no trial is open in the trial viewer. Tell the user to open a trial and ask again."
    logger.info(
        "SensAI set_versus: %s",
        json.dumps(
            {
                "enabled": enabled,
                "trial_range": trial_range,
                "no_range": no_range,
                "pin": pin,
                "unpin": unpin,
                "failed_requirement": failed_requirement,
                "clear_pins": clear_pins,
            },
            default=str,
        )[:500],
    )
    job = ctx.deps.job_status
    known = list(job.trial_nums) if job is not None else None
    pins = list(pin or [])
    if failed_requirement:
        if job is None:
            return "No job is loaded, so there are no failed trials to look up. Pin the trial numbers the user names instead."
        found = trials_that_missed(job, failed_requirement)
        if isinstance(found, str):
            return found
        if not found and not (
            enabled is not None
            or trial_range is not None
            or no_range
            or pin
            or unpin
            or clear_pins
        ):
            return (
                f"No trial missed '{failed_requirement}', so there is nothing to show."
            )
        pins += found
    room = max(0, ctx.deps.max_versus_trials - ctx.deps.versus_trials_added)
    try:
        change = change_versus(
            state,
            room=room,
            known=known,
            enabled=enabled,
            trial_range=trial_range,
            no_range=no_range,
            pin=pins,
            unpin=unpin or [],
            clear_pins=clear_pins,
        )
    except VersusError as exc:
        logger.info("SensAI set_versus refused: %s", exc)
        raise _refusal(ctx, str(exc)) from exc
    ctx.deps.plot_edit_refusal = None
    ctx.deps.versus = change.state
    ctx.deps.versus_trials_added += change.added
    if change.state == state:
        text = "Nothing changed: versus mode already has those values."
    else:
        text = f"Done. {describe_versus(change.state, known)}"
    if change.left_out:
        text += (
            f" {change.left_out} more trial{'s were' if change.left_out != 1 else ' was'} not added: "
            f"one message adds at most {ctx.deps.max_versus_trials} comparison trials "
            "(dojo.sensai.max_versus_trials in settings). Tell the user how many were left out "
            "and that asking again adds the next batch."
        )
    return text


@plot_config_agent.tool
async def describe_filters(
    ctx: RunContext[SensAIDeps], filter_type: str | None = None
) -> str:
    """
    Describes the filters a signal or the x-axis can have.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        filter_type: One filter type from the list, to get its parameters and how to write it. Leave it out to list every type.

    Returns:
        The list of filter types, or the one type's parameters.

    """
    return filter_catalog(await get_filter_schema(), filter_type)


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


@plot_config_agent.tool
async def load_plot_config(ctx: RunContext[SensAIDeps], name: str) -> str:
    """
    Load a previously saved plot config profile by name, replacing the plot with it.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        name: The profile name to load, e.g. 'robotics/baseline'.

    Returns:
        What was loaded.

    Raises:
        ModelRetry: If no profile with this name exists, so the caller can retry with a corrected name.

    """
    path = _resolve_profile_path(name)
    if not path.exists():
        raise _refusal(ctx, f"No saved profile named {name!r} found.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        profile = _parse_profile(data, name)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise _refusal(
            ctx, f"Profile {name!r} failed validation and cannot be loaded: {exc}"
        ) from exc
    config = profile.tabs[profile.active_tab_index].config
    ctx.deps.plot_edit_refusal = None
    ctx.deps.current_plot_config = config
    return f"Loaded {name!r}: it plots {len(config.y_axes)} signal(s)."
