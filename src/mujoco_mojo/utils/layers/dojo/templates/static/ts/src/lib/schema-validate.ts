// Minimal JSON Schema (draft 2020-12 subset) validator for the PlotConfig
// schema exported from plot_config.py. Covers $ref/$defs, anyOf, oneOf with
// discriminator, enum, const, object/array/number constraints - the subset
// that Pydantic's model_json_schema() actually emits for this project.
//
// This is additive validation: it runs alongside (not instead of) the
// hand-written semantic checks in validateConfig().

export type JsonSchemaNode = Record<string, unknown>;

function resolveRef(ref: string, defs: Record<string, JsonSchemaNode>): JsonSchemaNode {
  const name = ref.replace(/^#\/\$defs\//, "");
  const resolved = defs[name];
  if (!resolved) throw new Error(`Unresolved $ref: ${ref}`);
  return resolved;
}

function typeOfValue(value: unknown): string {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  return typeof value;
}

function matchesType(value: unknown, type: string): boolean {
  const actual = typeOfValue(value);
  if (type === "integer") return actual === "number" && Number.isInteger(value as number);
  if (type === "number") return actual === "number" || actual === "integer";
  return actual === type;
}

function pickDiscriminatedBranch(
  data: unknown,
  schema: JsonSchemaNode,
  defs: Record<string, JsonSchemaNode>,
  path: string,
): { schema?: JsonSchemaNode; error?: string } {
  const disc = schema.discriminator as
    | { propertyName: string; mapping?: Record<string, string> }
    | undefined;
  if (!disc || typeOfValue(data) !== "object") {
    return { error: `${path}: does not match any allowed type` };
  }
  const obj = data as Record<string, unknown>;
  const tag = obj[disc.propertyName];
  const ref = typeof tag === "string" ? disc.mapping?.[tag] : undefined;
  if (!ref) {
    return { error: `${path}: unknown "${disc.propertyName}" value ${JSON.stringify(tag)}` };
  }
  return { schema: resolveRef(ref, defs) };
}

function validatesQuietly(data: unknown, schema: JsonSchemaNode, defs: Record<string, JsonSchemaNode>): boolean {
  return validateNode(data, schema, defs, "$").length === 0;
}

function validateNode(
  data: unknown,
  schema: JsonSchemaNode,
  defs: Record<string, JsonSchemaNode>,
  path: string,
): string[] {
  if (typeof schema.$ref === "string") {
    return validateNode(data, resolveRef(schema.$ref, defs), defs, path);
  }

  if (Array.isArray(schema.anyOf)) {
    const branches = schema.anyOf as JsonSchemaNode[];
    if (branches.some((s) => validatesQuietly(data, s, defs))) return [];
    return [`${path}: does not match any allowed type`];
  }

  if (Array.isArray(schema.oneOf)) {
    const branch = pickDiscriminatedBranch(data, schema, defs, path);
    if (branch.error) return [branch.error];
    return validateNode(data, branch.schema!, defs, path);
  }

  if ("const" in schema) {
    if (data !== schema.const) return [`${path}: must equal ${JSON.stringify(schema.const)}`];
    return [];
  }

  if (Array.isArray(schema.enum)) {
    if (!schema.enum.includes(data)) {
      return [`${path}: must be one of ${schema.enum.map((v) => JSON.stringify(v)).join(", ")}`];
    }
    return [];
  }

  const errors: string[] = [];
  const type = schema.type as string | string[] | undefined;
  if (type) {
    const types = Array.isArray(type) ? type : [type];
    if (!types.some((t) => matchesType(data, t))) {
      errors.push(`${path}: must be of type ${types.join(" | ")} (got ${typeOfValue(data)})`);
      return errors;
    }
  }

  if (type === "object" && typeOfValue(data) === "object") {
    const obj = data as Record<string, unknown>;
    for (const key of (schema.required as string[] | undefined) ?? []) {
      if (!(key in obj)) errors.push(`${path}.${key}: required field is missing`);
    }
    const properties = schema.properties as Record<string, JsonSchemaNode> | undefined;
    if (properties) {
      for (const [key, propSchema] of Object.entries(properties)) {
        if (key in obj) errors.push(...validateNode(obj[key], propSchema, defs, `${path}.${key}`));
      }
    }
    // dict/Record types (e.g. PlotConfig.yAxes) validate each entry against
    // `additionalProperties` instead of (or in addition to) named properties.
    const additionalProperties = schema.additionalProperties;
    if (additionalProperties && typeof additionalProperties === "object") {
      for (const [key, value] of Object.entries(obj)) {
        if (!properties || !(key in properties)) {
          errors.push(...validateNode(value, additionalProperties as JsonSchemaNode, defs, `${path}.${key}`));
        }
      }
    }
  }

  if (type === "array" && Array.isArray(data)) {
    const prefixItems = schema.prefixItems as JsonSchemaNode[] | undefined;
    const items = schema.items as JsonSchemaNode | undefined;
    if (prefixItems) {
      prefixItems.forEach((itemSchema, i) => {
        if (i < data.length) errors.push(...validateNode(data[i], itemSchema, defs, `${path}[${i}]`));
      });
    } else if (items) {
      data.forEach((item, i) => errors.push(...validateNode(item, items, defs, `${path}[${i}]`)));
    }
    if (typeof schema.minItems === "number" && data.length < schema.minItems) {
      errors.push(`${path}: must have at least ${schema.minItems} items`);
    }
    if (typeof schema.maxItems === "number" && data.length > schema.maxItems) {
      errors.push(`${path}: must have at most ${schema.maxItems} items`);
    }
  }

  if (type === "number" || type === "integer") {
    const n = data as number;
    if (typeof schema.minimum === "number" && n < schema.minimum) {
      errors.push(`${path}: must be >= ${schema.minimum}`);
    }
    if (typeof schema.maximum === "number" && n > schema.maximum) {
      errors.push(`${path}: must be <= ${schema.maximum}`);
    }
    if (typeof schema.exclusiveMinimum === "number" && n <= schema.exclusiveMinimum) {
      errors.push(`${path}: must be > ${schema.exclusiveMinimum}`);
    }
    if (typeof schema.exclusiveMaximum === "number" && n >= schema.exclusiveMaximum) {
      errors.push(`${path}: must be < ${schema.exclusiveMaximum}`);
    }
  }

  return errors;
}

// Validates `data` against a top-level JSON Schema document (with its own
// `$defs`), returning a list of human-readable error paths/messages.
export function validateAgainstSchema(data: unknown, schema: JsonSchemaNode): string[] {
  const defs = (schema.$defs as Record<string, JsonSchemaNode> | undefined) ?? {};
  return validateNode(data, schema, defs, "config");
}
