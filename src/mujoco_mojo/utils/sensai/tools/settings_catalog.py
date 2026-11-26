"""
The settings of MuJoCo Mojo as SensAI's docs agent reads them: one entry for each setting, in words.

The settings are described only on their fields, each with a title, a description, a default and sometimes a list of choices, which is also what the settings panel shows. This reads them off the settings schema instead of from a page that would have to be kept in step with the code. A setting is found by the section or key prefix it sits under (`reloaded`, `reloaded.keys`), or by words in its key, label or description.

A secret setting is listed too, marked as one the settings panel does not show: a schema carries a field's description and default, never the value it holds, and the panel's omission is exactly why a user may need to be told the setting exists.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Sequence
from functools import cache
from typing import Any

from pydantic import BaseModel, Field

from mujoco_mojo.settings import GenerateJsonSchemaWithDefaults, MujocoMojoSettings

from .docs_catalog import STOP_WORDS, docs_url

__all__ = [
    "Setting",
    "read_from",
    "read_settings",
    "settings",
    "settings_from_schema",
]

_WORD = re.compile(r"[a-z0-9]+")
_SKIPPED_WORDS = STOP_WORDS | {
    "set",
    "setting",
    "settings",
    "change",
    "turn",
    "use",
    "off",
    "enable",
    "disable",
}
_DEFAULT_SUFFIX = re.compile(r"\n\nDefault: .*\Z", re.DOTALL)

# a word in a setting's key or label says more about it than one in its description
_KEY_WEIGHT = 3
# a hit has to score at least this share of the best one, which leaves out the settings that only share a word most of them have (`dojo`)
_KEEP_SHARE = 0.4
_MAX_HITS = 8
_READ_LIMIT = 7000

_HOW_TO_CHANGE = (
    "Change a setting in the [settings panel]({link}) (the gear in the Dojo's toolbar), "
    "with `mujoco-mojo settings set KEY VALUE`, or in `~/.mujoco-mojo/settings.toml`. "
    "A project's `.mujoco-mojo/settings.toml` takes priority over the global file."
)


class Setting(BaseModel):
    """One setting, as its key, the label the settings panel gives it, the values it takes, its default and what it does."""

    key: str
    """The dotted key, such as `dojo.chime_enabled`."""
    label: str
    """The name the settings panel shows for it."""
    kind: str
    """The values it takes, in words."""
    default: str
    description: str
    choices: dict[str, str] = Field(default_factory=dict)
    """What each value means, for a setting that takes one of a few."""
    secret: bool = False
    """Whether it holds a secret, which the settings panel does not show."""

    @property
    def section(self) -> str:
        """The first part of the key, which is the section of the settings panel it is in."""
        return self.key.split(".", 1)[0]

    def text(self) -> str:
        """The setting written out for the agent to read."""
        lines = [
            self.key,
            f"  panel label: {self.label}",
            f"  value: {self.kind}; default {self.default}",
        ]
        if self.secret:
            lines.append(
                "  the settings panel does not show this one, because it holds a secret"
            )
        lines.append(f"  {self.description}")
        lines += [f"  `{value}`: {meaning}" for value, meaning in self.choices.items()]
        return "\n".join(lines)


def _resolve(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    """The node with its `$ref` filled in from `$defs`, keeping what the node itself says (its title, description and default) over what the definition says."""
    ref = node.get("$ref")
    if not isinstance(ref, str):
        return node
    own = {key: value for key, value in node.items() if key != "$ref"}
    return {**defs.get(ref.split("/")[-1], {}), **own}


def _is_secret(prop: dict[str, Any]) -> bool:
    """Whether the setting holds a secret, which a schema marks `writeOnly`, on the setting itself or on the type it is one of (`SecretStr | None`)."""
    options = prop.get("anyOf", [])
    return bool(prop.get("writeOnly")) or any(
        option.get("writeOnly") for option in options
    )


def _kind(prop: dict[str, Any]) -> str:
    """The values a setting takes, in words."""
    if "enum" in prop:
        return "one of " + ", ".join(f"`{value}`" for value in prop["enum"])
    if prop.get("x-widget") == "color":
        return "a color"
    options = prop.get("anyOf")
    if options:
        kinds = [_kind(option) for option in options if option.get("type") != "null"]
        text = " or ".join(dict.fromkeys(kinds))
        unset = any(option.get("type") == "null" for option in options)
        return f"{text}, or unset" if unset else text
    match prop.get("type"):
        case "boolean":
            return "true or false"
        case "integer" | "number" as number:
            noun = "a whole number" if number == "integer" else "a number"
            low, high = prop.get("minimum"), prop.get("maximum")
            if low is not None and high is not None:
                return f"{noun} from {low} to {high}"
            if low is not None:
                return f"{noun} of at least {low}"
            if high is not None:
                return f"{noun} of at most {high}"
            return noun
        case "string":
            return "text"
        case "array":
            return "a list"
        case "object":
            return "a table of key = value pairs"
        case _:
            return "a value"


def _default(prop: dict[str, Any]) -> str:
    """A setting's default in words."""
    if "default" not in prop:
        return "none"
    value = prop["default"]
    if value is None:
        return "unset"
    if isinstance(value, str):
        return f"`{value}`" if value else "empty"
    if value == []:
        return "an empty list"
    return f"`{json.dumps(value)}`"


