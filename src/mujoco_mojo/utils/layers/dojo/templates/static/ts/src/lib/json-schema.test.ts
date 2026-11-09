import { describe, expect, it } from "vitest";

import {
  describeDefField,
  describeEnumValue,
  describeFilterField,
  describeSchemaPath,
  resolveSchemaPath,
  type JsonSchemaNode,
} from "./json-schema";

// shaped like the schema Pydantic emits for PlotConfig, cut down to the
// constructs the helpers walk
const schema: JsonSchemaNode = {
  $defs: {
    GridMode: {
      type: "string",
      description: "Which grid lines to draw.",
      "x-enum-descriptions": { all: "Major and minor tick grid lines.", major: "Major tick grid lines only." },
    },
    Note: { type: "object", properties: { text: { type: "string", description: "The note text." } } },
    YAxisConfig: {
      type: "object",
      properties: {
        color: { type: "string", description: "Axis color." },
        filters: {
          type: "array",
          items: {
            discriminator: {
              propertyName: "type",
              mapping: { low_pass: "#/$defs/LowPassFilter", median: "#/$defs/RollingMedianFilter" },
            },
          },
        },
      },
    },
    LowPassFilter: { type: "object", properties: { cutoff: { type: "number", description: "Cutoff frequency." } } },
    RollingMedianFilter: { type: "object", properties: { window: { type: "integer", description: "Window size." } } },
    VlineShape: { type: "object", properties: { x0: { type: "number", description: "X coordinate of the line." } } },
    RectShape: { type: "object", properties: { x0: { type: "number", description: "Left x coordinate." } } },
  },
  type: "object",
  properties: {
    title: { type: "string", description: "Plot title." },
    grid: { $ref: "#/$defs/GridMode", description: "Grid override." },
    gridPlain: { $ref: "#/$defs/GridMode" },
    gridWrapped: { allOf: [{ $ref: "#/$defs/GridMode" }], description: "Wrapped grid." },
    yAxes: { type: "object", additionalProperties: { $ref: "#/$defs/YAxisConfig" } },
    annotations: { type: "array", items: { $ref: "#/$defs/Note" } },
    shapes: { type: "array", items: { oneOf: [{ $ref: "#/$defs/VlineShape" }, { $ref: "#/$defs/RectShape" }] } },
  },
};

describe("resolveSchemaPath", () => {
  it("returns null when there is no schema yet", () => {
    expect(resolveSchemaPath(null, ["title"])).toBeNull();
  });

  it("returns the root itself for an empty path", () => {
    expect(resolveSchemaPath(schema, [])).toBe(schema);
  });

  it("returns a plain property", () => {
    expect(resolveSchemaPath(schema, ["title"])).toMatchObject({ type: "string", description: "Plot title." });
  });

  it("returns null for a path the schema does not cover", () => {
    expect(resolveSchemaPath(schema, ["nope"])).toBeNull();
    expect(resolveSchemaPath(schema, ["title", "deeper"])).toBeNull();
  });

  it("follows a $ref and lets the field's own description win over the target's", () => {
    expect(resolveSchemaPath(schema, ["grid"])?.description).toBe("Grid override.");
    expect(resolveSchemaPath(schema, ["gridPlain"])?.description).toBe("Which grid lines to draw.");
  });

  it("unwraps a single-item allOf the same way", () => {
    const node = resolveSchemaPath(schema, ["gridWrapped"]);
    expect(node?.description).toBe("Wrapped grid.");
    expect(node?.["x-enum-descriptions"]).toHaveProperty("all");
  });

  it("steps into a dict value whatever the key", () => {
    expect(resolveSchemaPath(schema, ["yAxes", "some signal", "color"])?.description).toBe("Axis color.");
  });

  it("steps into an array item whatever the index", () => {
    expect(resolveSchemaPath(schema, ["annotations", "", "text"])?.description).toBe("The note text.");
    expect(resolveSchemaPath(schema, ["annotations", "3", "text"])?.description).toBe("The note text.");
  });
});

describe("describeSchemaPath", () => {
  it("returns the description, or an empty string when there is none", () => {
    expect(describeSchemaPath(schema, ["title"])).toBe("Plot title.");
    expect(describeSchemaPath(schema, ["yAxes"])).toBe("");
    expect(describeSchemaPath(schema, ["nope"])).toBe("");
    expect(describeSchemaPath(null, ["title"])).toBe("");
  });

  it("takes the first union branch that has the property, which is why describeDefField exists", () => {
    expect(describeSchemaPath(schema, ["shapes", "0", "x0"])).toBe("X coordinate of the line.");
  });
});

describe("describeDefField", () => {
  it("reads a field off a named definition", () => {
    expect(describeDefField(schema, "RectShape", "x0")).toBe("Left x coordinate.");
    expect(describeDefField(schema, "VlineShape", "x0")).toBe("X coordinate of the line.");
  });

  it("returns an empty string for an unknown definition, field or schema", () => {
    expect(describeDefField(schema, "Nope", "x0")).toBe("");
    expect(describeDefField(schema, "RectShape", "nope")).toBe("");
    expect(describeDefField(null, "RectShape", "x0")).toBe("");
  });
});

describe("describeEnumValue", () => {
  it("returns the description of one enum member", () => {
    expect(describeEnumValue(schema, ["grid"], "all")).toBe("Major and minor tick grid lines.");
    expect(describeEnumValue(schema, ["gridWrapped"], "major")).toBe("Major tick grid lines only.");
  });

  it("returns an empty string for an unknown member, a non-enum field or no schema", () => {
    expect(describeEnumValue(schema, ["grid"], "nope")).toBe("");
    expect(describeEnumValue(schema, ["title"], "all")).toBe("");
    expect(describeEnumValue(null, ["grid"], "all")).toBe("");
  });
});

describe("describeFilterField", () => {
  it("reads the filter class from the discriminator mapping, not from the type name", () => {
    expect(describeFilterField(schema, "low_pass", "cutoff")).toBe("Cutoff frequency.");
    // the type is "median" but the class is RollingMedianFilter
    expect(describeFilterField(schema, "median", "window")).toBe("Window size.");
  });

  it("returns an empty string for an unknown type, field or schema", () => {
    expect(describeFilterField(schema, "nope", "window")).toBe("");
    expect(describeFilterField(schema, "median", "nope")).toBe("");
    expect(describeFilterField(null, "median", "window")).toBe("");
  });
});
