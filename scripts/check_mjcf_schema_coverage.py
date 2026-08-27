"""
Cross-references MuJoCo's authoritative `mjcf.schema` (see `scripts/mjcf_schema.py`) against
the XMLModel subclasses implemented in mujoco_mojo. This is the schema-file-based counterpart
to `check_mjcf_spec_coverage.py`, which scrapes and regex-parses the `XMLreference.rst.txt`
docs page instead. The schema is structured and generated from/tested against the C headers,
so it's an authoritative source rather than scraped prose -- this script reuses mojo's own
Pydantic registry (`build_python_registry`) from the RST-based script rather than duplicating
it, and reuses `mjcf_schema.parse_schema`/`fetch_schema` for the schema side.

For every schema element it reports:
- whether mujoco_mojo implements a class for it (matched by `tag`, after resolving `xml=`
  renames)
- attributes declared in the schema but not covered by any matching class's
  `attributes`/`non_xml_fields` (likely a missed field)
- attributes whose schema default doesn't match the Python field's default value
- attributes the schema marks `required` where the Python field has a non-required default,
  or vice versa

This is advisory, not a hard gate: the schema legitimately declares several distinct elements
under the same XML tag depending on context (e.g. `joint` the body child vs `equality_joint`
(`xml=joint`) vs `composite_joint` (`xml=joint`)), which are merged the same permissive way
`check_mjcf_spec_coverage.py` merges its own duplicate bare names -- so review the output rather
than treating it as pass/fail. Reviewed, accepted findings can be silenced via the same
`mjcf_ignore.txt` used by the RST-based script (categories: "unimplemented", "untagged",
"coverage_gap", "default_mismatch").

Usage:
    python scripts/check_mjcf_schema_coverage.py                    # fetch the schema live
    python scripts/check_mjcf_schema_coverage.py path/to/mjcf.schema  # use a local copy
"""

from __future__ import annotations

import sys
from pathlib import Path

from check_mjcf_spec_coverage import (
    IGNORE_FILE,
    ORIENTATION_COVERING_FIELDS,
    ORIENTATION_GROUP,
    _literals_match,
    _print_classes,
    build_python_registry,
    load_ignore_file,
    normalize_field_name,
)
from mjcf_schema import (
    Attribute,
    Element,
    Schema,
    fetch_schema,
    parse_schema,
    validate_schema,
)
from rich.console import Console
from rich.markup import escape

console = Console(soft_wrap=True)


def merge_elements_by_tag(schema: Schema) -> dict[str, Element]:
    """
    Merges schema elements by their effective XML tag (`xml_tag` facet if present, else the
    declaration name), unioning attributes/children/constraints across every declaration that
    shares a tag. Mirrors `check_mjcf_spec_coverage.merge_by_bare_name`'s permissive merge for
    the RST spec, and for the same reason: several schema elements share a tag by design (e.g.
    `equality_joint`/`fixed_joint`/`composite_joint` all render as `<joint>` in different
    contexts).
    """
    merged: dict[str, Element] = {}
    for element in schema.elements.values():
        tag = element.xml_tag or element.name
        bucket = merged.setdefault(
            tag, Element(name=tag, struct=element.struct, line=element.line)
        )
        bucket.attributes.extend(element.attributes)
        bucket.children.extend(element.children)
        bucket.constraints.extend(element.constraints)
        bucket.sets.extend(element.sets)
        bucket.used_groups.extend(element.used_groups)
        if not bucket.comment:
            bucket.comment = element.comment
    return merged


def _schema_attr_default(attr: Attribute) -> tuple[str, str | None] | None:
    """
    Classifies a schema attribute's default into the same (kind, value) shape
    `check_mjcf_spec_coverage._python_field_default` uses for the Python side: ("required", None),
    ("optional", None) for reference-like types with no default (matches mojo's `X | None = None`
    convention), or ("literal", formatted_value). A brace-delimited array default is reformatted
    to mojo's own space-separated `_format_value` convention so numeric comparison lines up.

    Returns None (skip comparison entirely) when there's no reliable ground truth to compare
    against:
    - `reading=custom`/`writing=custom` attributes -- the schema's own header documents these as
      hand-written, with no typed binding generated.
    - Any non-reference attribute with no explicit `= value` at all. It's tempting to assume the
      C zero-init value (0 / false / first enum keyword), but that's provably unreliable: checked
      concretely against the real engine, `adhesion/gain` has no explicit schema default yet
      compiles to gain=1, not gain=0 -- a compiler-side hardcoded convenience default for actuator
      shortcuts (per their own doc comment: "sets ... internal defaults ... regardless of any
      default settings"), invisible to the schema's `= value` facet. Since the schema alone can't
      distinguish a true zero-init from a hardcoded one, asserting either would risk reporting
      confident false positives -- skip rather than guess. Reference-like types remain safe to
      compare, since "no default" for those genuinely means absent, matching mojo's `X | None`.
    """
    if attr.reading_custom or attr.writing_custom:
        return None
    if attr.required:
        return "required", None

    if attr.default is not None:
        value = attr.default.strip()
        if value.startswith("{") and value.endswith("}"):
            value = " ".join(tok.strip() for tok in value[1:-1].split(","))
        else:
            value = value.strip('"')
        return "literal", value

    if attr.type.kind in ("ref", "id", "string", "file"):
        return "optional", None
    return None


