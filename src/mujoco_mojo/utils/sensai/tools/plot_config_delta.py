"""
Applying a small edit to the trial viewer's plot config, the way SensAI changes the plot.

The agent never retypes the whole config. It sends only what changes, in the shape of a JSON Merge Patch (RFC 7386): an object merges into the config key by key, and anything else, a value or a list, replaces what was there. One difference from the RFC: `null` never deletes anything. Models write `null` for "nothing here", so reading it as a removal wiped signals and reset fields that were meant to stay. `null` is only accepted as a value, for the few fields that allow it (an automatic range, say), and a signal is removed with `remove_plot_signals`. The edit is applied to the current config and the result is checked, so a field the config does not have, a signal the trial does not have, or a value out of range is refused with a message the agent can act on, instead of landing in the plot.
"""

from __future__ import annotations

import difflib
import json
from collections.abc import Collection, Mapping
from typing import Any, get_args

from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from mujoco_mojo.utils.layers.dojo.plot_config import (
    PLOT_COLORS,
    PlotConfig,
    XAxisConfig,
    YAxisConfig,
)

from .plot_config_catalog import find_signals

__all__ = [
    "PlotConfigDeltaError",
    "apply_plot_config_delta",
    "compact_plot_config",
    "remove_plot_signals",
]

_MAX_ERRORS_SHOWN = 5


class PlotConfigDeltaError(ValueError):
    """An edit that cannot be applied, worded for the agent that wrote it so it can correct itself."""


def compact_plot_config(config: PlotConfig) -> dict[str, Any]:
    """
    The config without anything that has its default value, so a prompt carries only what has been set.

    Filters stay whole when there are any, since their `type` is a default value too and the filter would be unreadable without it. A signal always keeps its color, which has no default.
    """
    full = config.model_dump(mode="json")
    default = PlotConfig().model_dump(mode="json")
    compact: dict[str, Any] = {
        key: value
        for key, value in full.items()
        if key not in ("xAxis", "yAxes") and value != default[key]
    }
    x_axis = {
        key: value
        for key, value in full["xAxis"].items()
        if value != default["xAxis"][key]
    }
    if x_axis:
        compact["xAxis"] = x_axis
    signals: dict[str, Any] = {}
    for name, entry in full["yAxes"].items():
        base = YAxisConfig(color=entry["color"]).model_dump(mode="json")
        signals[name] = {
            key: value
            for key, value in entry.items()
            if key == "color" or value != base[key]
        }
    if signals:
        compact["yAxes"] = signals
    return compact


def _accepted_names(model: type[BaseModel]) -> dict[str, str]:
    """Each spelling a model accepts for a field (its name or its camelCase alias) and the alias it is stored under."""
    names: dict[str, str] = {}
    for name, info in model.model_fields.items():
        alias = info.alias or name
        names[name] = alias
        names[alias] = alias
    return names


def _check_keys(
    patch: Mapping[str, Any], model: type[BaseModel], where: str
) -> dict[str, Any]:
    """The patch with every key written as its alias, or an error naming the fields that exist for any key that is not one."""
    accepted = _accepted_names(model)
    aliases = sorted({alias for alias in accepted.values()})
    normalized: dict[str, Any] = {}
    for key, value in patch.items():
        alias = accepted.get(key)
        if alias is None:
            close = difflib.get_close_matches(key, aliases, n=3, cutoff=0.5)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            msg = f'{where} has no field "{key}".{hint} Its fields are: {", ".join(aliases)}.'
            raise PlotConfigDeltaError(msg)
        normalized[alias] = value
    return normalized


def _accepts_none(info: FieldInfo) -> bool:
    """Whether `null` is a real value for the field (an automatic range, no log base) and not just an absence."""
    return type(None) in get_args(info.annotation)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return getattr(value, "value", value)


def _refuse_nulls(
    fields: Mapping[str, Any], model: type[BaseModel], where: str
) -> None:
    """Refuses a `null` for a field that needs a value, since a model writes `null` for "nothing here" and that must never reset what the user set."""
    for alias, value in fields.items():
        if value is not None:
            continue
        info = next(i for n, i in model.model_fields.items() if (i.alias or n) == alias)
        if _accepts_none(info):
            continue
        default = info.get_default(call_default_factory=True)
        instead = (
            "Send a value for it."
            if default is PydanticUndefined
            else f"Send its value, which is {json.dumps(_jsonable(default))} by default."
        )
        raise PlotConfigDeltaError(
            f"{where} cannot be null: null does not leave a field alone or reset it. "
            f"Leave out any field you are not changing. {instead}"
        )


def _next_color(used: Collection[str], signals: int) -> str:
    """The first color of the plot's palette that no signal uses, in the palette's order, as the trial viewer picks one; once every color is used, the palette again from its start, by how many signals there are."""
    taken = {color.lower() for color in used}
    for color in PLOT_COLORS:
        if color not in taken:
            return color
    return PLOT_COLORS[signals % len(PLOT_COLORS)]


def _unknown_signal(name: str, columns: Collection[str], what: str) -> str:
    close = find_signals(columns, name, limit=8)
    hint = f" Closest signals: {', '.join(close)}." if close else ""
    return f'"{name}" is not {what}.{hint} Use find_signals to look a name up.'


