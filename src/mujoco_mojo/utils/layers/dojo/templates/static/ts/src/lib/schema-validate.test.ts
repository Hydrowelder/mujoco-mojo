import { describe, expect, it } from "vitest";

import { collectSchemaDiagnostics, validateAgainstSchema, type JsonSchemaNode } from "./schema-validate";

const errorsOf = (data: unknown, schema: JsonSchemaNode) => validateAgainstSchema(data, schema);

describe("types", () => {
  it("accepts a matching type and names both types on a mismatch", () => {
    expect(errorsOf("x", { type: "string" })).toEqual([]);
    expect(errorsOf(3, { type: "string" })).toEqual(["config: must be of type string (got number)"]);
  });

  it("distinguishes null, arrays and objects", () => {
    expect(errorsOf(null, { type: "object" })).toEqual(["config: must be of type object (got null)"]);
    expect(errorsOf([], { type: "object" })).toEqual(["config: must be of type object (got array)"]);
    expect(errorsOf({}, { type: "array" })).toEqual(["config: must be of type array (got object)"]);
    expect(errorsOf(null, { type: "null" })).toEqual([]);
  });

  it("treats integer as a kind of number, but not the reverse", () => {
    expect(errorsOf(2, { type: "integer" })).toEqual([]);
    expect(errorsOf(2, { type: "number" })).toEqual([]);
    expect(errorsOf(1.5, { type: "number" })).toEqual([]);
    expect(errorsOf(1.5, { type: "integer" })).toEqual(["config: must be of type integer (got number)"]);
  });

  it("accepts any of a list of types", () => {
    const schema = { type: ["string", "null"] };
    expect(errorsOf(null, schema)).toEqual([]);
    expect(errorsOf("x", schema)).toEqual([]);
    expect(errorsOf(5, schema)).toEqual(["config: must be of type string | null (got number)"]);
  });

  it("checks a string pattern only after the type passes", () => {
    const schema = { type: "string", pattern: "^#[0-9a-f]{6}$" };
    expect(errorsOf("#00ff00", schema)).toEqual([]);
    expect(errorsOf("red", schema)).toEqual(["config: must match pattern ^#[0-9a-f]{6}$"]);
    expect(errorsOf(7, schema)).toEqual(["config: must be of type string (got number)"]);
  });
});

describe("enum and const", () => {
  it("lists the allowed values", () => {
    const schema = { enum: ["a", "b"] };
    expect(errorsOf("a", schema)).toEqual([]);
    expect(errorsOf("c", schema)).toEqual(['config: must be one of "a", "b"']);
  });

  it("requires an exact const", () => {
    expect(errorsOf("x", { const: "x" })).toEqual([]);
    expect(errorsOf("y", { const: "x" })).toEqual(['config: must equal "x"']);
  });
});

describe("numbers", () => {
  it.each([
    [{ type: "number", minimum: 0 }, -1, "config: must be >= 0"],
    [{ type: "number", maximum: 10 }, 11, "config: must be <= 10"],
    [{ type: "number", exclusiveMinimum: 0 }, 0, "config: must be > 0"],
    [{ type: "integer", exclusiveMaximum: 10 }, 10, "config: must be < 10"],
  ])("rejects an out-of-range value: %j", (schema, value, message) => {
    expect(errorsOf(value, schema)).toEqual([message]);
  });

  it("accepts values on an inclusive bound", () => {
    expect(errorsOf(0, { type: "number", minimum: 0 })).toEqual([]);
    expect(errorsOf(10, { type: "number", maximum: 10 })).toEqual([]);
  });
});

describe("objects", () => {
  const schema = {
    type: "object",
    required: ["a"],
    properties: { a: { type: "integer" }, b: { type: "array", items: { type: "string" } } },
  };

  it("reports a missing required field at its own path", () => {
    expect(errorsOf({}, schema)).toEqual(["config.a: required field is missing"]);
  });

  it("reports nested problems with dotted keys and bracketed indexes", () => {
    expect(errorsOf({ a: 1, b: ["x", 2] }, schema)).toEqual(["config.b[1]: must be of type string (got number)"]);
  });

  it("lists required-field problems before property problems", () => {
    expect(errorsOf({ b: [1] }, schema)).toEqual([
      "config.a: required field is missing",
      "config.b[0]: must be of type string (got number)",
    ]);
  });

  it("rejects unknown keys when additionalProperties is false, as the server does", () => {
    const strict = { type: "object", properties: { a: {} }, additionalProperties: false };
    expect(errorsOf({ a: 1 }, strict)).toEqual([]);
    expect(errorsOf({ a: 1, z: 2 }, strict)).toEqual(["config.z: Extra inputs are not permitted"]);
    expect(errorsOf({ k: 1 }, { type: "object", additionalProperties: false })).toEqual([
      "config.k: Extra inputs are not permitted",
    ]);
  });

  it("validates dict values against additionalProperties, skipping named properties", () => {
    const dict = { type: "object", properties: { fixed: {} }, additionalProperties: { type: "number" } };
    expect(errorsOf({ fixed: "anything", x: 1 }, dict)).toEqual([]);
    expect(errorsOf({ fixed: "anything", y: "s" }, dict)).toEqual(["config.y: must be of type number (got string)"]);
  });

  it("ignores extra keys when additionalProperties is not mentioned", () => {
    expect(errorsOf({ a: 1, extra: true }, schema)).toEqual([]);
  });
});

