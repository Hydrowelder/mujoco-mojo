// @vitest-environment happy-dom
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { PINNED_KEY } from "./lib/sensai";

// the component object itself, not a copy of its logic: its methods are called
// on a real `sensai()` with nothing but the browser storage behind it
type SensAI = {
  open: boolean;
  pinned: boolean;
  toggle(): void;
  close(): void;
  dismiss(): void;
  togglePin(): void;
  isLastUserMessage(i: number): boolean;
  init(): Promise<void>;
  $watch: () => void;
  messages: Array<{ role: string }>;
};

let make: () => SensAI;

beforeAll(async () => {
  vi.stubGlobal("Alpine", { store: () => ({}) });
  await import("./sensai");
  make = (window as unknown as { sensai: () => SensAI }).sensai;
});

beforeEach(() => {
  localStorage.clear();
});

describe("the SensAI window", () => {
  it("closes for a click elsewhere or Escape when it is not pinned", () => {
    const s = make();
    s.open = true;
    s.dismiss();
    expect(s.open).toBe(false);
  });

  it("stays open for a click elsewhere or Escape when it is pinned", () => {
    const s = make();
    s.open = true;
    s.pinned = true;
    s.dismiss();
    expect(s.open).toBe(true);
  });

  it("can still be closed on purpose while pinned, by its own button", () => {
    const s = make();
    s.open = true;
    s.pinned = true;
    s.close();
    expect(s.open).toBe(false);
  });

  it("closes for a click elsewhere again once it is unpinned", () => {
    const s = make();
    s.open = true;
    s.pinned = true;
    s.dismiss();
    s.togglePin();
    s.dismiss();
    expect(s.pinned).toBe(false);
    expect(s.open).toBe(false);
  });

  it("remembers the pin for the next page", () => {
    const s = make();
    s.togglePin();
    expect(localStorage.getItem(PINNED_KEY)).toBe("1");
    s.togglePin();
    expect(localStorage.getItem(PINNED_KEY)).toBe("0");
  });

  it("comes back pinned on the next page when it was left pinned", async () => {
    localStorage.setItem(PINNED_KEY, "1");
    vi.stubGlobal("fetch", () =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ enabled: true }) }),
    );
    const s = make();
    s.$watch = () => undefined;

    await s.init();

    expect(s.pinned).toBe(true);
    // pinned alone does not open it: the window starts closed on every page
    expect(s.open).toBe(false);
  });

  it("starts unpinned and closed", () => {
    const s = make();
    expect(s.pinned).toBe(false);
    expect(s.open).toBe(false);
  });

  it("knows which message is the latest the user sent", () => {
    const s = make();
    s.messages = [{ role: "user" }, { role: "assistant" }, { role: "user" }, { role: "assistant" }];
    expect(s.isLastUserMessage(2)).toBe(true);
    expect(s.isLastUserMessage(0)).toBe(false);
    expect(s.isLastUserMessage(3)).toBe(false);
  });
});