def _normalize_patch(
    patch: Mapping[str, Any], config: PlotConfig, columns: Collection[str]
) -> dict[str, Any]:
    """The patch with its keys checked and spelled as aliases, and every signal and column it names checked against the trial."""
    out = _check_keys(patch, PlotConfig, "The plot config")
    if "yAxes" in out and out["yAxes"] is None:
        raise PlotConfigDeltaError(
            "yAxes cannot be null, which would stop plotting every signal. "
            "To stop plotting signals, call remove_signals with their names."
        )
    if "xAxis" in out and out["xAxis"] is None:
        raise PlotConfigDeltaError(
            'xAxis cannot be null. To plot against time again, send {"xAxis": {"col": "time"}}.'
        )
    _refuse_nulls(
        {k: v for k, v in out.items() if k not in ("xAxis", "yAxes")},
        PlotConfig,
        "A plot field",
    )

    x_axis = out.get("xAxis")
    if isinstance(x_axis, Mapping):
        out["xAxis"] = _check_keys(x_axis, XAxisConfig, "xAxis")
        _refuse_nulls(out["xAxis"], XAxisConfig, "An xAxis field")
        col = out["xAxis"].get("col")
        if col is not None and columns and col not in columns:
            raise PlotConfigDeltaError(
                _unknown_signal(str(col), columns, "a column of this trial")
            )
    elif x_axis is not None:
        raise PlotConfigDeltaError('xAxis must be an object such as {"col": "time"}.')

    if "yAxes" in out:
        signals = out["yAxes"]
        if not isinstance(signals, Mapping):
            raise PlotConfigDeltaError(
                "yAxes must be an object keyed by signal name, such as"
                ' {"Bodies/box/xpos:x": {"color": "#ff0000"}}.'
            )
        plotted = config.y_axes
        normalized: dict[str, Any] = {}
        for name, entry in signals.items():
            if entry is None:
                raise PlotConfigDeltaError(
                    f'yAxes["{name}"] cannot be null: null neither adds nor removes a signal. '
                    f'To add "{name}", send an object (an empty one uses the defaults): '
                    f'{{"yAxes": {{"{name}": {{}}}}}}. To stop plotting a signal, call remove_signals.'
                )
            if not isinstance(entry, Mapping):
                raise PlotConfigDeltaError(
                    f'yAxes["{name}"] must be an object of the signal\'s fields, such as {{"color": "#ff0000"}}.'
                )
            if name not in plotted and columns and name not in columns:
                raise PlotConfigDeltaError(
                    _unknown_signal(name, columns, "a signal of this trial")
                )
            fields = _check_keys(entry, YAxisConfig, f'yAxes["{name}"]')
            _refuse_nulls(fields, YAxisConfig, f'yAxes["{name}"] field')
            if name not in plotted and "color" not in fields:
                fields["color"] = _next_color(
                    [y.color for y in plotted.values()]
                    + [
                        str(entry["color"])
                        for entry in normalized.values()
                        if "color" in entry
                    ],
                    len(plotted) + sum(1 for n in normalized if n not in plotted),
                )
            normalized[name] = fields
        out["yAxes"] = normalized
    return out


def _merge_patch(target: Any, patch: Any) -> Any:
    """`target` with `patch` merged in as a JSON Merge Patch, except that a `null` is a value and deletes nothing (the checks above have already refused every `null` that is not one); neither argument is changed."""
    if not isinstance(patch, Mapping):
        return patch
    result: dict[str, Any] = dict(target) if isinstance(target, Mapping) else {}
    for key, value in patch.items():
        result[key] = _merge_patch(result.get(key), value)
    return result


def _describe(exc: ValidationError) -> str:
    lines = [
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    ]
    shown = lines[:_MAX_ERRORS_SHOWN]
    more = f" (and {len(lines) - len(shown)} more)" if len(lines) > len(shown) else ""
    hint = (
        " Call describe_filters for a filter type's fields."
        if any("filters" in line for line in shown)
        else ""
    )
    return "That edit is not valid: " + "; ".join(shown) + more + "." + hint


def apply_plot_config_delta(
    config: PlotConfig, delta: Mapping[str, Any], columns: Collection[str] = ()
) -> PlotConfig:
    """
    The config with the edit `delta` applied. `config` itself is not changed.

    Args:
        config: The current plot config.
        delta: The edit, as a JSON Merge Patch in which `null` is never a removal. Keys may be written as field names or in camelCase.
        columns: The columns of the trial. When there are any, a signal or x-axis column the edit names has to be one of them; when there are none (nothing is known about the trial) names are not checked.

    Raises:
        PlotConfigDeltaError: If a field does not exist, a signal is not in the trial, or the result is not a valid config. The message says what to fix.

    """
    normalized = _normalize_patch(delta, config, columns)
    merged = _merge_patch(config.model_dump(mode="json"), normalized)
    try:
        return PlotConfig.model_validate(merged)
    except ValidationError as exc:
        raise PlotConfigDeltaError(_describe(exc)) from exc


def remove_plot_signals(config: PlotConfig, names: Collection[str]) -> PlotConfig:
    """
    The config without the signals named. `config` itself is not changed.

    Raises:
        PlotConfigDeltaError: If no name is given, or a name is not plotted. The message lists what is plotted.

    """
    plotted = config.y_axes
    wanted = list(dict.fromkeys(names))
    if not wanted:
        raise PlotConfigDeltaError("Name at least one signal to remove.")
    missing = [name for name in wanted if name not in plotted]
    if missing:
        raise PlotConfigDeltaError(
            f"Not plotted, so there is nothing to remove: {', '.join(missing)}. "
            f"Plotted signals: {', '.join(plotted) or 'none'}."
        )
    data = config.model_dump(mode="json")
    for name in wanted:
        del data["yAxes"][name]
    return PlotConfig.model_validate(data)