def _default_mismatch(attr: Attribute, cls: type, field_name: str) -> str | None:
    """
    Returns a human-readable mismatch description, or None if the default checks out (or
    isn't checkable -- see `_schema_attr_default`).
    """
    from check_mjcf_spec_coverage import _python_field_default

    schema_result = _schema_attr_default(attr)
    if schema_result is None:
        return None
    schema_kind, schema_value = schema_result

    python_kind, python_value = _python_field_default(cls, field_name)
    if python_kind in ("composite", "discriminator"):
        return None

    if schema_kind == python_kind == "required":
        return None
    if schema_kind == python_kind == "optional":
        return None
    if schema_kind == "literal" and python_kind == "literal":
        assert schema_value is not None and python_value is not None
        if _literals_match(schema_value, python_value):
            return None
        return f'schema default "{schema_value}" != python default "{python_value}"'

    python_desc = f' ("{python_value}")' if python_value is not None else ""
    return f"schema marks attribute as {schema_kind} but python default is {python_kind}{python_desc}"


def main() -> None:
    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        text = fetch_schema()

    schema = parse_schema(text)
    warnings = validate_schema(schema)
    if warnings:
        console.rule(
            f"[bold red]Schema self-consistency warnings[/bold red] ({len(warnings)})"
        )
        for w in warnings:
            console.print(f"  [yellow]{escape(w)}[/yellow]")
        console.print()

    schema_by_tag = merge_elements_by_tag(schema)
    python_registry = build_python_registry()
    ignored = load_ignore_file(IGNORE_FILE)

    schema_tags = set(schema_by_tag)
    python_tags = set(python_registry)

    unimplemented = sorted(
        n
        for n in (schema_tags - python_tags)
        if n not in ignored.get("unimplemented", ())
    )
    untagged = sorted(
        n for n in (python_tags - schema_tags) if n not in ignored.get("untagged", ())
    )

    console.rule(
        f"[bold]Schema elements with no matching implemented tag[/bold] ({len(unimplemented)})"
    )
    for name in unimplemented:
        console.print(f"  [yellow]{escape(name)}[/yellow]")

    console.print()
    console.rule(
        f"[bold]Implemented tags with no matching schema element[/bold] ({len(untagged)})"
    )
    for name in untagged:
        console.print(f"  [yellow]{escape(name)}[/yellow]:")
        _print_classes(python_registry[name]["classes"])

    console.print()
    console.rule(
        "[bold]Attribute coverage gaps[/bold] (schema attributes not covered by attributes/non_xml_fields)"
    )
    for name in sorted(schema_tags & python_tags):
        schema_el = schema_by_tag[name]
        covered = python_registry[name]["covered"]
        missing = set()
        for attr in schema_el.attributes:
            attr_name = normalize_field_name(attr.name)
            if attr_name in covered:
                continue
            if attr_name in ORIENTATION_GROUP and covered & ORIENTATION_COVERING_FIELDS:
                continue
            if f"{name}.{attr_name}" in ignored.get("coverage_gap", ()):
                continue
            missing.add(attr_name)
        if missing:
            console.print(
                f"  [red]{escape(name)}[/red]: missing [bold yellow]{escape(str(sorted(missing)))}[/bold yellow]"
            )
            _print_classes(python_registry[name]["classes"])

    console.print()
    console.rule(
        "[bold]Default value mismatches[/bold] (schema default doesn't match the Python field default)"
    )
    for name in sorted(schema_tags & python_tags):
        schema_el = schema_by_tag[name]
        schema_attrs_by_name = {
            normalize_field_name(a.name): a for a in schema_el.attributes
        }
        for _, location, cls in python_registry[name]["classes"]:
            for field_name in cls.attributes:
                attr_name = normalize_field_name(field_name)
                if f"{name}.{attr_name}" in ignored.get("default_mismatch", ()):
                    continue
                schema_attr = schema_attrs_by_name.get(attr_name)
                if schema_attr is None:
                    continue
                mismatch = _default_mismatch(schema_attr, cls, field_name)
                if mismatch:
                    console.print(
                        f"  [red]{escape(name)}.{escape(attr_name)}[/red]: {escape(mismatch)}"
                    )
                    console.print(
                        f"      [bold cyan]{escape(cls.__name__)}[/bold cyan] [dim]{escape(location)}[/dim]"
                    )


if __name__ == "__main__":
    main()
