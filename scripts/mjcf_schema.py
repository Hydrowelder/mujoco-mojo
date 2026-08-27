"""
Parser for MuJoCo's `mjcf.schema` file: the single source of truth for the MJCF modeling
language, introduced in MuJoCo 3.12.0 (see `src/xml/mjcf.schema` upstream). This is a small,
custom brace-delimited DSL, not XML/YAML/JSON, so it needs a real parser rather than a generic
loader. The full grammar is documented in the schema file's own header comment, which this
parser follows directly.

This module only builds the parsed representation (`Schema`, with `Enum`, `Group`, `Element`,
`Attribute`, `Child`, and `Constraint` records) and checks it for internal consistency (e.g. a
`use groupname` that names an undefined group). It intentionally does not compare the result
against mujoco_mojo's own Pydantic classes -- that comparison belongs in a follow-up script
that imports `parse_schema`/`fetch_schema` from here, mirroring how `check_mjcf_spec_coverage.py`
separates spec-parsing from the mojo-registry diff.

Usage:
    python scripts/mjcf_schema.py                      # fetch the schema from GitHub
    python scripts/mjcf_schema.py path/to/mjcf.schema   # parse a local copy instead
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import requests
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TransferSpeedColumn,
)
from rich.table import Table

SCHEMA_URL = "https://raw.githubusercontent.com/google-deepmind/mujoco/refs/heads/main/src/xml/mjcf.schema"

console = Console(soft_wrap=True)

# ---------------------------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------------------------


@dataclass
class EnumMember:
    key: str
    """The keyword as written in MJCF (quotes stripped), e.g. "cube" or "2d"."""

    value: str
    """The raw right-hand side: either a literal int or a C constant name (e.g. mjJNT_FREE)."""

    comment: str = ""


@dataclass
class Enum:
    name: str
    c_type: str | None
    """The bound C enum type (e.g. mjtJoint), or None for a schema-only enum with no C binding."""

    members: list[EnumMember] = field(default_factory=list)
    comment: str = ""
    line: int = 0


@dataclass
class AttrType:
    kind: str
    """One of: double, float, int, bool, string, file, chars, enum, flags, id, ref."""

    ref: str | None = None
    """The `<name>` inside enum<name>/flags<name>/id<ns>/ref<ns>; None for plain scalar types."""

    is_list: bool = False
    """True for enum<name>[] -- a list of enum keywords, distinct from flags<name> (bitwise)."""

    arity_min: int | None = None
    """None for a bare scalar type (double, bool, ...). 1 for a single-bracket fixed/ranged array."""

    arity_max: int | str | None = None
    """An int for a literal bound, a str for a symbolic bound (e.g. "mjNDYN"), or None for []
    (unbounded)."""

    def __str__(self) -> str:
        base = self.kind if self.ref is None else f"{self.kind}<{self.ref}>"
        if self.is_list:
            return f"{base}[]"
        if self.arity_min is None:
            return base
        if self.arity_max is None:
            return f"{base}[]"
        if self.arity_min == self.arity_max:
            return f"{base}[{self.arity_min}]"
        return f"{base}[{self.arity_min}..{self.arity_max}]"


@dataclass
class Attribute:
    name: str
    type: AttrType
    default: str | None = None
    """Raw default expression as written (e.g. "auto", "-1", "{1, 0, 0, 0}"), or None if absent."""

    required: bool = False
    nodefault: bool = False
    field_name: str | None = None
    """The bound C struct field, from `field=name`, when it differs from `name`."""

    pattern: str | None = None
    min: str | None = None
    max: str | None = None
    positive: bool = False
    reading_custom: bool = False
    writing_custom: bool = False
    comment: str = ""
    line: int = 0
    source_group: str | None = None
    """Name of the group this attribute was spliced in from via `use`, or None if declared
    directly on the element."""


@dataclass
class Child:
    name: str
    cardinality: str
    """One of "?" (optional, at most one), "!" (required, exactly one), "*" (any number),
    "R" (any number, recursive)."""

    line: int = 0


@dataclass
class Constraint:
    kind: str
    """One of: exclusive, together, requires, oneof."""

    bundles: list[list[str]]
    """Each bundle is a list of attribute names; multiple names in one bundle (from "a+b" in the
    schema) mean the bundle is complete only when all of them are present."""

    line: int = 0


@dataclass
class SetDirective:
    field_name: str
    """The C struct field being hardcoded, e.g. "type" or "objtype"."""

    value: str
    """The literal value assigned, usually a C constant (e.g. mjSENS_TOUCH)."""

    line: int = 0


@dataclass
class Group:
    name: str
    variant: bool
    """True for `group name variant { ... }`: the group's attributes are mutually exclusive."""

    attributes: list[Attribute] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    line: int = 0


