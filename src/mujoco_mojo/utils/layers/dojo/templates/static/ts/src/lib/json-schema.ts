// Small helpers for walking a Pydantic-generated JSON Schema (as produced by
// model_json_schema(), e.g. PlotConfig's - see routers/mosaic.py's
// /api/plot-config-schema) to find a field's description at a given path.
// Shared by trial-viewer.ts's Plot Editor hover-info icons (_chart.html,
// _macros.html's field_help_icon) and its JSON editor CodeMirror hover
// tooltips - both read the one schema fetched once at page load, so a
// Field(description=...) change in plot_config.py shows up in both without
// any manual sync.
//
// This is not a general JSON Schema implementation - just enough of one to
// resolve what Pydantic v2's model_json_schema() actually emits: $ref,
// allOf (the single-item wrapper Pydantic uses so a $ref'd type can still
// carry its own sibling description), dict values (additionalProperties),
// array items, and a best-effort fallback across oneOf/anyOf branches for
// discriminated unions (PlotConfig.shapes) where this module has no way to
// know which branch's discriminator value is actually in use at a given
// JSON position - it just searches every branch for a matching property.

export interface JsonSchemaNode {
  $ref?: string;
  description?: string;
  type?: string;
  properties?: Record<string, JsonSchemaNode>;
  items?: JsonSchemaNode;
  additionalProperties?: JsonSchemaNode | boolean;
  allOf?: JsonSchemaNode[];
  oneOf?: JsonSchemaNode[];
  anyOf?: JsonSchemaNode[];
  $defs?: Record<string, JsonSchemaNode>;
  // Pydantic's own emission for a discriminated union (e.g. AnyFilter) -
  // maps each discriminator value ("rotation") to its $defs $ref
  // ("#/$defs/RotationFilter"). Only present on the union's own schema node
  // (an array's `items`, here), not on the resolved branches themselves.
  discriminator?: { propertyName: string; mapping: Record<string, string> };
  // value -> that enum member's own attribute-docstring, e.g.
  // GridMode's {"all": "Major and minor tick grid lines."} - a custom
  // extension (routers/mosaic.py's GeneratePlotConfigSchema), since
  // standard JSON Schema's `enum` keyword has no room for per-value
  // metadata. Only present on a resolved enum $def, not on the field
  // schema that $refs it.
  "x-enum-descriptions"?: Record<string, string>;
}

