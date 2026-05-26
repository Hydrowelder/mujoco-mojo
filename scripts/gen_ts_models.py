"""
Generate TypeScript types from Pydantic models in plot_config.py.

Run from the repo root:

    python scripts/gen_ts_models.py

Writes:
    src/mujoco_mojo/utils/layers/dojo/templates/static/ts/src/lib/plot-config.generated.ts
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).parent.parent
TS_OUT = (
    ROOT
    / "src/mujoco_mojo/utils/layers/dojo/templates/static/ts/src/lib"
    / "plot-config.generated.ts"
)

# ---------------------------------------------------------------------------
# JSON Schema → TypeScript converter
# ---------------------------------------------------------------------------


def _ref_name(ref: str) -> str:
    """'#/$defs/FooBar' → 'FooBar'"""
    return ref.rsplit("/", 1)[-1]


def _schema_to_ts(node: dict, defs: dict) -> str:
    """Recursively convert a JSON Schema node to a TypeScript type string."""
    if "$ref" in node:
        return _ref_name(node["$ref"])

    if "anyOf" in node:
        parts = [_schema_to_ts(s, defs) for s in node["anyOf"]]
        return " | ".join(parts)

    if "enum" in node:
        return " | ".join(f'"{v}"' for v in node["enum"])

    t = node.get("type")

    if t == "string":
        return "string"
    if t in ("number", "integer"):
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "null":
        return "null"

    if t == "array":
        if "prefixItems" in node:
            items = [_schema_to_ts(s, defs) for s in node["prefixItems"]]
            return f"[{', '.join(items)}]"
        if "items" in node:
            items_node = node["items"]
            # discriminated union (oneOf + discriminator) → use the FilterEntry alias
            if "oneOf" in items_node and "discriminator" in items_node:
                return "FilterEntry[]"
            return f"{_schema_to_ts(items_node, defs)}[]"
        return "unknown[]"

    if t == "object":
        add_props = node.get("additionalProperties")
        props = node.get("properties", {})
        required = set(node.get("required", []))

        if add_props and not props:
            # Pure dict / Record
            if add_props is True or add_props == {}:
                return "Record<string, unknown>"
            return f"Record<string, {_schema_to_ts(add_props, defs)}>"

        # Inline object (rare — models surface as $defs, not inline)
        lines = _props_to_ts_lines(props, required, defs)
        if add_props is True:
            lines.append("  [key: string]: unknown;")
        body = "\n".join(lines)
        return "{\n" + body + "\n}"

    return "unknown"


def _props_to_ts_lines(
    props: dict,
    required: set[str],
    defs: dict,
) -> list[str]:
    """Return one '  field?: Type;' string per property."""
    lines: list[str] = []
    for name, schema in props.items():
        ts_type = _schema_to_ts(schema, defs)
        opt = "" if name in required else "?"
        lines.append(f"  {name}{opt}: {ts_type};")
    return lines


# ---------------------------------------------------------------------------
# $defs → top-level TypeScript declarations
# ---------------------------------------------------------------------------


def _def_to_ts(name: str, schema: dict, defs: dict) -> str:
    """Convert one $defs entry to a TypeScript type or interface block."""
    # StrEnum / Literal  →  export type Name = "a" | "b";
    if "enum" in schema:
        values = " | ".join(f'"{v}"' for v in schema["enum"])
        return f"export type {name} = {values};\n"

    # BaseModel  →  export interface Name { ... }
    if schema.get("type") == "object":
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        lines = _props_to_ts_lines(props, required, defs)
        if schema.get("additionalProperties") is True:
            lines.append("  [key: string]: unknown;")
        body = "\n".join(lines) if lines else "  [key: string]: unknown;"
        return f"export interface {name} {{\n{body}\n}}\n"

    return f"// Unhandled $def: {name}\n"


def _top_level_interface(schema: dict, defs: dict) -> str:
    """Generate the top-level model (PlotConfig) as an interface."""
    name = schema.get("title", "PlotConfig")
    desc = schema.get("description", "")
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines = _props_to_ts_lines(props, required, defs)
    body = "\n".join(lines)
    comment = f"/** {desc} */\n" if desc else ""
    return f"{comment}export interface {name} {{\n{body}\n}}\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    # Import inside main so sys.path manipulation is localised
    sys.path.insert(0, str(ROOT / "src"))
    from mujoco_mojo.utils.layers.dojo.plot_config import PlotConfig

    schema = PlotConfig.model_json_schema()
    defs: dict = schema.get("$defs", {})

    blocks: list[str] = []

    # FilterEntry is the structural base for every discriminated filter object;
    # emitted first so XAxisConfig/YAxisConfig can reference it.
    blocks.append(
        "/** a single filter in a filter stack — type-discriminated, open-ended properties. */\n"
        "export type FilterEntry = { type: string; enabled?: boolean; [key: string]: unknown };\n"
    )

    # Emit each $def in definition order
    for def_name, def_schema in defs.items():
        blocks.append(_def_to_ts(def_name, def_schema, defs))

    # Emit the top-level PlotConfig interface
    blocks.append(_top_level_interface(schema, defs))

    header = textwrap.dedent("""\
        // ============================================================
        // AUTO-GENERATED - do not edit manually.
        // Source: src/mujoco_mojo/utils/layers/dojo/plot_config.py
        // Regenerate: python scripts/gen_ts_models.py
        // ============================================================

    """)

    output = header + "\n".join(blocks)
    TS_OUT.parent.mkdir(parents=True, exist_ok=True)
    TS_OUT.write_text(output, encoding="utf-8")
    print(f"Written → {TS_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
