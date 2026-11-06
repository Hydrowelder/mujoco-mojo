import { beforeEach, describe, expect, it } from "vitest";

import {
  collapseColorAlias,
  fieldRangeMessage,
  filterSettingsSections,
  findSettingsField,
  findSettingsGroup,
  findSettingsListField,
  isFieldOutOfRange,
  isHexColor,
  looksLikeHttpUrl,
  nearestColorName,
  parseSettingsSchema,
  resolveColorHex,
  serializeSettings,
  type SettingsField,
  type SettingsGroup,
  type SettingsSchema,
} from "./settings-panel";

// shaped like the schema the Dojo serves from GET /settings (Pydantic's
// model_json_schema() plus the x-widget / x-icon / x-enum-descriptions
// extensions), cut down to one of each construct the parser handles
const schema: SettingsSchema = {
  type: "object",
  properties: {
    general: { $ref: "#/$defs/General" },
    dojo: { $ref: "#/$defs/Dojo" },
    tags: { type: "object", title: "Tags", additionalProperties: { type: "string" } },
  },
  $defs: {
    General: {
      type: "object",
      title: "General",
      description: "Options for every command.",
      "x-icon": '<path d="M0 0"/>',
      properties: {
        verbose: {
          type: "integer",
          title: "Verbosity",
          description: "How chatty.",
          minimum: 0,
          maximum: 3,
          default: 0,
        },
        default_host: { type: "string", default: "127.0.0.1" },
        debug: { type: "boolean", default: false },
        mode: { $ref: "#/$defs/Mode", description: "How to run." },
        chime: {
          anyOf: [{ type: "string", format: "uri" }, { type: "string", format: "path" }, { type: "null" }],
          title: "Chime",
        },
        limit: { anyOf: [{ type: "integer", minimum: 1 }, { type: "null" }], title: "Limit" },
        accent: { type: "string", "x-widget": "color", title: "Accent" },
        password: { type: "string", writeOnly: true },
        nested: { $ref: "#/$defs/Nested" },
      },
    },
    Nested: { type: "object", title: "Nested", properties: { depth: { type: "integer", title: "Depth" } } },
    Mode: {
      type: "string",
      title: "Mode",
      description: "A mode.",
      enum: ["fast", "slow"],
      "x-enum-descriptions": { fast: "Quick.", slow: "Careful." },
    },
    Dojo: {
      type: "object",
      title: "Dojo",
      properties: { models: { type: "array", title: "Models", items: { $ref: "#/$defs/ModelEntry" } } },
    },
    ModelEntry: {
      type: "object",
      title: "Model",
      properties: {
        name: { type: "string", title: "Name" },
        kind: { $ref: "#/$defs/Mode" },
        key: { type: "string", title: "Key", writeOnly: true },
      },
    },
  },
};

const values = () => ({
  general: {
    verbose: 2,
    default_host: "0.0.0.0",
    debug: true,
    mode: "slow",
    chime: "https://x.test/a.mp3",
    limit: null,
    accent: "EMERALD_500",
    password: "leaked",
    nested: { depth: 4 },
  },
  dojo: { models: [{ name: "gpt", kind: "fast", key: "****" }] },
  tags: { a: "1", n: 2, flag: true },
});

const valueMeta = { "general.chime": { is_url: true } };

const fieldOf = (group: SettingsGroup, key: string) => group.fields.find((f) => f.key === key)!;

let groups: SettingsGroup[];
let general: SettingsGroup;

beforeEach(() => {
  groups = parseSettingsSchema(schema, values(), valueMeta);
  general = groups[0]!;
});