def _leaves(
    node: dict[str, Any], defs: dict[str, Any], prefix: str = ""
) -> list[Setting]:
    """Every setting under `node`, walking into the nested groups."""
    found: list[Setting] = []
    for name, raw in node.get("properties", {}).items():
        prop = _resolve(raw, defs)
        if "properties" in prop:
            found += _leaves(prop, defs, f"{prefix}{name}.")
            continue
        descriptions = prop.get("x-enum-descriptions", {})
        found.append(
            Setting(
                key=f"{prefix}{name}",
                label=str(prop.get("title", name)),
                kind=_kind(prop),
                default=_default(prop),
                description=" ".join(
                    _DEFAULT_SUFFIX.sub("", str(prop.get("description", ""))).split()
                ),
                choices={
                    str(value): str(descriptions[value])
                    for value in prop.get("enum", [])
                    if value in descriptions
                },
                secret=_is_secret(prop),
            )
        )
    return found


def settings_from_schema(schema: dict[str, Any]) -> tuple[Setting, ...]:
    """The settings a JSON Schema of the settings describes, in the order the schema lists them."""
    defs = schema.get("$defs", {})
    return tuple(_leaves(_resolve(schema, defs), defs))


@cache
def settings() -> tuple[Setting, ...]:
    """Every setting of this install."""
    return settings_from_schema(
        MujocoMojoSettings.model_json_schema(
            schema_generator=GenerateJsonSchemaWithDefaults
        )
    )


def _groups(found: Sequence[Setting]) -> Counter[str]:
    """How many settings are in each section, and in each group inside one (`reloaded` and `reloaded.keys`)."""
    counts: Counter[str] = Counter()
    for setting in found:
        parts = setting.key.split(".")
        for end in range(1, len(parts)):
            counts[".".join(parts[:end])] += 1
    return counts


def _outline(found: Sequence[Setting]) -> str:
    """The sections and groups to ask for."""
    lines = [
        f"- `{name}` ({count} settings)"
        for name, count in sorted(_groups(found).items())
    ]
    return "The settings are in these sections:\n" + "\n".join(lines)


def _under(found: Sequence[Setting], name: str) -> list[Setting]:
    """The settings whose key is `name` or starts with it as a section."""
    return [s for s in found if s.key == name or s.key.startswith(f"{name}.")]


def _matching(found: Sequence[Setting], query: str) -> list[Setting]:
    """The settings that best match some words, best first. A word that few settings have counts for more than one that most have."""
    words = [
        word
        for word in _WORD.findall(query.lower())
        if len(word) > 2 and word not in _SKIPPED_WORDS
    ]
    named = {s.key: f"{s.key} {s.label}".lower() for s in found}
    described = {s.key: s.description.lower() for s in found}
    weight = {
        word: math.log(
            1
            + len(found)
            / max(1, sum(word in named[k] or word in described[k] for k in named))
        )
        for word in words
    }
    scored: list[tuple[float, Setting]] = []
    for setting in found:
        score = sum(
            weight[word]
            * (
                (_KEY_WEIGHT if word in named[setting.key] else 0)
                + (1 if word in described[setting.key] else 0)
            )
            for word in words
        )
        if score:
            scored.append((score, setting))
    scored.sort(key=lambda item: -item[0])
    if not scored:
        return []
    best = scored[0][0]
    return [s for score, s in scored[:_MAX_HITS] if score >= _KEEP_SHARE * best]


def _written(found: Sequence[Setting]) -> str:
    """The settings written out, cut short with a note when they are more than fit."""
    text = "\n\n".join(setting.text() for setting in found)
    if len(text) <= _READ_LIMIT:
        return text
    kept = text[:_READ_LIMIT]
    kept = kept[: kept.rfind("\n\n")]
    shown = kept.count("\n\n") + 1
    return f"{kept}\n\n(cut after {shown} of {len(found)} settings: ask for a smaller section, such as `reloaded.keys`)"


def read_from(found: Sequence[Setting], section: str = "") -> str:
    """What `read_settings` answers for the settings in `found`."""
    link = f"{docs_url('user-guides/features/dojo/dojo.md')}#settings"
    how = _HOW_TO_CHANGE.format(link=link)
    query = section.strip().strip("`.").lower()
    if not query:
        return f"{_outline(found)}\n\n{how}"
    hits = _under(found, query) or _matching(found, section)
    if not hits:
        return f"No setting matches that. {_outline(found)}"
    return f"{_written(hits)}\n\n{how}"


def read_settings(section: str = "") -> str:
    """The settings of this install, written out: all of a section (`reloaded`, `reloaded.keys`), or the ones that match some words. With no section, the list of sections."""
    return read_from(settings(), section)
