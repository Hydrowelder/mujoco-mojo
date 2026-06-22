"""
One-off script that cross-references the MJCF XML reference against the XMLModel
subclasses implemented in mujoco_mojo. By default it fetches the latest reference
directly from the MuJoCo docs; pass a local path to check against a specific copy
instead (e.g. a pinned XMLreference.rst.txt).

For every MJCF element it reports:
- whether mujoco_mojo implements a class for it (matched by `tag`)
- attributes documented in the spec but not covered by any matching class's
  `attributes`/`non_xml_fields` (likely a missed field)
- attributes whose spec default doesn't match the Python field's default value
- attributes with no per-field docstring, or one that has drifted from the spec
- a class-level docstring similarity score, to flag descriptions that may have
  drifted from the spec

This is advisory, not a hard gate: false positives are expected (the spec groups
several distinct elements, e.g. body/joint vs tendon/fixed/joint, under the same bare
tag name) and docstrings are deliberately reworded in places, so review the output
rather than treating it as pass/fail.

Reviewed, accepted findings can be silenced by adding them to `mjcf_ignore.txt`
(next to this script) -- see that file's header for the format. This only applies to
the "Spec elements with no matching implemented tag", "Implemented tags with no
matching spec element", "Attribute coverage gaps", "Default value mismatches", and
"Docstring similarity warnings" sections; "Attribute docstring warnings" always shows
everything, since per-field docstrings are easy to add and shouldn't be silenced.

Usage:
    python scripts/check_mjcf_spec_coverage.py                       # fetch the spec live
    python scripts/check_mjcf_spec_coverage.py path/to/XMLreference.rst.txt  # use a local copy
"""

from __future__ import annotations

import ast
import functools
import inspect
import math
import re
import sys
import textwrap
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal, get_args, get_origin

import requests
from pydantic_core import PydanticUndefined
from rich.console import Console
from rich.markup import escape

SPEC_URL = "https://mujoco.readthedocs.io/en/stable/_sources/XMLreference.rst.txt"

IGNORE_FILE = Path(__file__).with_name("mjcf_ignore.txt")

# below this difflib ratio, a description is flagged as likely drifted from the spec
DOCSTRING_SIMILARITY_THRESHOLD = 0.2

# what's left of a spec attribute description after `_clean` strips a bare
# `:ref:`Something`` cross-reference with no other content (e.g. most sensors'
# shared name/noise/cutoff/... attributes just say "See CSensor."); comparing this
# placeholder against a real python docstring would always read as drift, so it's
# treated the same as having no spec description to compare against
SPEC_DESC_PLACEHOLDER = "See ."

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
class SpecAttr:
    description: str = ""
    # raw text trailing the first top-level comma in the `:at-val:` body, e.g.
    # '"0 0 1"', "optional", "required", or unparsed prose for the rare multi-clause cases
    default_raw: str = ""


@dataclass
class SpecElement:
    name: str
    description: str = ""
    attrs: dict[str, SpecAttr] = field(default_factory=dict)


def _clean(text: str) -> str:
    text = RST_NOISE_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _expand_names(raw_name: str) -> list[str]:
    m = re.match(r"\((\w+)\)(\w+)$", raw_name)
    if m:
        return [m.group(2), m.group(1) + m.group(2)]
    return [raw_name]


def _parse_attr_default(val_text: str) -> str:
    """
    Splits an `:at-val:` body like `[false, true], "false"` or `real(3), "0 0 0"` into
    its trailing default-value text, by finding the first top-level comma (ignoring
    commas nested inside the type spec's brackets/parens, e.g. `[false, true]`).

    Returns "" if no top-level comma is found (e.g. shared `:at:` lines whose `:at-val:`
    is empty or absent).
    """
    depth = 0
    for i, ch in enumerate(val_text):
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        elif ch == "," and depth == 0:
            return val_text[i + 1 :].strip()
    return ""