describe("arrays", () => {
  it("validates every item against items", () => {
    expect(errorsOf([1, "x", 2], { type: "array", items: { type: "number" } })).toEqual([
      "config[1]: must be of type number (got string)",
    ]);
  });

  it("validates positions against prefixItems and tolerates a short array", () => {
    const tuple = { type: "array", prefixItems: [{ type: "number" }, { type: "string" }] };
    expect(errorsOf([1, 2], tuple)).toEqual(["config[1]: must be of type string (got number)"]);
    expect(errorsOf([1], tuple)).toEqual([]);
  });

  it("checks minItems and maxItems", () => {
    expect(errorsOf([1], { type: "array", minItems: 2 })).toEqual(["config: must have at least 2 items"]);
    expect(errorsOf([1, 2, 3], { type: "array", maxItems: 2 })).toEqual(["config: must have at most 2 items"]);
  });
});

describe("composition", () => {
  it("follows $ref into $defs", () => {
    const schema = {
      $defs: { Pos: { type: "object", required: ["x"], properties: { x: { type: "number" } } } },
      type: "object",
      properties: { p: { $ref: "#/$defs/Pos" } },
    };
    expect(errorsOf({ p: {} }, schema)).toEqual(["config.p.x: required field is missing"]);
    expect(errorsOf({ p: { x: 1 } }, schema)).toEqual([]);
  });

  it("throws on a $ref that has no definition", () => {
    expect(() => errorsOf(1, { $ref: "#/$defs/Nope" })).toThrow("Unresolved $ref: #/$defs/Nope");
  });

  it("passes anyOf when any branch matches and gives one generic error otherwise", () => {
    const schema = { anyOf: [{ type: "string" }, { type: "integer" }] };
    expect(errorsOf("s", schema)).toEqual([]);
    expect(errorsOf(3, schema)).toEqual([]);
    expect(errorsOf(1.5, schema)).toEqual(["config: does not match any allowed type"]);
  });

  it("handles an optional bounded number the way Pydantic emits it", () => {
    const schema = { anyOf: [{ type: "number", minimum: 0 }, { type: "null" }] };
    expect(errorsOf(null, schema)).toEqual([]);
    expect(errorsOf(2, schema)).toEqual([]);
    expect(errorsOf(-1, schema)).toEqual(["config: does not match any allowed type"]);
  });

  describe("oneOf with a discriminator", () => {
    const schema = {
      $defs: {
        A: { type: "object", required: ["kind", "n"], properties: { kind: { const: "a" }, n: { type: "integer" } } },
        B: { type: "object", required: ["kind"], properties: { kind: { const: "b" } } },
      },
      oneOf: [{ $ref: "#/$defs/A" }, { $ref: "#/$defs/B" }],
      discriminator: { propertyName: "kind", mapping: { a: "#/$defs/A", b: "#/$defs/B" } },
    };

    it("validates against the branch the tag selects, at the original path", () => {
      expect(errorsOf({ kind: "a", n: 1 }, schema)).toEqual([]);
      expect(errorsOf({ kind: "a", n: "x" }, schema)).toEqual(["config.n: must be of type integer (got string)"]);
      expect(errorsOf({ kind: "b" }, schema)).toEqual([]);
    });

    it("names an unknown or missing tag", () => {
      expect(errorsOf({ kind: "zzz" }, schema)).toEqual(['config: unknown "kind" value "zzz"']);
      expect(errorsOf({ n: 1 }, schema)).toEqual(['config: unknown "kind" value undefined']);
    });

    it("rejects data that is not an object, and a oneOf with no discriminator", () => {
      expect(errorsOf(5, schema)).toEqual(["config: does not match any allowed type"]);
      expect(errorsOf({ kind: "a" }, { oneOf: [{ type: "string" }] })).toEqual([
        "config: does not match any allowed type",
      ]);
    });
  });
});

describe("collectSchemaDiagnostics", () => {
  it("returns the path as structured segments, with numbers for array indexes", () => {
    const schema = { type: "object", properties: { b: { type: "array", items: { type: "string" } } } };
    expect(collectSchemaDiagnostics({ b: ["x", 2] }, schema)).toEqual([
      { path: ["b", 1], message: "must be of type string (got number)" },
    ]);
  });

  it("works on a schema with no $defs", () => {
    expect(collectSchemaDiagnostics("x", { type: "string" })).toEqual([]);
  });

  it("reports the root with an empty path", () => {
    expect(collectSchemaDiagnostics(1, { type: "string" })).toEqual([
      { path: [], message: "must be of type string (got number)" },
    ]);
  });
});
