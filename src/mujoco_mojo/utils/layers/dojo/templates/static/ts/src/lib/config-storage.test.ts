import { describe, expect, it } from "vitest";

import { parseRawConfig, parseSavedConfig, parseSavedHistory } from "./config-storage";

describe("parseSavedConfig", () => {
  it("reads a saved config", () => {
    const raw = JSON.stringify({ title: "T", plotType: "line", refFrame: ["q", "o"] });
    expect(parseSavedConfig(raw)).toEqual({ title: "T", plotType: "line", refFrame: ["q", "o"] });
  });

  it("leaves a config with no reference frame as it is", () => {
    expect(parseSavedConfig('{"title":"T"}')).toEqual({ title: "T" });
  });

  it("resets a reference frame from before frames were pairs to the world frame", () => {
    expect(parseSavedConfig('{"title":"T","refFrame":"body"}')).toEqual({ title: "T", refFrame: [null, null] });
    expect(parseSavedConfig('{"title":"T","refFrame":null}')).toEqual({ title: "T", refFrame: [null, null] });
  });

  it("keeps a valid world frame", () => {
    expect(parseSavedConfig('{"refFrame":[null,null]}')).toEqual({ refFrame: [null, null] });
  });

  it("is null for text that is not json", () => {
    expect(parseSavedConfig("{not json")).toBeNull();
    expect(parseSavedConfig("")).toBeNull();
  });

  it("is null for json a frame cannot be read from", () => {
    expect(parseSavedConfig("null")).toBeNull();
  });

  it("passes other json values through as read", () => {
    expect(parseSavedConfig("5")).toBe(5);
    expect(parseSavedConfig('"text"')).toBe("text");
    expect(parseSavedConfig("[1,2]")).toEqual([1, 2]);
  });
});

describe("parseSavedHistory", () => {
  it("reads the stack and the index", () => {
    expect(parseSavedHistory('{"stack":["a","b"],"index":1}')).toEqual({ stack: ["a", "b"], index: 1 });
  });

  it("reads an index at either end of the stack", () => {
    expect(parseSavedHistory('{"stack":["a","b"],"index":0}')).toEqual({ stack: ["a", "b"], index: 0 });
    expect(parseSavedHistory('{"stack":["a"],"index":0}')).toEqual({ stack: ["a"], index: 0 });
  });

  it("leaves out anything else the saved object held", () => {
    const out = parseSavedHistory('{"stack":["a"],"index":0,"extra":true}');
    expect(Object.keys(out!).sort()).toEqual(["index", "stack"]);
  });

  it("is null for text that is not json", () => {
    expect(parseSavedHistory("{not json")).toBeNull();
    expect(parseSavedHistory("")).toBeNull();
  });

  it("is null for json that is not an object with a history in it", () => {
    for (const raw of ["null", "5", '"text"', "[]", "{}", "true"]) {
      expect(parseSavedHistory(raw), raw).toBeNull();
    }
  });

  it("is null when a part is missing", () => {
    expect(parseSavedHistory('{"stack":["a"]}')).toBeNull();
    expect(parseSavedHistory('{"index":0}')).toBeNull();
  });

  it("is null for a stack that is not a list of snapshots, or is empty", () => {
    expect(parseSavedHistory('{"stack":"a","index":0}')).toBeNull();
    expect(parseSavedHistory('{"stack":{"0":"a"},"index":0}')).toBeNull();
    expect(parseSavedHistory('{"stack":[],"index":0}')).toBeNull();
    expect(parseSavedHistory('{"stack":["a",1],"index":0}')).toBeNull();
    expect(parseSavedHistory('{"stack":[null],"index":0}')).toBeNull();
  });

  it("is null for an index that is not a place in the stack", () => {
    for (const index of ["-1", "2", "1.5", '"1"', "null", "true", "[1]"]) {
      expect(parseSavedHistory(`{"stack":["a","b"],"index":${index}}`), index).toBeNull();
    }
  });
});

describe("parseRawConfig", () => {
  it("is the config for json that describes an object", () => {
    expect(parseRawConfig('{"title":"T"}')).toEqual({ json: true, config: { title: "T" } });
    expect(parseRawConfig("{}")).toEqual({ json: true, config: {} });
  });

  it("is not json for text that does not parse", () => {
    expect(parseRawConfig("{not json")).toEqual({ json: false });
    expect(parseRawConfig("")).toEqual({ json: false });
  });

  it("is json with no config for values that are not objects", () => {
    expect(parseRawConfig("null")).toEqual({ json: true, config: null });
    expect(parseRawConfig("5")).toEqual({ json: true, config: null });
    expect(parseRawConfig("0")).toEqual({ json: true, config: null });
    expect(parseRawConfig('"text"')).toEqual({ json: true, config: null });
    expect(parseRawConfig("true")).toEqual({ json: true, config: null });
  });

  it("takes an array as an object, since it is one", () => {
    expect(parseRawConfig("[1]")).toEqual({ json: true, config: [1] });
  });
});