describe("parseSettingsSchema", () => {
  it("makes one group per top-level property, in schema order", () => {
    expect(groups.map((g) => g.key)).toEqual(["general", "dojo", "tags"]);
  });

  it("reads a group's title, description and icon, falling back to the key", () => {
    expect(general).toMatchObject({
      path: "general",
      title: "General",
      description: "Options for every command.",
      icon: '<path d="M0 0"/>',
    });
    expect(groups[1]).toMatchObject({ title: "Dojo", description: "", icon: "" });
  });

  it("nests an object property as a subgroup with a dotted path", () => {
    expect(general.subgroups.map((s) => s.path)).toEqual(["general.nested"]);
    expect(general.subgroups[0]!.fields[0]).toMatchObject({ path: "general.nested.depth", value: 4 });
  });

  it("never renders a write-only property, even when the response carries its value", () => {
    expect(general.fields.map((f) => f.key)).not.toContain("password");
  });

  it("builds a dict group, inferring each entry's value type", () => {
    expect(groups[2]!.fields).toEqual([]);
    expect(groups[2]!.dictField?.entries).toEqual([
      { key: "a", valueType: "string", value: "1" },
      { key: "n", valueType: "number", value: 2 },
      { key: "flag", valueType: "boolean", value: true },
    ]);
  });

  it("copes with a response that has no values at all", () => {
    const empty = parseSettingsSchema(schema, {}, {});
    expect(fieldOf(empty[0]!, "verbose").value).toBeNull();
    expect(empty[1]!.listFields[0]!.items).toEqual([]);
    expect(empty[2]!.dictField?.entries).toEqual([]);
  });

  describe("field widgets", () => {
    it("reads an integer as a number with its bounds, default and description", () => {
      expect(fieldOf(general, "verbose")).toMatchObject({
        path: "general.verbose",
        title: "Verbosity",
        description: "How chatty.",
        widget: "number",
        value: 2,
        default: 0,
        minimum: 0,
        maximum: 3,
        nullable: false,
      });
    });

    it("falls back to the key for a missing title and to null for a missing default", () => {
      expect(fieldOf(general, "default_host")).toMatchObject({
        title: "default_host",
        widget: "text",
        value: "0.0.0.0",
        default: "127.0.0.1",
      });
      expect(fieldOf(general, "mode").default).toBeNull();
    });

    it("keeps a false default as false", () => {
      expect(fieldOf(general, "debug")).toMatchObject({ widget: "toggle", value: true, default: false });
    });

    it("reads an enum reference as a select, with the field's own description winning", () => {
      expect(fieldOf(general, "mode")).toMatchObject({
        widget: "select",
        title: "Mode",
        description: "How to run.",
        value: "slow",
        enumOptions: ["fast", "slow"],
        enumDescriptions: { fast: "Quick.", slow: "Careful." },
      });
    });

    it("reads an optional uri as a nullable url and takes isUrl from the server's metadata", () => {
      expect(fieldOf(general, "chime")).toMatchObject({ widget: "url", nullable: true, isUrl: true });
      const withoutMeta = parseSettingsSchema(schema, values(), {})[0]!;
      expect(fieldOf(withoutMeta, "chime").isUrl).toBe(false);
    });

    it("reads an optional number as nullable, taking the bound from the number branch", () => {
      expect(fieldOf(general, "limit")).toMatchObject({ widget: "number", nullable: true, minimum: 1, value: null });
    });

    it("reads an x-widget color as a nullable color", () => {
      expect(fieldOf(general, "accent")).toMatchObject({ widget: "color", nullable: true, value: "EMERALD_500" });
    });
  });

  describe("list fields", () => {
    const models = () => groups[1]!.listFields[0]!;

    it("builds a row per stored item and a blank template", () => {
      expect(models()).toMatchObject({ path: "dojo.models", key: "models", itemTitle: "Model" });
      expect(models().items).toHaveLength(1);
      expect(models().itemTemplate.map((f) => f.key)).toEqual(["name", "kind", "key"]);
    });

    it("gives each row its own synthetic paths, distinct from the template's", () => {
      const row = models().items[0]!.fields;
      expect(row[0]!.path).toMatch(/^dojo\.models\..+\.name$/);
      expect(row[0]!.path).not.toBe(models().itemTemplate[0]!.path);
      expect(models().itemTemplate[0]!.path).toBe("dojo.models.__template__.name");
    });

    it("masks a secret in a row but remembers the original", () => {
      const key = models().items[0]!.fields.find((f) => f.key === "key")!;
      expect(key).toMatchObject({ widget: "secret", value: "", secretOriginal: "****" });
    });
  });
});