def parse_spec(text: str) -> list[SpecElement]:
    lines = text.splitlines()
    elements: list[SpecElement] = []
    # a header can expand to more than one name (e.g. "(world)body" -> "body" and
    # "worldbody"); every name in the group shares the same attrs/description, since
    # they're documenting the same element under different aliases
    current_group: list[SpecElement] = []
    pending_attr_names: list[str] = []
    pending_default_raw = ""
    buffer: list[str] = []

    def flush_attr() -> None:
        if current_group and pending_attr_names:
            desc = _clean(" ".join(buffer))
            for el in current_group:
                for name in pending_attr_names:
                    el.attrs[name] = SpecAttr(
                        description=desc, default_raw=pending_default_raw
                    )

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
            pending_default_raw = ""
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
            pending_default_raw = ""
            buffer = []
            i += 2
            continue

        if ANCHOR_RE.match(line):
            flush_attr()
            flush_description()
            pending_attr_names = []
            pending_default_raw = ""
            buffer = []
            i += 1
            continue

        attr_match = ATTR_LINE_RE.match(line)
        if attr_match:
            flush_attr()
            # only look for `name` tokens before ":at-val:" so type/default values
            # (e.g. :at-val:`string`) aren't mistaken for additional attribute names
            name_part, _, val_part = line.partition(":at-val:")
            pending_attr_names = AT_NAME_RE.findall(name_part)
            # val_part looks like "`real(3), "0 0 1"`" when an :at-val: is present,
            # or "" when this line only lists attribute names with no value of its own
            # (e.g. a line that just cross-references attributes documented elsewhere)
            val_text = val_part.strip()
            if val_text.startswith("`") and val_text.endswith("`"):
                val_text = val_text[1:-1]
            pending_default_raw = _parse_attr_default(val_text)
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


def load_ignore_file(path: Path = IGNORE_FILE) -> dict[str, set[str]]:
    """
    Parses `mjcf_ignore.txt`-style lines of the form `<category>:<key>` into
    {category: {key, ...}}. Blank lines and lines starting with `#` are skipped.
    Missing file just means nothing is ignored.
    """
    ignored: dict[str, set[str]] = {}
    if not path.exists():
        return ignored
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        category, _, key = line.partition(":")
        ignored.setdefault(category, set()).add(key)
    return ignored


@functools.cache
def _extract_field_docstrings(cls: type) -> dict[str, str]:
    """
    Parses the class's source to recover the bare string-literal "docstrings" this
    project writes directly after each field assignment. These are a convention for
    human/doc-tool readers only -- the interpreter discards them as statement
    expressions, so they aren't reachable via normal runtime introspection.

    Only looks at `cls`'s own body; fields inherited from a base class (e.g. the
    `name`/`noise`/`cutoff`/... fields most sensor subclasses get from `SensorBase`)
    are not found here -- see `_field_docstrings_for_class` for the MRO-aware version.
    """
    try:
        source = inspect.getsource(cls)
    except (OSError, TypeError):
        return {}
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return {}
    if not tree.body or not isinstance(tree.body[0], ast.ClassDef):
        return {}

    body = tree.body[0].body
    docs: dict[str, str] = {}
    for i, node in enumerate(body):
        name = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            name = node.targets[0].id
        if name is None or i + 1 >= len(body):
            continue
        following = body[i + 1]
        if (
            isinstance(following, ast.Expr)
            and isinstance(following.value, ast.Constant)
            and isinstance(following.value.value, str)
        ):
            docs[name] = following.value.value
    return docs


def _field_docstrings_for_class(cls: type) -> dict[str, str]:
    """
    Merges `_extract_field_docstrings` across the whole MRO, so fields defined on a
    base class (e.g. `SensorBase.name`) are attributed to every concrete subclass that
    inherits them. Walking base-to-derived means a subclass's own docstring for a
    field wins over an inherited one of the same name, if it redefines it.
    """
    docs: dict[str, str] = {}
    for base in reversed(cls.__mro__):
        docs.update(_extract_field_docstrings(base))
    return docs


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
            tag,
            {
                "classes": [],
                "covered": set(),
                "docstrings": [],
                # field name -> list of per-class docstrings (collected even for
                # fields outside `attributes`/`non_xml_fields`; harmless since
                # only the ones matching a spec attribute name are ever read)
                "field_docs": {},
                # fields any class declares as a single-value `Literal[...]`
                # discriminator (e.g. MeshSphere.builtin = Literal["sphere"]); these
                # are fixed tag values, not documentable XML attributes, so they're
                # exempt from the missing-docstring check below. A multi-value Literal
                # (e.g. `condim: Literal[1, 3, 4, 6]`) is a real constrained attribute
                # and still needs a docstring, so it doesn't count here
                "literal_fields": set(),
            },
        )
        bucket["classes"].append((cls.__name__, _class_location(cls), cls))
        names = {
            normalize_field_name(n) for n in (*cls.attributes, *cls.non_xml_fields)
        }
        bucket["covered"] |= names
        if cls.__doc__:
            bucket["docstrings"].append(cls.__doc__)
        for raw_name, doc in _field_docstrings_for_class(cls).items():
            bucket["field_docs"].setdefault(normalize_field_name(raw_name), []).append(
                doc
            )
        for raw_name, field_info in cls.model_fields.items():
            annotation = field_info.annotation
            if get_origin(annotation) is Literal and len(get_args(annotation)) == 1:
                bucket["literal_fields"].add(normalize_field_name(raw_name))
    return registry