@dataclass
class Element:
    name: str
    struct: str | None
    """The bound mjs* C struct (e.g. mjsActuator), or None for a bare/grouping element."""

    xml_tag: str | None = None
    """From the `xml=tag` facet, when the XML tag differs from the declaration name."""

    alias: str | None = None
    """From the `alias=body` facet: this element's grammar is validated against another
    element's row (used by worldbody/frame/replicate)."""

    field_name: str | None = None
    """From an element-level `field=name` facet (e.g. visual/global binds to mjVisual.global)."""

    used_groups: list[str] = field(default_factory=list)
    attributes: list[Attribute] = field(default_factory=list)
    """Flattened attribute list in declaration order, including those spliced in via `use`."""

    sets: list[SetDirective] = field(default_factory=list)
    """Fields hardcoded by this element (e.g. `touch` sets type=mjSENS_TOUCH) -- implied by the
    tag itself, not settable as an XML attribute."""

    children: list[Child] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    comment: str = ""
    line: int = 0

    def attribute_names(self) -> set[str]:
        return {a.name for a in self.attributes}


@dataclass
class Schema:
    enums: dict[str, Enum] = field(default_factory=dict)
    groups: dict[str, Group] = field(default_factory=dict)
    elements: dict[str, Element] = field(default_factory=dict)


# ---------------------------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------------------------


