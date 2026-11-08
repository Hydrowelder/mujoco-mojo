"""
What the plot-config agent needs to know to edit a plot config: a short list of its fields, a signal search, and a filter reference.

The whole JSON schema of the config is far heavier than the agent needs, since it lists every filter type in full. The field list here has one line per field, built from the models' own descriptions so it cannot drift from them. Filters are looked up on demand, since there are dozens and most edits touch none.
"""

from __future__ import annotations

import difflib
import json
import re
from collections.abc import Collection
from enum import Enum
from typing import Any, get_args

from pydantic import BaseModel
from pydantic_core import PydanticUndefined, to_jsonable_python

from mujoco_mojo.utils.layers.dojo.plot_config import (
    PlotConfig,
    XAxisConfig,
    YAxisConfig,
)

__all__ = ["filter_catalog", "find_signals", "plot_config_catalog"]

_MAX_SIGNAL_MATCHES = 25

# a field with more choices than this lists the first few and an ellipsis, since a value that is not one of them is refused with the full list
_MAX_CHOICES_SHOWN = 8

# the top-level fields that get their own section rather than a line each
_STRUCTURED_FIELDS = frozenset({"x_axis", "y_axes"})


def find_signals(
    columns: Collection[str], query: str, limit: int = _MAX_SIGNAL_MATCHES
) -> list[str]:
    """
    The columns that match `query`, so a signal can be named exactly without listing every column.

    A column matches when it contains every word of the query (case is ignored, and spaces, `/`, `:`, `_`, `.` and `-` separate words), shortest first. When nothing matches, the closest spellings are returned instead.
    """
    words = [w for w in re.split(r"[\s/:_.\-]+", query.lower()) if w]
    if not words:
        return []
    hits = sorted(
        (c for c in columns if all(w in c.lower() for w in words)),
        key=lambda c: (len(c), c),
    )
    if hits:
        return hits[:limit]
    return difflib.get_close_matches(query, list(columns), n=min(limit, 10), cutoff=0.4)


def _enum_type(annotation: Any) -> type[Enum] | None:
    """The enum a field's annotation is made of, looking through `Optional` and `Annotated`."""
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation
    for arg in get_args(annotation):
        found = _enum_type(arg)
        if found is not None:
            return found
    return None


def _first_sentence(text: str) -> str:
    """The text up to the end of its first sentence, which is a full stop followed by a capital letter (so an `e.g.` does not end it) or by nothing."""
    text = text.strip()
    end = re.search(r"[.!?](?:(?=\s+[A-Z])|$)", text)
    return text[: end.start()] if end else text


def _field_line(model: type[BaseModel], name: str) -> str:
    info = model.model_fields[name]
    alias = info.alias or name
    enum = _enum_type(info.annotation)
    default = info.get_default(call_default_factory=True)
    notes: list[str] = []
    if enum is not None:
        choices = [str(member.value) for member in enum]
        if len(choices) > _MAX_CHOICES_SHOWN:
            choices = [*choices[:_MAX_CHOICES_SHOWN], "..."]
        notes.append("|".join(choices))
    if default is not PydanticUndefined and info.default_factory is None:
        notes.append(f"default {json.dumps(to_jsonable_python(default))}")
    suffix = f" ({', '.join(notes)})" if notes else ""
    description = _first_sentence(info.description or "")
    return f"- {alias}{suffix}: {description}"


def plot_config_catalog() -> str:
    """One line per editable field of the plot config, its x-axis and each signal, for the plot agent's prompt."""
    plot_fields = [n for n in PlotConfig.model_fields if n not in _STRUCTURED_FIELDS]
    lines = ["Plot-wide fields (change them with edit_plot_config):"]
    lines += [_field_line(PlotConfig, n) for n in plot_fields]
    lines += [
        "",
        'xAxis (an object, also changed with edit_plot_config, such as {"xAxis": {"col": "time"}}):',
    ]
    lines += [_field_line(XAxisConfig, n) for n in XAxisConfig.model_fields]
    lines += [
        "",
        "Signal fields (every plotted signal has these; change one signal's with edit_signal, and add or remove signals with add_signals and remove_signals):",
    ]
    lines += [_field_line(YAxisConfig, n) for n in YAxisConfig.model_fields]
    return "\n".join(lines)


def _param_text(param: dict[str, Any]) -> str:
    text = f"{param['name']} ({param['type']}"
    if param.get("default") is not None:
        text += f", default {json.dumps(param['default'])}"
    return text + ")"


def filter_catalog(schema: list[dict[str, Any]], type_name: str | None = None) -> str:
    """
    The filter types a signal or the x-axis can be given, from the filter schema the filter editor uses.

    Without `type_name` it is one line per type (name and what it does). With one, it is that type's parameters, how to write the filter entry, and nothing else.
    """
    if type_name is None:
        return "\n".join(f"- {f['type']}: {f['description']}" for f in schema)
    by_type = {f["type"]: f for f in schema}
    found = by_type.get(type_name)
    if found is None:
        close = difflib.get_close_matches(type_name, list(by_type), n=5, cutoff=0.4)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        return f'There is no filter type "{type_name}".{hint} Call describe_filters with no type to list them.'
    params = ", ".join(_param_text(p) for p in found["params"]) or "none"
    args = "".join(f', "{p["name"]}": ...' for p in found["params"])
    example = f'{{"type": "{found["type"]}"{args}}}'
    return (
        f"{found['type']}: {found['description']}\n"
        f"Parameters: {params}\n"
        f"Write it as {example}. Filters are an ordered list under a signal's `filters` or under `xAxis`, and a list you send replaces the whole list."
    )
