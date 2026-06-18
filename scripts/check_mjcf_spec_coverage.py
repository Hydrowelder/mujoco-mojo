"""
One-off script that cross-references the MJCF XML reference against the XMLModel
subclasses implemented in mujoco_mojo. By default it fetches the latest reference
directly from the MuJoCo docs; pass a local path to check against a specific copy
instead (e.g. a pinned XMLreference.rst.txt).

For every MJCF element it reports:
- whether mujoco_mojo implements a class for it (matched by `tag`)
- attributes documented in the spec but not covered by any matching class's
  `attributes`/`non_xml_fields` (likely a missed field)
- a docstring similarity score, to flag descriptions that may have drifted from the spec

This is advisory, not a hard gate: false positives are expected (the spec groups
several distinct elements, e.g. body/joint vs tendon/fixed/joint, under the same bare
tag name) and docstrings are deliberately reworded in places, so review the output
rather than treating it as pass/fail.

Usage:
    python scripts/check_mjcf_spec_coverage.py                       # fetch the spec live
    python scripts/check_mjcf_spec_coverage.py path/to/XMLreference.rst.txt  # use a local copy
"""

from __future__ import annotations

import inspect
import re
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import requests
from rich.console import Console
from rich.markup import escape

SPEC_URL = "https://mujoco.readthedocs.io/en/stable/_sources/XMLreference.rst.txt"

# soft_wrap avoids breaking long file-path lines mid-string, which would make
# them harder to click through to from a terminal or IDE
console = Console(soft_wrap=True)

HEADER_RE = re.compile(
    r"^(?:\:el-prefix:`(?P<prefix>\w+)/`\s*\|-\|\s*)?\*\*(?P<name>.+?)\*\*\s*\|[!@?*-]\|\s*$"
)
ANCHOR_RE = re.compile(r"^\.\. _[\w-]+:\s*$")
# plain RST subsection titles (e.g. "collision sensors") use the same `^^^^`/`~~~~` underline
# convention as real element headers but don't match HEADER_RE; without detecting them, `current`
# stays pinned to whatever element preceded them, and any shared `:at:` blocks inside get
# misattributed to that element instead of being ignored
GENERIC_UNDERLINE_RE = re.compile(r"^[\^~]{3,}\s*$")
ATTR_LINE_RE = re.compile(r"^:at:`(?P<rest>.+)`\s*(?::\s*:at-val:`.*`)?\s*$")
# only match names immediately preceded by the `:at:` role marker, so prose lines that
# happen to start with `:at:`something`` but reference other roles later (e.g. `:el:`general``)
# don't get misread as also declaring an attribute named "general"
AT_NAME_RE = re.compile(r":at:`(\w+)`")
RST_NOISE_RE = re.compile(
    r":(?:ref|el|at|at-val|el-prefix|math):`[^`]*`|``|\|br\||\.\. .*"
)

# attribute names that get merged into a single python field via PoseBase/OrientationBase: `pose`
# (position + orientation) on most elements, or a bare `orientation` field where pos is separate
# (e.g. Inertial, which has its own `pos` field alongside `orientation`)
ORIENTATION_GROUP = {"pos", "quat", "axisangle", "xyaxes", "zaxis", "euler"}
ORIENTATION_COVERING_FIELDS = {"pose", "orientation"}


@dataclass
class SpecElement:
    name: str
    description: str = ""
    attrs: dict[str, str] = field(default_factory=dict)


def _clean(text: str) -> str:
    text = RST_NOISE_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _expand_names(raw_name: str) -> list[str]:
    m = re.match(r"\((\w+)\)(\w+)$", raw_name)
    if m:
        return [m.group(2), m.group(1) + m.group(2)]
    return [raw_name]


def parse_spec(text: str) -> list[SpecElement]:
    lines = text.splitlines()
    elements: list[SpecElement] = []
    # a header can expand to more than one name (e.g. "(world)body" -> "body" and
    # "worldbody"); every name in the group shares the same attrs/description, since
    # they're documenting the same element under different aliases
    current_group: list[SpecElement] = []
    pending_attr_names: list[str] = []
    buffer: list[str] = []

    def flush_attr() -> None:
        if current_group and pending_attr_names:
            desc = _clean(" ".join(buffer))
            for el in current_group:
                for name in pending_attr_names:
                    el.attrs[name] = desc

    def flush_description() -> None:
        # first non-empty buffer wins; later prose between attribute blocks (e.g. trailing
        # notes before the next anchor) shouldn't clobber the element's intro description
        if current_group and not pending_attr_names and buffer:
            desc = _clean(" ".join(buffer))
            for el in current_group:
                if not el.description:
                    el.description = desc

    i = 0
    while i < len(lines):
        line = lines[i]
        header = HEADER_RE.match(line)
        if header:
            flush_attr()
            flush_description()
            pending_attr_names = []
            buffer = []

            current_group = []
            for name in _expand_names(header.group("name")):
                el = SpecElement(name=name)
                elements.append(el)
                current_group.append(el)
            i += 1
            continue

        if (
            line.strip()
            and i + 1 < len(lines)
            and GENERIC_UNDERLINE_RE.match(lines[i + 1])
            and not ANCHOR_RE.match(line)
            and not ATTR_LINE_RE.match(line)
        ):
            flush_attr()
            flush_description()
            current_group = []
            pending_attr_names = []
            buffer = []
            i += 2
            continue

        if ANCHOR_RE.match(line):
            flush_attr()
            flush_description()
            pending_attr_names = []
            buffer = []
            i += 1
            continue

        attr_match = ATTR_LINE_RE.match(line)
        if attr_match:
            flush_attr()
            # only look for `name` tokens before ":at-val:" so type/default values
            # (e.g. :at-val:`string`) aren't mistaken for additional attribute names
            name_part = line.split(":at-val:")[0]
            pending_attr_names = AT_NAME_RE.findall(name_part)
            buffer = []
            i += 1
            continue

        buffer.append(line)
        i += 1

    flush_attr()
    flush_description()
    # keep every real header match, even ones with zero attributes of their own (e.g.
    # pure container elements like <actuator>/<asset>, or elements like actuator/motor
    # whose attributes are documented by reference under a shared element instead of
    # being restated) -- dropping them caused them to be falsely reported as unimplemented
    return elements