def _python_field_default(cls: type, field_name: str) -> tuple[str, str | None]:
    """
    Classifies a Python field's default into ("required", None) when no default is
    set, ("optional", None) when the default is None, ("composite", None) when the
    default is a nested XMLModel (e.g. `pos: Pos = Pos(...)`, flattened into XML
    attributes by a separate code path that's out of scope for this comparison),
    ("discriminator", formatted_value) when the field is a single-value `Literal[...]`
    (e.g. `type: Literal[GeomType.SPHERE]` on a discriminated geom subclass -- its
    fixed value isn't meant to match the spec's generic default for the merged
    element), or ("literal", formatted_value) otherwise, formatted the same way
    `XMLModel.to_xml` formats it for the real XML output.
    """
    from mujoco_mojo.mjcf.xml_model import XMLModel, _format_value

    field_info = cls.model_fields[field_name]
    default = field_info.get_default(call_default_factory=True)
    if default is PydanticUndefined:
        return "required", None
    if default is None:
        return "optional", None
    if isinstance(default, XMLModel):
        return "composite", None
    formatted = _format_value(default)
    annotation = field_info.annotation
    if get_origin(annotation) is Literal and len(get_args(annotation)) == 1:
        return "discriminator", formatted
    return "literal", formatted


def _spec_attr_default(spec_attr: SpecAttr) -> tuple[str, str | None]:
    """Mirrors `_python_field_default`'s (kind, value) shape for the spec side."""
    stripped = spec_attr.default_raw.strip()
    if stripped == "required":
        return "required", None
    if stripped == "optional":
        return "optional", None
    match = re.match(r'^"([^"]*)"', stripped)
    if match:
        return "literal", match.group(1)
    # no `:at-val:` at all, or prose too irregular to parse as a literal/optional/required
    return "unparsed", None


def _parse_float_list(text: str) -> list[float] | None:
    try:
        return [float(tok) for tok in text.split()]
    except ValueError:
        return None


def _literals_match(spec_value: str, python_value: str) -> bool:
    if spec_value == python_value:
        return True
    # numeric defaults can be formatted differently (e.g. spec "1" vs python "1.0")
    # while still being the same value; compare as numbers when both sides parse
    spec_floats = _parse_float_list(spec_value)
    python_floats = _parse_float_list(python_value)
    if spec_floats is None or python_floats is None:
        return False
    return len(spec_floats) == len(python_floats) and all(
        math.isclose(a, b, abs_tol=1e-9) for a, b in zip(spec_floats, python_floats)
    )


def _default_mismatch(spec_attr: SpecAttr, cls: type, field_name: str) -> str | None:
    """Returns a human-readable mismatch description, or None if the default checks out."""
    spec_kind, spec_value = _spec_attr_default(spec_attr)
    if spec_kind == "unparsed":
        return None

    python_kind, python_value = _python_field_default(cls, field_name)
    if python_kind in ("composite", "discriminator"):
        return None

    if spec_kind == python_kind == "required":
        return None
    if spec_kind == python_kind == "optional":
        return None
    if spec_kind == "literal" and python_kind == "literal":
        assert spec_value is not None and python_value is not None
        if _literals_match(spec_value, python_value):
            return None
        return f'spec default "{spec_value}" != python default "{python_value}"'

    python_desc = f' ("{python_value}")' if python_value is not None else ""
    return f"spec marks attribute as {spec_kind} but python default is {python_kind}{python_desc}"


