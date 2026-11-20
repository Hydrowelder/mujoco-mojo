// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";

import { installRevealActive, lostFromView, revealOffset, revealTab, type StripBox } from "./tab-reveal";

// a strip that shows 100 to 400 on the page, scrolled by `scrollLeft`
const strip = (scrollLeft = 0): StripBox => ({ left: 100, right: 400, scrollLeft });

describe("revealOffset", () => {
  it("is null for a tab that is in view", () => {
    expect(revealOffset(strip(50), { left: 150, right: 250 })).toBeNull();
    // right up to the margin on both sides still counts as in view
    expect(revealOffset(strip(50), { left: 108, right: 392 })).toBeNull();
  });

  it("scrolls right for a tab past the end, until its end is a margin inside the strip", () => {
    // the tab ends at 520, 128 past the 392 it may reach
    expect(revealOffset(strip(0), { left: 420, right: 520 })).toBe(128);
    expect(revealOffset(strip(40), { left: 420, right: 520 })).toBe(168);
  });

  it("scrolls left for a tab before the start, until its start is a margin inside the strip", () => {
    // the tab starts at 60, 48 before the 108 it may reach
    expect(revealOffset(strip(200), { left: 60, right: 160 })).toBe(152);
  });

  it("reveals a tab only partly in view", () => {
    expect(revealOffset(strip(0), { left: 350, right: 450 })).toBe(58);
    expect(revealOffset(strip(100), { left: 80, right: 180 })).toBe(72);
  });

  it("lines up the left end of a tab wider than the strip, rather than hiding it to show the right", () => {
    // 340 wide in a strip with 284 of room, starting 200 in: its left end is what is lined up
    expect(revealOffset(strip(0), { left: 300, right: 640 })).toBe(192);
  });

  it("never asks for a position before the start of the strip", () => {
    expect(revealOffset(strip(5), { left: 0, right: 80 })).toBe(0);
  });
});

describe("lostFromView", () => {
  it("is true for a tab that was in view and is cut off by a strip that got narrower", () => {
    // shown in a strip 300 wide, which a button beside it has made 200
    expect(lostFromView(strip(0), { left: 300, right: 380 }, 300, 200)).toBe(true);
  });

  it("is false for a tab the narrower strip still shows", () => {
    expect(lostFromView(strip(0), { left: 120, right: 220 }, 300, 200)).toBe(false);
  });

  it("is false for a tab that was out of view already, which the user may have scrolled away from", () => {
    expect(lostFromView(strip(0), { left: 450, right: 520 }, 300, 200)).toBe(false);
  });

  it("is false for a strip that got wider", () => {
    expect(lostFromView(strip(0), { left: 120, right: 220 }, 300, 450)).toBe(false);
  });
});

const rect = (left: number, right: number) =>
  ({ left, right, top: 0, bottom: 0, width: right - left, height: 0, x: left, y: 0, toJSON: () => ({}) }) as DOMRect;

// a strip showing 100 to 400 with tabs whose boxes are stated, since happy-dom has no layout. `measured` is
// how many times each tab was measured, which is how often it was revealed
function build(boxes: Record<string, [number, number]>, scrollLeft = 0) {
  const el = document.createElement("div");
  el.scrollLeft = scrollLeft;
  vi.spyOn(el, "getBoundingClientRect").mockReturnValue(rect(100, 400));
  const measured: Record<string, Mock<() => DOMRect>> = {};
  for (const [id, [left, right]] of Object.entries(boxes)) {
    const tab = document.createElement("div");
    tab.dataset["tabId"] = id;
    measured[id] = vi.spyOn(tab, "getBoundingClientRect").mockReturnValue(rect(left, right));
    el.append(tab);
  }
  return { el, measured };
}

describe("revealTab", () => {
  it("scrolls the strip to the tab with that id", () => {
    const { el } = build({ a: [120, 220], b: [420, 520] });

    expect(revealTab(el, "b")).toBe(true);

    expect(el.scrollLeft).toBe(128);
  });

  it("leaves a strip alone when the tab is in view", () => {
    const { el } = build({ a: [120, 220] }, 30);

    expect(revealTab(el, "a")).toBe(true);

    expect(el.scrollLeft).toBe(30);
  });

  it("says so when there is no such tab, and leaves the strip alone", () => {
    const { el } = build({ a: [120, 220] }, 30);

    expect(revealTab(el, "missing")).toBe(false);

    expect(el.scrollLeft).toBe(30);
  });

  it("finds an id with quotes and backslashes in it", () => {
    const odd = 'a"b\\c';
    const { el } = build({ [odd]: [420, 520] });

    expect(revealTab(el, odd)).toBe(true);

    expect(el.scrollLeft).toBe(128);
  });
});

