"""
What the plot-config agent needs to know to edit a plot config: a short list of its fields, a signal search, and a filter reference.

The whole JSON schema of the config is far heavier than the agent needs, since it lists every filter type in full. The field list here has one line per field, built from the models' own descriptions so it cannot drift from them. Filters are looked up on demand, since there are dozens and most edits touch none.
"""

from __future__ import annotations

import difflib
import json
import re
from collections.abc import Collection, Mapping
from enum import Enum
from functools import lru_cache
from typing import Any, get_args

from pydantic import BaseModel
from pydantic_core import PydanticUndefined, to_jsonable_python

from mujoco_mojo.utils.layers.dojo.plot_config import (
    PlotConfig,
    XAxisConfig,
    YAxisConfig,
)
from mujoco_mojo.utils.signal_metadata import ColumnMetadata

__all__ = ["filter_catalog", "find_signals", "plot_config_catalog"]

_MAX_SIGNAL_MATCHES = 25

# a field with more choices than this lists the first few and an ellipsis, since a value that is not one of them is refused with the full list
_MAX_CHOICES_SHOWN = 8

# the top-level fields that get their own section rather than a line each
_STRUCTURED_FIELDS = frozenset({"x_axis", "y_axes"})


_TEXT_WORDS = re.compile(r"[a-z0-9]+")


@lru_cache(maxsize=65536)
def _words(text: str) -> tuple[str, ...]:
    """The lowercase words of `text`, the start of which a search of a signal's metadata matches. Cached, since the same text is searched on every query."""
    words: list[str] = _TEXT_WORDS.findall(text.lower())
    return tuple(words)


def _metadata_text(meta: ColumnMetadata) -> str:
    """What a signal's metadata says about it, which `find_signals` searches: its description, quantity and unit."""
    return " ".join(p for p in (meta.description, meta.quantity, meta.unit) if p)


def find_signals(
    columns: Collection[str],
    query: str,
    limit: int = _MAX_SIGNAL_MATCHES,
    metadata: Mapping[str, ColumnMetadata] | None = None,
) -> list[str]:
    """
    The columns that match `query`, so a signal can be named exactly without listing every column.

    A column matches when every word of the query (case is ignored, and spaces, `/`, `:`, `_`, `.` and `-` separate words) is in its name or, where `metadata` has some for it, is the start of a word of its description, quantity or unit. That way `box1 angular velocity` finds `Bodies/box1/xvelr:y`, and `veloc` finds a `velocity`, while `y` does not find every description with a `y` somewhere in it. The columns with the most of the words in their name come first, then the shortest. When nothing matches, the closest spellings of the name are returned instead.
    """
    words = [w for w in re.split(r"[\s/:_.\-]+", query.lower()) if w]
    if not words:
        return []
    described = metadata or {}
    ranked: list[tuple[int, int, str]] = []
    for column in columns:
        name = column.lower()
        in_name = sum(w in name for w in words)
        if in_name < len(words):
            meta = described.get(column)
            known = _words(_metadata_text(meta)) if meta else ()
            if not all(w in name or any(t.startswith(w) for t in known) for w in words):
                continue
        ranked.append((-in_name, len(column), column))
    if ranked:
        ranked.sort()
        return [column for _, _, column in ranked[:limit]]
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