def _print_classes(classes: list[tuple[str, str, type]]) -> None:
    for name, location, *_ in classes:
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
    ignored = load_ignore_file()

    spec_names = set(spec_by_name)
    python_tags = set(python_registry)

    unimplemented = sorted(
        n
        for n in (spec_names - python_tags)
        if n not in ignored.get("unimplemented", ())
    )
    untagged = sorted(
        n for n in (python_tags - spec_names) if n not in ignored.get("untagged", ())
    )

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
            if f"{name}.{attr}" in ignored.get("coverage_gap", ()):
                continue
            missing.add(attr)
        if missing:
            console.print(
                f"  [red]{escape(name)}[/red]: missing [bold yellow]{escape(str(sorted(missing)))}[/bold yellow]"
            )
            _print_classes(python_registry[name]["classes"])

    console.print()
    console.rule(
        "[bold]Default value mismatches[/bold] (spec default doesn't match the Python field default)"
    )
    for name in sorted(spec_names & python_tags):
        spec_el = spec_by_name[name]
        for _, location, cls in python_registry[name]["classes"]:
            for field_name in cls.attributes:
                attr_name = normalize_field_name(field_name)
                if f"{name}.{attr_name}" in ignored.get("default_mismatch", ()):
                    continue
                spec_attr = spec_el.attrs.get(attr_name)
                if spec_attr is None:
                    continue
                mismatch = _default_mismatch(spec_attr, cls, field_name)
                if mismatch:
                    console.print(
                        f"  [red]{escape(name)}.{escape(attr_name)}[/red]: {escape(mismatch)}"
                    )
                    console.print(
                        f"      [bold cyan]{escape(cls.__name__)}[/bold cyan] [dim]{escape(location)}[/dim]"
                    )

    console.print()
    console.rule(
        "[bold]Attribute docstring warnings[/bold] (missing per-field docstring, or drifted from the spec)"
    )
    for name in sorted(spec_names & python_tags):
        spec_el = spec_by_name[name]
        covered = python_registry[name]["covered"]
        field_docs = python_registry[name]["field_docs"]
        literal_fields = python_registry[name]["literal_fields"]
        for attr_name, spec_attr in spec_el.attrs.items():
            if attr_name not in covered:
                continue  # already reported as a coverage gap above
            if attr_name in ORIENTATION_GROUP and covered & ORIENTATION_COVERING_FIELDS:
                continue  # merged into a `pose`/`orientation` field with no 1:1 docstring
            if attr_name in literal_fields:
                continue  # fixed discriminator value, not a documentable attribute
            # dedupe before joining: a field defined once on a shared base class (e.g.
            # GeomBase.name) is re-collected for every subclass sharing this tag, and
            # comparing a short spec description against N copies of the same text
            # would deflate the similarity ratio for no real reason
            py_doc = _clean(" ".join(dict.fromkeys(field_docs.get(attr_name, []))))
            if not py_doc:
                console.print(
                    f"  [magenta]{escape(name)}.{escape(attr_name)}[/magenta]: no docstring found"
                )
                continue
            if spec_attr.description in ("", SPEC_DESC_PLACEHOLDER):
                continue
            ratio = SequenceMatcher(None, spec_attr.description, py_doc).ratio()
            if ratio < DOCSTRING_SIMILARITY_THRESHOLD:
                console.print(
                    f"  [magenta]{escape(name)}.{escape(attr_name)}[/magenta]: similarity=[bold]{ratio:.2f}[/bold]"
                )

    console.print()
    console.rule(
        "[bold]Docstring similarity warnings[/bold] (ratio < 0.2, review for drift)"
    )
    for name in sorted(spec_names & python_tags):
        if name in ignored.get("docstring_class", ()):
            continue
        spec_desc = spec_by_name[name].description
        py_desc = _clean(" ".join(dict.fromkeys(python_registry[name]["docstrings"])))
        if not spec_desc or not py_desc:
            continue
        ratio = SequenceMatcher(None, spec_desc, py_desc).ratio()
        if ratio < DOCSTRING_SIMILARITY_THRESHOLD:
            console.print(
                f"  [magenta]{escape(name)}[/magenta]: similarity=[bold]{ratio:.2f}[/bold]"
            )
            _print_classes(python_registry[name]["classes"])


if __name__ == "__main__":
    main()