describe("installRevealActive", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // frames run at once, and a resize observer the test can fire by hand
  function stubBrowser() {
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 0;
    });
    const observers: Array<{ fire: () => void; disconnected: boolean }> = [];
    vi.stubGlobal(
      "ResizeObserver",
      class {
        private readonly entry = { fire: () => {}, disconnected: false };
        constructor(callback: () => void) {
          this.entry.fire = callback;
          observers.push(this.entry);
        }
        observe() {}
        disconnect() {
          this.entry.disconnected = true;
        }
      },
    );
    return observers;
  }

  const widthOf = (el: HTMLElement, width: number) => Object.defineProperty(el, "clientWidth", { value: width, configurable: true });

  // the id source the directive gives: a listener it calls with the id now and whenever it changes
  function ids(initial: string) {
    let listener: (id: string) => void = () => {};
    return {
      watch: (l: (id: string) => void) => {
        listener = l;
        l(initial);
      },
      change: (id: string) => listener(id),
    };
  }

  it("reveals the open tab when it first knows it, and again each time it changes", () => {
    stubBrowser();
    const { el, measured } = build({ a: [120, 220], b: [420, 520] });
    widthOf(el, 300);
    const source = ids("a");

    installRevealActive(el, source.watch, () => {});
    expect(measured["a"]).toHaveBeenCalledTimes(1);
    expect(measured["b"]).not.toHaveBeenCalled();
    source.change("b");

    expect(measured["b"]).toHaveBeenCalledTimes(1);
    expect(el.scrollLeft).toBe(128);
  });

  it("has no tab to reveal while there is no open one", () => {
    stubBrowser();
    const { el, measured } = build({ a: [120, 220] });
    widthOf(el, 300);

    installRevealActive(el, ids("").watch, () => {});

    expect(measured["a"]).not.toHaveBeenCalled();
  });

  it("reveals the open tab the first time a strip that had no width gets one", () => {
    const observers = stubBrowser();
    const { el, measured } = build({ a: [420, 520] });
    widthOf(el, 0);
    installRevealActive(el, ids("a").watch, () => {});
    expect(measured["a"]).toHaveBeenCalledTimes(1);

    widthOf(el, 300);
    observers[0]!.fire();

    expect(measured["a"]).toHaveBeenCalledTimes(2);
  });

  it("does not move a strip that already shows when it is resized", () => {
    const observers = stubBrowser();
    const { el, measured } = build({ a: [120, 220] });
    widthOf(el, 300);
    installRevealActive(el, ids("a").watch, () => {});
    expect(measured["a"]).toHaveBeenCalledTimes(1);

    widthOf(el, 450);
    observers[0]!.fire();

    expect(measured["a"]).toHaveBeenCalledTimes(1);
  });

  it("brings the open tab back when something shown beside the strip takes the room it was in", () => {
    const observers = stubBrowser();
    const { el } = build({ a: [300, 380] });
    widthOf(el, 300);
    installRevealActive(el, ids("a").watch, () => {});
    expect(el.scrollLeft).toBe(0);

    // the strip is now 100 to 300, so the tab ends 80 past it
    widthOf(el, 200);
    vi.spyOn(el, "getBoundingClientRect").mockReturnValue(rect(100, 300));
    observers[0]!.fire();

    expect(el.scrollLeft).toBe(88);
  });

  it("leaves a strip scrolled away from the open tab where it is when the strip gets narrower", () => {
    const observers = stubBrowser();
    const { el } = build({ a: [450, 520] });
    widthOf(el, 300);
    installRevealActive(el, ids("a").watch, () => {});
    el.scrollLeft = 30;

    widthOf(el, 200);
    vi.spyOn(el, "getBoundingClientRect").mockReturnValue(rect(100, 300));
    observers[0]!.fire();

    expect(el.scrollLeft).toBe(30);
  });

  it("stops watching for a resize when it is cleaned up", () => {
    const observers = stubBrowser();
    const { el } = build({ a: [120, 220] });
    widthOf(el, 300);
    let undo = () => {};

    installRevealActive(el, ids("a").watch, (fn) => (undo = fn));
    expect(observers[0]!.disconnected).toBe(false);
    undo();

    expect(observers[0]!.disconnected).toBe(true);
  });
});