def merge_by_bare_name(elements: list[SpecElement]) -> dict[str, SpecElement]:
    merged: dict[str, SpecElement] = {}
    for el in elements:
        bucket = merged.setdefault(el.name, SpecElement(name=el.name))
        bucket.attrs.update(el.attrs)
        if not bucket.description:
            bucket.description = el.description
    return merged


def normalize_field_name(name: str) -> str:
    if name.endswith("_") and len(name) > 1:
        return name[:-1]
    return name


def collect_xml_model_classes():
    import mujoco_mojo  # noqa: F401
    from mujoco_mojo.mjcf.xml_model import XMLModel

    seen: set[type] = set()
    stack = [XMLModel]
    classes: list[type] = []
    while stack:
        cls = stack.pop()
        for sub in cls.__subclasses__():
            if sub not in seen:
                seen.add(sub)
                classes.append(sub)
                stack.append(sub)
    return classes


def _class_location(cls: type) -> str:
    try:
        file = inspect.getsourcefile(cls)
        _, line = inspect.getsourcelines(cls)
    except (OSError, TypeError):
        return "<unknown location>"
    if not file:
        return "<unknown location>"
    # show a path relative to the cwd when the file is underneath it, so the
    # output stays clickable/short when run from within the repo
    path = Path(file)
    try:
        path = path.relative_to(Path.cwd())
    except ValueError:
        pass
    return f"{path}:{line}"


def build_python_registry() -> dict[str, dict]:
    registry: dict[str, dict] = {}
    for cls in collect_xml_model_classes():
        tag = getattr(cls, "tag", "")
        if not tag:
            continue
        bucket = registry.setdefault(
            tag, {"classes": [], "covered": set(), "docstrings": []}
        )
        bucket["classes"].append((cls.__name__, _class_location(cls)))
        names = {
            normalize_field_name(n) for n in (*cls.attributes, *cls.non_xml_fields)
        }
        bucket["covered"] |= names
        if cls.__doc__:
            bucket["docstrings"].append(cls.__doc__)
    return registry


def _print_classes(classes: list[tuple[str, str]]) -> None:
    for name, location in classes:
        console.print(
            f"      [bold cyan]{escape(name)}[/bold cyan] [dim]{escape(location)}[/dim]"
        )


def main() -> None:
    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        response = requests.get(SPEC_URL)
        response.raise_for_status()
        text = response.text

    spec_elements = parse_spec(text)
    spec_by_name = merge_by_bare_name(spec_elements)
    python_registry = build_python_registry()

    spec_names = set(spec_by_name)
    python_tags = set(python_registry)

    unimplemented = sorted(spec_names - python_tags)
    untagged = sorted(python_tags - spec_names)

    console.rule(
        f"[bold]Spec elements with no matching implemented tag[/bold] ({len(unimplemented)})"
    )
    for name in unimplemented:
        console.print(f"  [yellow]{escape(name)}[/yellow]")

    console.print()
    console.rule(
        f"[bold]Implemented tags with no matching spec element[/bold] ({len(untagged)})"
    )
    for name in untagged:
        console.print(f"  [yellow]{escape(name)}[/yellow]:")
        _print_classes(python_registry[name]["classes"])

    console.print()
    console.rule(
        "[bold]Attribute coverage gaps[/bold] (spec attributes not covered by attributes/non_xml_fields)"
    )
    for name in sorted(spec_names & python_tags):
        spec_el = spec_by_name[name]
        covered = python_registry[name]["covered"]
        missing = set()
        for attr in spec_el.attrs:
            if attr in covered:
                continue
            if attr in ORIENTATION_GROUP and covered & ORIENTATION_COVERING_FIELDS:
                continue
            missing.add(attr)
        if missing:
            console.print(
                f"  [red]{escape(name)}[/red]: missing [bold yellow]{escape(str(sorted(missing)))}[/bold yellow]"
            )
            _print_classes(python_registry[name]["classes"])

    console.print()
    console.rule(
        "[bold]Docstring similarity warnings[/bold] (ratio < 0.2, review for drift)"
    )
    for name in sorted(spec_names & python_tags):
        spec_desc = spec_by_name[name].description
        py_desc = _clean(" ".join(python_registry[name]["docstrings"]))
        if not spec_desc or not py_desc:
            continue
        ratio = SequenceMatcher(None, spec_desc, py_desc).ratio()
        if ratio < 0.2:
            console.print(
                f"  [magenta]{escape(name)}[/magenta]: similarity=[bold]{ratio:.2f}[/bold]"
            )
            _print_classes(python_registry[name]["classes"])


if __name__ == "__main__":
    main()