function resolveRef(root: JsonSchemaNode, ref: string): JsonSchemaNode {
  const key = ref.replace(/^#\/\$defs\//, "");
  return root.$defs?.[key] ?? {};
}

// Follows a single $ref or single-item allOf wrapper, keeping this node's
// own description if it has one - that's Pydantic's way of attaching a
// field-level description to an otherwise bare $ref'd type (e.g.
// PlotConfig.grid: GridMode gets {"$ref": ..., "description": "..."}).
function resolveNode(root: JsonSchemaNode, node: JsonSchemaNode): JsonSchemaNode {
  if (node.$ref) {
    const target = resolveNode(root, resolveRef(root, node.$ref));
    return { ...target, description: node.description ?? target.description };
  }
  if (node.allOf && node.allOf.length === 1) {
    const target = resolveNode(root, node.allOf[0]!);
    return { ...target, description: node.description ?? target.description };
  }
  return node;
}

// One step down the schema from `node` for JSON key `key` - a fixed
// property, a dict value (additionalProperties, e.g. PlotConfig.yAxes'
// per-signal YAxisConfig), an array item (e.g. PlotConfig.annotations' own
// Annotation items - `key` is ignored here since every index shares the
// same item schema; describeSchemaPath's caller passes "" for this step),
// or a property found by searching every oneOf/anyOf branch.
function stepInto(root: JsonSchemaNode, node: JsonSchemaNode, key: string): JsonSchemaNode | null {
  const resolved = resolveNode(root, node);
  if (resolved.properties && key in resolved.properties) return resolved.properties[key]!;
  if (resolved.type === "array" && resolved.items) return resolved.items;
  if (resolved.additionalProperties && typeof resolved.additionalProperties === "object") {
    return resolved.additionalProperties;
  }
  const branches = resolved.oneOf ?? resolved.anyOf;
  if (branches) {
    for (const branch of branches) {
      const branchResolved = resolveNode(root, branch);
      if (branchResolved.properties && key in branchResolved.properties) {
        return branchResolved.properties[key]!;
      }
    }
  }
  return null;
}

/**
 * The (fully $ref/allOf-resolved) schema node at `path` (a list of JSON
 * keys walked from the schema root) - null if the schema doesn't cover it
 * (not loaded yet, or the path doesn't resolve to a known field). A path
 * segment for an array's own item step (descending PlotConfig.annotations
 * into one Annotation, say) can be any string, including "" - stepInto
 * ignores it there since every array item shares the same schema
 * regardless of index. describeSchemaPath and describeEnumValue below are
 * both just this plus a specific key read off the result - exported
 * separately for callers (initCodeMirror's hover source) that want the
 * resolved node itself, e.g. to tell an enum field from a plain string one.
 */
export function resolveSchemaPath(root: JsonSchemaNode | null, path: string[]): JsonSchemaNode | null {
  if (!root) return null;
  let node: JsonSchemaNode = root;
  for (const seg of path) {
    const next = stepInto(root, node, seg);
    if (!next) return null;
    node = next;
  }
  return resolveNode(root, node);
}

/** Description of the field at `path` - see resolveSchemaPath. "" if unresolved or the field has no description. */
export function describeSchemaPath(root: JsonSchemaNode | null, path: string[]): string {
  return resolveSchemaPath(root, path)?.description ?? "";
}

/**
 * Description of `fieldName` on a specific $defs entry named `defName`
 * (e.g. defName "RectShape", fieldName "x0" -> "Left x coordinate.") -
 * for a caller that already knows exactly which model it's describing,
 * rather than walking there from the schema root through describeSchemaPath's
 * best-effort oneOf/anyOf branch search. That search picks whichever
 * branch happens to have a matching property name first, which is wrong
 * here specifically: PlotConfig.shapes is a VlineShape | HlineShape |
 * RectShape union where the same field name means different things per
 * branch (VlineShape.x0 is "X coordinate of the line.", RectShape.x0 is
 * "Left x coordinate.") - the Shape editor (_chart.html) always knows
 * which shape type it's currently editing (shapeDraft.type), so it can
 * name the exact def directly instead of leaving it to a guess.
 */
export function describeDefField(root: JsonSchemaNode | null, defName: string, fieldName: string): string {
  const field = root?.$defs?.[defName]?.properties?.[fieldName];
  if (!field || !root) return "";
  return resolveNode(root, field).description ?? "";
}

/**
 * Description of one enum member `value` belonging to the field at `path`
 * (e.g. path ["grid"], value "all" -> GridMode.ALL's own docstring) - ""
 * if the field isn't an enum, isn't loaded yet, or that particular value
 * has no attribute-docstring in plot_config.py. See JsonSchemaNode's own
 * "x-enum-descriptions" comment for where this data comes from.
 */
export function describeEnumValue(root: JsonSchemaNode | null, path: string[], value: string): string {
  return resolveSchemaPath(root, path)?.["x-enum-descriptions"]?.[value] ?? "";
}

/**
 * Description of `fieldName` on the filter class discriminated by `filterType`
 * (e.g. "rotation" + "originCol" -> RotationFilter.originCol's docstring).
 * The type -> $defs name mapping isn't a fixed rule - type "median" is
 * RollingMedianFilter, type "stat_median" is MedianFilter - so this reads
 * Pydantic's own discriminator.mapping off AnyFilter (read from
 * YAxisConfig.filters; XAxisConfig.filters carries the identical union, so
 * either would resolve the same mapping) rather than guessing a class name
 * from the type string.
 */
export function describeFilterField(root: JsonSchemaNode | null, filterType: string, fieldName: string): string {
  const mapping = root?.$defs?.["YAxisConfig"]?.properties?.["filters"]?.items?.discriminator?.mapping;
  const ref = mapping?.[filterType];
  if (!ref) return "";
  return describeDefField(root, ref.replace(/^#\/\$defs\//, ""), fieldName);
}
