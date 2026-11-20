// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_SIGNAL_SEARCH,
  loadSignalSearch,
  nextSearchMode,
  saveSignalSearch,
} from "./signal-search";

// replaces localStorage as a whole: happy-dom keeps handing out the methods it
// returned first, so a spy on the prototype would do nothing
function stubStorage(fail: { read?: boolean; write?: boolean } = {}): Map<string, string> {
  const data = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => {
      if (fail.read) throw new Error("storage refused a read");
      return data.get(key) ?? null;
    },
    setItem: (key: string, value: string) => {
      if (fail.write) throw new Error("storage refused a write");
      data.set(key, String(value));
    },
  });
  return data;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("nextSearchMode", () => {
  it("cycles between regex and text", () => {
    expect(nextSearchMode("regex")).toBe("text");
    expect(nextSearchMode("text")).toBe("regex");
    expect(nextSearchMode(nextSearchMode("regex"))).toBe("regex");
  });
});

describe("loadSignalSearch", () => {
  it("is regex with no metadata search when nothing is saved", () => {
    stubStorage();
    expect(loadSignalSearch()).toEqual({ mode: "regex", metadata: false });
    expect(loadSignalSearch()).toEqual(DEFAULT_SIGNAL_SEARCH);
  });

  it("gives back what was saved", () => {
    stubStorage();
    saveSignalSearch({ mode: "text", metadata: true });
    expect(loadSignalSearch()).toEqual({ mode: "text", metadata: true });
  });

  it("takes the defaults for what is missing or not one of the choices", () => {
    const data = stubStorage();
    data.set("mojo-signal-search", JSON.stringify({ mode: "fuzzy", metadata: "yes" }));
    expect(loadSignalSearch()).toEqual({ mode: "regex", metadata: false });
    data.set("mojo-signal-search", JSON.stringify({ metadata: true }));
    expect(loadSignalSearch()).toEqual({ mode: "regex", metadata: true });
  });

  it.each(["not json", "null", "7", '"text"', "[]"])("takes the defaults for saved text that is %s", (saved) => {
    stubStorage().set("mojo-signal-search", saved);
    expect(loadSignalSearch()).toEqual({ mode: "regex", metadata: false });
  });

  it("does not throw when storage refuses to read", () => {
    stubStorage({ read: true });
    expect(loadSignalSearch()).toEqual({ mode: "regex", metadata: false });
  });
});

describe("saveSignalSearch", () => {
  it("does not throw when storage refuses to write", () => {
    stubStorage({ write: true });
    expect(() => saveSignalSearch({ mode: "text", metadata: true })).not.toThrow();
  });
});