def fetch_schema(url: str = SCHEMA_URL) -> str:
    """
    Downloads the schema file, showing a rich progress bar keyed off Content-Length.

    Requests identity encoding: GitHub gzips the response by default, and requests
    transparently decompresses each chunk before it reaches us, so Content-Length (the
    compressed size) would otherwise undercount against the bytes we actually measure.
    """
    response = requests.get(
        url, stream=True, timeout=30, headers={"Accept-Encoding": "identity"}
    )
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))

    chunks: list[bytes] = []
    with Progress(
        TextColumn("[bold blue]Downloading mjcf.schema"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("download", total=total or None)
        for chunk in response.iter_content(chunk_size=8192):
            chunks.append(chunk)
            progress.update(task, advance=len(chunk))

    return b"".join(chunks).decode("utf-8")


# ---------------------------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------------------------

_ENUM_HEADER_RE = re.compile(
    r"^enum\s+(?P<name>\w+)(?:\s*:\s*(?P<ctype>\w+))?\s*\{\s*(?:#\s*(?P<comment>.*))?$"
)
_ENUM_MEMBER_RE = re.compile(
    r'^\s*(?P<key>"[^"]*"|\S+)\s*=\s*(?P<value>\S+)\s*(?:#\s*(?P<comment>.*))?$'
)
_GROUP_HEADER_RE = re.compile(
    r"^group\s+(?P<name>\w+)(?P<variant>\s+variant)?\s*\{\s*(?:#\s*.*)?$"
)
_ELEMENT_HEADER_RE = re.compile(
    r"^element\s+(?P<name>\w+)(?:\s*:\s*(?P<struct>\w+))?"
    r"(?:\s*\((?P<facets>[^)]*)\))?\s*\{\s*(?:#\s*(?P<comment>.*))?$"
)
_USE_RE = re.compile(r"^\s*use\s+(?P<name>\w+)\s*$")
_SET_RE = re.compile(r"^\s*set\s+(?P<field>\w+)\s*=\s*(?P<value>\S+)\s*$")
_CHILD_RE = re.compile(r"^\s*child\s+(?P<name>\w+)\s+(?P<card>[?!*R])\s*(?:#\s*.*)?$")
_CONSTRAINT_RE = re.compile(
    r"^\s*(?P<kind>exclusive|together|requires|oneof)\s+(?P<rest>[^#]+?)\s*(?:#.*)?$"
)
_ATTR_RE = re.compile(
    r"^\s*(?P<name>\w+)\s*:\s*(?P<type>[^=(#]+?)\s*"
    r"(?:=\s*(?P<default>\{[^}]*\}|\S+)\s*)?"
    r"(?:\((?P<facets>[^)]*)\)\s*)?"
    r"(?:#\s*(?P<comment>.*))?$"
)
_TYPE_RE = re.compile(r"^(?P<kind>\w+)(?:<(?P<ref>\w+)>)?(?:\[(?P<arity>[^\]]*)\])?$")
_FACET_TOKEN_RE = re.compile(r'(?P<key>\w+)(?:=(?P<value>"[^"]*"|\S+))?')


def _parse_type(raw: str) -> AttrType:
    raw = raw.strip()
    m = _TYPE_RE.match(raw)
    if not m:
        msg = f"Could not parse attribute type: {raw!r}"
        raise ValueError(msg)

    kind = m.group("kind")
    ref = m.group("ref")
    arity = m.group("arity")

    is_list = False
    arity_min: int | None = None
    arity_max: int | str | None = None

    if arity is not None:
        if kind in ("enum", "flags") and ref is not None and arity == "":
            # enum<name>[] -- a list of keywords, not a fixed/ranged/unbounded numeric array
            is_list = True
        elif arity == "":
            arity_min, arity_max = 0, None
        elif ".." in arity:
            lo, hi = arity.split("..", 1)
            arity_min = int(lo)
            arity_max = int(hi) if hi.isdigit() else hi
        else:
            arity_min = arity_max = int(arity)

    return AttrType(
        kind=kind, ref=ref, is_list=is_list, arity_min=arity_min, arity_max=arity_max
    )


def _parse_facets(raw: str | None) -> dict[str, str | bool]:
    """
    Splits a parenthesized facet string like 'min=0, max=5, reading=custom' into a dict of
    bare-flag facets (value True) and key=value facets (value the unquoted string).
    """
    facets: dict[str, str | bool] = {}
    if not raw:
        return facets
    for m in _FACET_TOKEN_RE.finditer(raw):
        key = m.group("key")
        value = m.group("value")
        if value is None:
            facets[key] = True
        else:
            facets[key] = value.strip('"')
    return facets


def _apply_attr_facets(attr: Attribute, facets: dict[str, str | bool]) -> None:
    attr.required = bool(facets.get("required", False))
    attr.nodefault = bool(facets.get("nodefault", False))
    attr.positive = bool(facets.get("positive", False))
    attr.reading_custom = facets.get("reading") == "custom"
    attr.writing_custom = facets.get("writing") == "custom"
    field_val = facets.get("field")
    attr.field_name = field_val if isinstance(field_val, str) else None
    pattern_val = facets.get("pattern")
    attr.pattern = pattern_val if isinstance(pattern_val, str) else None
    min_val = facets.get("min")
    attr.min = min_val if isinstance(min_val, str) else None
    max_val = facets.get("max")
    attr.max = max_val if isinstance(max_val, str) else None


def _parse_attribute(line: str, lineno: int) -> Attribute:
    m = _ATTR_RE.match(line)
    if not m:
        msg = f"line {lineno}: could not parse attribute: {line!r}"
        raise ValueError(msg)

    attr_type = _parse_type(m.group("type"))
    facets = _parse_facets(m.group("facets"))
    attr = Attribute(
        name=m.group("name"),
        type=attr_type,
        default=m.group("default"),
        comment=(m.group("comment") or "").strip(),
        line=lineno,
    )
    _apply_attr_facets(attr, facets)
    return attr


def _parse_constraint(kind: str, rest: str, lineno: int) -> Constraint:
    bundles = [token.split("+") for token in rest.split()]
    return Constraint(kind=kind, bundles=bundles, line=lineno)


def parse_schema(text: str, *, show_progress: bool = True) -> Schema:
    """
    Parses the full mjcf.schema text into a `Schema`. Raises ValueError with a line number
    on any construct it doesn't recognize, rather than silently skipping it.
    """
    schema = Schema()
    lines = text.splitlines()

    block: Enum | Group | Element | None = None

    iterator = enumerate(lines, start=1)
    if show_progress:
        iterator = _tracked(iterator, total=len(lines))

    for lineno, raw_line in iterator:
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "}":
            if block is None:
                msg = f"line {lineno}: unmatched closing brace"
                raise ValueError(msg)
            if isinstance(block, Enum):
                schema.enums[block.name] = block
            elif isinstance(block, Group):
                schema.groups[block.name] = block
            else:
                schema.elements[block.name] = block
            block = None
            continue

        if block is None:
            if m := _ENUM_HEADER_RE.match(stripped):
                block = Enum(
                    name=m.group("name"),
                    c_type=m.group("ctype"),
                    comment=(m.group("comment") or "").strip(),
                    line=lineno,
                )
                continue
            if m := _GROUP_HEADER_RE.match(stripped):
                block = Group(
                    name=m.group("name"),
                    variant=m.group("variant") is not None,
                    line=lineno,
                )
                continue
            if m := _ELEMENT_HEADER_RE.match(stripped):
                facets = _parse_facets(m.group("facets"))
                xml_tag = facets.get("xml")
                alias = facets.get("alias")
                field_val = facets.get("field")
                block = Element(
                    name=m.group("name"),
                    struct=m.group("struct"),
                    xml_tag=xml_tag if isinstance(xml_tag, str) else None,
                    alias=alias if isinstance(alias, str) else None,
                    field_name=field_val if isinstance(field_val, str) else None,
                    comment=(m.group("comment") or "").strip(),
                    line=lineno,
                )
                continue
            msg = f"line {lineno}: expected 'enum'/'group'/'element' at top level: {stripped!r}"
            raise ValueError(msg)

        if isinstance(block, Enum):
            m = _ENUM_MEMBER_RE.match(stripped)
            if not m:
                msg = f"line {lineno}: could not parse enum member: {stripped!r}"
                raise ValueError(msg)
            block.members.append(
                EnumMember(
                    key=m.group("key").strip('"'),
                    value=m.group("value"),
                    comment=(m.group("comment") or "").strip(),
                )
            )
            continue

        # block is a Group or Element: both can carry presence constraints, but only
        # elements splice groups (`use`), hardcode fields (`set`), or declare children.
        if m := _CONSTRAINT_RE.match(stripped):
            block.constraints.append(
                _parse_constraint(m.group("kind"), m.group("rest"), lineno)
            )
            continue

        if isinstance(block, Group):
            block.attributes.append(_parse_attribute(stripped, lineno))
            continue

        if m := _USE_RE.match(stripped):
            block.used_groups.append(m.group("name"))
            continue
        if m := _SET_RE.match(stripped):
            block.sets.append(
                SetDirective(
                    field_name=m.group("field"), value=m.group("value"), line=lineno
                )
            )
            continue
        if m := _CHILD_RE.match(stripped):
            block.children.append(
                Child(name=m.group("name"), cardinality=m.group("card"), line=lineno)
            )
            continue
        block.attributes.append(_parse_attribute(stripped, lineno))

    if block is not None:
        msg = f"unterminated block starting at line {block.line}"
        raise ValueError(msg)

    _splice_groups(schema)
    return schema


def _splice_groups(schema: Schema) -> None:
    """
    Expands each element's `use groupname` references into flattened attribute and
    constraint lists, tagging each spliced attribute with the group it came from. `use` lines
    were recorded separately from attributes, so this just appends group attributes/constraints
    up front; declaration order within an element (own vs. used) is only preserved relative to
    other `use`s/attributes, which is good enough for coverage purposes since the schema always
    documents `use` before an element's own overrides.
    """
    for element in schema.elements.values():
        expanded_attrs: list[Attribute] = []
        expanded_constraints: list[Constraint] = []
        for group_name in element.used_groups:
            group = schema.groups.get(group_name)
            if group is None:
                continue
            for attr in group.attributes:
                spliced = Attribute(**{**attr.__dict__, "source_group": group_name})
                expanded_attrs.append(spliced)
            expanded_constraints.extend(group.constraints)
        expanded_attrs.extend(element.attributes)
        expanded_constraints.extend(element.constraints)
        element.attributes = expanded_attrs
        element.constraints = expanded_constraints


def _tracked(iterator, total: int):
    from rich.progress import track

    yield from track(
        iterator, total=total, description="Parsing mjcf.schema", console=console
    )


# ---------------------------------------------------------------------------------------------
# Self-consistency validation
# ---------------------------------------------------------------------------------------------


def validate_schema(schema: Schema) -> list[str]:
    """
    Checks the parsed schema for dangling references. Returns a list of warning strings;
    an empty list means the schema is internally consistent.
    """
    warnings: list[str] = []

    for element in schema.elements.values():
        for group_name in element.used_groups:
            if group_name not in schema.groups:
                warnings.append(
                    f"element {element.name!r} (line {element.line}): "
                    f"use of undefined group {group_name!r}"
                )

        for child in element.children:
            if child.name not in schema.elements:
                warnings.append(
                    f"element {element.name!r} (line {child.line}): "
                    f"child references undefined element {child.name!r}"
                )

        attr_names = element.attribute_names()
        for attr in element.attributes:
            if (
                attr.type.kind in ("enum", "flags")
                and attr.type.ref not in schema.enums
            ):
                warnings.append(
                    f"element {element.name!r}.{attr.name} (line {attr.line}): "
                    f"references undefined enum {attr.type.ref!r}"
                )

        for constraint in element.constraints:
            for bundle in constraint.bundles:
                for name in bundle:
                    if name not in attr_names:
                        warnings.append(
                            f"element {element.name!r} (line {constraint.line}): "
                            f"{constraint.kind} references undefined attribute {name!r}"
                        )

    return warnings


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------


def _print_summary(schema: Schema, warnings: list[str]) -> None:
    table = Table(title="mjcf.schema parse summary")
    table.add_column("Construct", style="bold cyan")
    table.add_column("Count", justify="right")
    table.add_row("Enums", str(len(schema.enums)))
    table.add_row("Groups", str(len(schema.groups)))
    table.add_row("Elements", str(len(schema.elements)))
    table.add_row(
        "Attributes (flattened, incl. spliced groups)",
        str(sum(len(e.attributes) for e in schema.elements.values())),
    )
    table.add_row(
        "Presence constraints",
        str(sum(len(e.constraints) for e in schema.elements.values())),
    )
    console.print(table)

    console.print()
    if warnings:
        console.rule(f"[bold red]Consistency warnings[/bold red] ({len(warnings)})")
        for w in warnings:
            console.print(f"  [yellow]{w}[/yellow]")
    else:
        console.print("[bold green]No consistency warnings.[/bold green]")


def main() -> None:
    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        text = fetch_schema()

    schema = parse_schema(text)
    warnings = validate_schema(schema)
    _print_summary(schema, warnings)


if __name__ == "__main__":
    main()
