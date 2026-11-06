// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  loadTabsFromStorage,
  newTabId,
  persistTabsToStorage,
  pickNextActiveOnClose,
  reorderTabs,
  selectRange,
  toggleSelection,
} from "./tab-session";

interface Tab {
  id: string;
  name?: string;
}

const tab = (id: string): Tab => ({ id });
const ids = (tabs: Tab[]) => tabs.map((t) => t.id);

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("newTabId", () => {
  it("is a short lowercase token starting with t", () => {
    expect(newTabId()).toMatch(/^t[0-9a-z]+$/);
  });

  // not asserted: uniqueness within one millisecond. only three random
  // characters follow the timestamp, so a burst of calls can collide; a tab
  // strip never creates ids that fast.
});

describe("loadTabsFromStorage", () => {
  const legacy = () => ({ tabs: [tab("legacy")], activeId: "legacy" });

  it("restores the stored tabs and the stored active tab", () => {
    localStorage.setItem("tabs", JSON.stringify([tab("a"), tab("b")]));
    localStorage.setItem("active", "b");
    expect(loadTabsFromStorage<Tab>("tabs", "active", legacy)).toEqual({
      tabs: [tab("a"), tab("b")],
      activeId: "b",
    });
  });

  it("activates the first tab when the stored active one no longer exists, or none was stored", () => {
    localStorage.setItem("tabs", JSON.stringify([tab("a"), tab("b")]));
    expect(loadTabsFromStorage<Tab>("tabs", "active", legacy).activeId).toBe("a");
    localStorage.setItem("active", "gone");
    expect(loadTabsFromStorage<Tab>("tabs", "active", legacy).activeId).toBe("a");
  });

  it.each([
    ["nothing stored", null],
    ["an empty list", "[]"],
    ["something that is not a list", '{"id":"a"}'],
    ["text that is not JSON", "not json"],
  ])("falls back to the legacy loader for %s", (_label, raw) => {
    if (raw !== null) localStorage.setItem("tabs", raw);
    expect(loadTabsFromStorage<Tab>("tabs", "active", legacy)).toEqual(legacy());
  });

  it("falls back when storage itself throws", () => {
    vi.stubGlobal("localStorage", {
      getItem() {
        throw new Error("blocked");
      },
    });
    expect(loadTabsFromStorage<Tab>("tabs", "active", legacy)).toEqual(legacy());
  });
});

describe("persistTabsToStorage", () => {
  it("writes the tabs and the active id under their keys", () => {
    persistTabsToStorage("tabs", "active", [tab("a"), tab("b")], "b");
    expect(JSON.parse(localStorage.getItem("tabs")!)).toEqual([tab("a"), tab("b")]);
    expect(localStorage.getItem("active")).toBe("b");
  });

  it("round-trips through loadTabsFromStorage", () => {
    const tabs: Tab[] = [{ id: "a", name: "First" }, { id: "b" }];
    persistTabsToStorage("tabs", "active", tabs, "b");
    expect(loadTabsFromStorage<Tab>("tabs", "active", () => ({ tabs: [], activeId: "" }))).toEqual({
      tabs,
      activeId: "b",
    });
  });

  it("swallows a storage failure such as a full quota", () => {
    vi.stubGlobal("localStorage", {
      setItem() {
        throw new Error("quota exceeded");
      },
    });
    expect(() => persistTabsToStorage("tabs", "active", [tab("a")], "a")).not.toThrow();
  });
});

describe("reorderTabs", () => {
  const tabs = [tab("a"), tab("b"), tab("c")];

  it("moves a tab to the drop index", () => {
    expect(ids(reorderTabs(tabs, "a", 2))).toEqual(["b", "c", "a"]);
    expect(ids(reorderTabs(tabs, "c", 0))).toEqual(["c", "a", "b"]);
  });

  it("is a no-op when dropped where it already is", () => {
    expect(ids(reorderTabs(tabs, "b", 1))).toEqual(["a", "b", "c"]);
  });

  it("returns the same array for an unknown id", () => {
    expect(reorderTabs(tabs, "zzz", 0)).toBe(tabs);
  });

  it("does not modify its input", () => {
    reorderTabs(tabs, "a", 2);
    expect(ids(tabs)).toEqual(["a", "b", "c"]);
  });
});

describe("selectRange", () => {
  const tabs = ["a", "b", "c", "d"].map(tab);

  it("is inclusive and works in either direction", () => {
    expect(selectRange(tabs, "b", "d")).toEqual(["b", "c", "d"]);
    expect(selectRange(tabs, "d", "b")).toEqual(["b", "c", "d"]);
    expect(selectRange(tabs, "c", "c")).toEqual(["c"]);
  });

  it("is empty when either end is not a tab", () => {
    expect(selectRange(tabs, "gone", "c")).toEqual([]);
    expect(selectRange(tabs, "b", "gone")).toEqual([]);
  });
});

describe("toggleSelection", () => {
  it("adds an id that is absent and removes one that is present", () => {
    expect(toggleSelection(["a"], "b")).toEqual(["a", "b"]);
    expect(toggleSelection(["a", "b"], "a")).toEqual(["b"]);
  });

  it("does not modify its input", () => {
    const selected = ["a"];
    toggleSelection(selected, "b");
    expect(selected).toEqual(["a"]);
  });
});

describe("pickNextActiveOnClose", () => {
  const blank = () => tab("blank");
  const abc = () => ["a", "b", "c"].map(tab);

  it("keeps the active tab when a background tab closes", () => {
    const result = pickNextActiveOnClose(abc(), 2, "a", blank);
    expect(ids(result.tabs)).toEqual(["a", "b"]);
    expect(result).toMatchObject({ nextActiveId: "a", activeChanged: false });
  });

  it("activates the tab that slides into the closed slot", () => {
    const result = pickNextActiveOnClose(abc(), 1, "b", blank);
    expect(ids(result.tabs)).toEqual(["a", "c"]);
    expect(result).toMatchObject({ nextActiveId: "c", activeChanged: true });
  });

  it("activates the new last tab when the last one closes", () => {
    const result = pickNextActiveOnClose(abc(), 2, "c", blank);
    expect(result).toMatchObject({ nextActiveId: "b", activeChanged: true });
  });

  it("opens a blank tab when the only tab closes", () => {
    const result = pickNextActiveOnClose([tab("a")], 0, "a", blank);
    expect(result.tabs).toEqual([tab("blank")]);
    expect(result).toMatchObject({ nextActiveId: "blank", activeChanged: true });
  });

  it("does not modify its input", () => {
    const tabs = abc();
    pickNextActiveOnClose(tabs, 0, "a", blank);
    expect(ids(tabs)).toEqual(["a", "b", "c"]);
  });
});