describe("serializeSettings", () => {
  it("rebuilds the nested settings from the form state", () => {
    expect(serializeSettings(groups)).toEqual({
      general: {
        verbose: 2,
        default_host: "0.0.0.0",
        debug: true,
        mode: "slow",
        chime: "https://x.test/a.mp3",
        limit: null,
        accent: "EMERALD_500",
        nested: { depth: 4 },
      },
      dojo: { models: [{ name: "gpt", kind: "fast", key: "****" }] },
      tags: { a: "1", n: 2, flag: true },
    });
  });

  it("never sends back a write-only property that was not rendered", () => {
    expect(serializeSettings(groups).general).not.toHaveProperty("password");
  });

  it("turns an emptied nullable field into null, but leaves an emptied plain text field empty", () => {
    fieldOf(general, "chime").value = "";
    fieldOf(general, "limit").value = "";
    fieldOf(general, "default_host").value = "";
    expect(serializeSettings(groups).general).toMatchObject({ chime: null, limit: null, default_host: "" });
  });

  it("sends a typed secret, and the original mask when the input was left blank", () => {
    const key = groups[1]!.listFields[0]!.items[0]!.fields.find((f) => f.key === "key")!;
    expect(serializeSettings(groups).dojo).toEqual({ models: [expect.objectContaining({ key: "****" })] });
    key.value = "sk-new";
    expect(serializeSettings(groups).dojo).toEqual({ models: [expect.objectContaining({ key: "sk-new" })] });
  });

  it("reflects edits to dict entries and removed rows", () => {
    groups[2]!.dictField!.entries.splice(0, 1);
    groups[1]!.listFields[0]!.items.pop();
    const out = serializeSettings(groups);
    expect(out.tags).toEqual({ n: 2, flag: true });
    expect(out.dojo).toEqual({ models: [] });
  });
});

describe("lookups", () => {
  it("finds a field by its dotted path, including in subgroups and list rows", () => {
    expect(findSettingsField(groups, "general.verbose")).toBe(fieldOf(general, "verbose"));
    expect(findSettingsField(groups, "general.nested.depth")).toBe(general.subgroups[0]!.fields[0]);
    const rowField = groups[1]!.listFields[0]!.items[0]!.fields[0]!;
    expect(findSettingsField(groups, rowField.path)).toBe(rowField);
    expect(findSettingsField(groups, "general.nope")).toBeNull();
  });

  it("finds groups at any depth", () => {
    expect(findSettingsGroup(groups, "general")).toBe(general);
    expect(findSettingsGroup(groups, "general.nested")).toBe(general.subgroups[0]);
    expect(findSettingsGroup(groups, "nope")).toBeNull();
  });

  it("finds a list field by path", () => {
    expect(findSettingsListField(groups, "dojo.models")).toBe(groups[1]!.listFields[0]);
    expect(findSettingsListField(groups, "dojo.nope")).toBeNull();
  });
});

describe("range checks", () => {
  const numberField = (over: Partial<SettingsField> = {}): SettingsField => ({
    path: "x",
    key: "x",
    title: "X",
    description: "",
    widget: "number",
    default: 0,
    value: 1,
    nullable: false,
    isUrl: false,
    minimum: 0,
    maximum: 3,
    ...over,
  });

  it("flags a number outside its bounds, inclusive at the edges", () => {
    expect(isFieldOutOfRange(numberField({ value: 5 }))).toBe(true);
    expect(isFieldOutOfRange(numberField({ value: -1 }))).toBe(true);
    expect(isFieldOutOfRange(numberField({ value: 0 }))).toBe(false);
    expect(isFieldOutOfRange(numberField({ value: 3 }))).toBe(false);
  });

  it("checks only the bounds that exist", () => {
    expect(isFieldOutOfRange(numberField({ value: -50, minimum: undefined }))).toBe(false);
    expect(isFieldOutOfRange(numberField({ value: 50, maximum: undefined }))).toBe(false);
  });

  it("ignores fields that are not numbers or have no number yet", () => {
    expect(isFieldOutOfRange(numberField({ widget: "text", value: 99 }))).toBe(false);
    expect(isFieldOutOfRange(numberField({ value: null }))).toBe(false);
    expect(isFieldOutOfRange(numberField({ value: "9" }))).toBe(false);
  });

  it("words the message for whichever bounds exist", () => {
    expect(fieldRangeMessage(numberField())).toBe("Must be between 0 and 3");
    expect(fieldRangeMessage(numberField({ maximum: undefined }))).toBe("Must be at least 0");
    expect(fieldRangeMessage(numberField({ minimum: undefined }))).toBe("Must be at most 3");
    expect(fieldRangeMessage(numberField({ minimum: undefined, maximum: undefined }))).toBe("");
  });
});

