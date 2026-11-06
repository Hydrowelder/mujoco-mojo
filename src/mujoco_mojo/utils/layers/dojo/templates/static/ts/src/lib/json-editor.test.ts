import { describe, expect, it } from "vitest";

import { EditorState, json } from "./codemirror";
import { jsonPathAt, jsonRangeForPath } from "./json-editor";

const stateOf = (doc: string) => EditorState.create({ doc, extensions: [json()] });

// a position a few characters into `needle`, so it is inside the token
const inside = (doc: string, needle: string) => doc.indexOf(needle) + 1;

const DOC = '{"yAxes": {"ax1": {"color": "#fff"}}, "items": [1, {"k": 2}], "n": null}';

describe("jsonPathAt", () => {
  const path = (doc: string, needle: string) => jsonPathAt(stateOf(doc), inside(doc, needle));

  it("names the keys enclosing a position, outermost first", () => {
    expect(path(DOC, '"color"')).toEqual(["yAxes", "ax1", "color"]);
    expect(path(DOC, "#fff")).toEqual(["yAxes", "ax1", "color"]);
    expect(path(DOC, '"ax1"')).toEqual(["yAxes", "ax1"]);
    expect(path(DOC, '"yAxes"')).toEqual(["yAxes"]);
  });

  it("uses an empty string for each array step, since the index does not matter", () => {
    expect(path(DOC, "1,")).toEqual(["items", ""]);
    expect(path(DOC, '"k"')).toEqual(["items", "", "k"]);
  });

  it("is empty outside any key", () => {
    expect(jsonPathAt(stateOf(DOC), 0)).toEqual([]);
  });

  it("decodes escapes in a key", () => {
    const doc = '{"a\\"b": 1}';
    expect(jsonPathAt(stateOf(doc), doc.indexOf("1"))).toEqual(['a"b']);
  });
});

describe("jsonRangeForPath", () => {
  const textAt = (doc: string, p: (string | number)[]) => {
    const range = jsonRangeForPath(stateOf(doc), p);
    return range && doc.slice(range.from, range.to);
  };

  it("spans the whole document for an empty path", () => {
    expect(jsonRangeForPath(stateOf(DOC), [])).toEqual({ from: 0, to: DOC.length });
  });

  it("finds the value under a chain of keys", () => {
    expect(textAt(DOC, ["yAxes", "ax1", "color"])).toBe('"#fff"');
    expect(textAt(DOC, ["yAxes", "ax1"])).toBe('{"color": "#fff"}');
    expect(textAt(DOC, ["n"])).toBe("null");
  });

  it("finds an array element by index, counting values and not punctuation", () => {
    expect(textAt(DOC, ["items", 0])).toBe("1");
    expect(textAt(DOC, ["items", 1])).toBe('{"k": 2}');
    expect(textAt(DOC, ["items", 1, "k"])).toBe("2");
  });

  it("matches a key by its decoded text", () => {
    expect(textAt('{"a\\"b": 7}', ['a"b'])).toBe("7");
  });

  it("returns null when the path does not resolve", () => {
    expect(textAt(DOC, ["nope"])).toBeNull();
    expect(textAt(DOC, ["yAxes", "nope", "color"])).toBeNull();
    // an index into an object, a key into an array, and an index past the end
    expect(textAt(DOC, ["yAxes", 0])).toBeNull();
    expect(textAt(DOC, ["items", "k"])).toBeNull();
    expect(textAt(DOC, ["items", 5])).toBeNull();
    // stepping into something that is not a container
    expect(textAt(DOC, ["n", "x"])).toBeNull();
  });

  it("returns null for a key in an empty document", () => {
    expect(jsonRangeForPath(stateOf(""), ["a"])).toBeNull();
  });
});