describe("filterSettingsSections", () => {
  const fieldKeys = (list: SettingsGroup[]) => list.map((g) => g.fields.map((f) => f.key));

  it("passes the list through untouched for an empty or blank query", () => {
    expect(filterSettingsSections(groups, "")).toBe(groups);
    expect(filterSettingsSections(groups, "   ")).toBe(groups);
  });

  it("keeps only the matching fields of a group, case-insensitively and trimmed", () => {
    const out = filterSettingsSections(groups, "  VERB ");
    expect(out.map((g) => g.key)).toEqual(["general"]);
    expect(fieldKeys(out)).toEqual([["verbose"]]);
    expect(out[0]!.subgroups).toEqual([]);
  });

  it("matches on a field's description as well as its title and key", () => {
    expect(fieldKeys(filterSettingsSections(groups, "how to run"))).toEqual([["mode"]]);
    expect(fieldKeys(filterSettingsSections(groups, "default_host"))).toEqual([["default_host"]]);
  });

  it("returns a group whole when its own title or description matches", () => {
    const out = filterSettingsSections(groups, "general");
    expect(out).toHaveLength(1);
    expect(out[0]).toBe(general);
  });

  it("keeps a group alive for a match that is only in a subgroup", () => {
    const out = filterSettingsSections(groups, "depth");
    expect(out[0]!.fields).toEqual([]);
    expect(out[0]!.subgroups.map((s) => s.fields.map((f) => f.key))).toEqual([["depth"]]);
  });

  it("drops groups with no match and does not modify the originals", () => {
    expect(filterSettingsSections(groups, "zzz")).toEqual([]);
    filterSettingsSections(groups, "verb");
    expect(general.fields.length).toBeGreaterThan(1);
  });
});

describe("color helpers", () => {
  const choices = { EMERALD_500: "#10b981", RED_500: "#ef4444", BLUE_500: "#3b82f6" };

  describe("isHexColor", () => {
    it.each(["#10b981", "#10B981", "#000000"])("accepts %s", (value) => {
      expect(isHexColor(value)).toBe(true);
    });

    it.each(["#10b98", "10b981", "#10b98g", "#10b9811", "", "EMERALD_500"])("rejects %j", (value) => {
      expect(isHexColor(value)).toBe(false);
    });

    it.each([null, undefined, 5, {}])("rejects the non-string %j", (value) => {
      expect(isHexColor(value)).toBe(false);
    });
  });

  describe("resolveColorHex", () => {
    it("resolves a name in any case to its hex", () => {
      expect(resolveColorHex("EMERALD_500", choices)).toBe("#10b981");
      expect(resolveColorHex("emerald_500", choices)).toBe("#10b981");
    });

    it("uppercases a hex code", () => {
      expect(resolveColorHex("#abcdef", choices)).toBe("#ABCDEF");
    });

    it("returns null for blanks, unknown names and incomplete hex", () => {
      for (const value of [null, undefined, "", "nope", "#ABCDE"]) {
        expect(resolveColorHex(value, choices)).toBeNull();
      }
    });
  });

  describe("collapseColorAlias", () => {
    it("turns a hex that matches a named swatch into the name, ignoring case", () => {
      expect(collapseColorAlias("#10B981", choices)).toBe("EMERALD_500");
      expect(collapseColorAlias("#10b981", choices)).toBe("EMERALD_500");
    });

    it("uppercases a hex that matches no swatch", () => {
      expect(collapseColorAlias("#12345a", choices)).toBe("#12345A");
    });

    it("passes names, partial hex and empty values through unchanged", () => {
      expect(collapseColorAlias("EMERALD_500", choices)).toBe("EMERALD_500");
      expect(collapseColorAlias("#12", choices)).toBe("#12");
      expect(collapseColorAlias(null, choices)).toBeNull();
      expect(collapseColorAlias(undefined, choices)).toBeUndefined();
    });
  });

  describe("nearestColorName", () => {
    it("picks the closest swatch by RGB distance", () => {
      expect(nearestColorName("#ee4040", choices)).toBe("RED_500");
      expect(nearestColorName("#0000ff", choices)).toBe("BLUE_500");
    });

    it("returns the swatch itself for its own hex", () => {
      expect(nearestColorName("#10b981", choices)).toBe("EMERALD_500");
    });

    it("returns an empty string when there are no choices", () => {
      expect(nearestColorName("#ffffff", {})).toBe("");
    });
  });
});

describe("looksLikeHttpUrl", () => {
  it.each(["https://example.com/a.mp3", "http://localhost:8000", "HTTP://EXAMPLE.COM"])("accepts %s", (value) => {
    expect(looksLikeHttpUrl(value)).toBe(true);
  });

  it.each(["ftp://example.com/a.mp3", "/home/me/chime.mp3", "C:\\sounds\\chime.mp3", "mailto:a@b.c", "", "not a url"])(
    "rejects %j",
    (value) => {
      expect(looksLikeHttpUrl(value)).toBe(false);
    },
  );

  it.each([null, undefined, 5, {}])("rejects the non-string %j", (value) => {
    expect(looksLikeHttpUrl(value)).toBe(false);
  });
});
