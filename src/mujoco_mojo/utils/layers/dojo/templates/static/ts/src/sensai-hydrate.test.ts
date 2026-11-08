// @vitest-environment happy-dom
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { renderMarkdown } from "./lib/markdown";

// the Dojo's pages have a doctype, so they are in the browser's standards mode, which KaTeX needs and
// checks once, when it is loaded. happy-dom reports no mode, which KaTeX takes for quirks mode and then
// will not render, so this says what the pages are before anything loads it
Object.defineProperty(document, "compatMode", { value: "CSS1Compat", configurable: true });

// what a message does once it is on the page: its code blocks, its measuring and its math
type Message = {
  hydrate(isLastUser?: boolean): void;
  measure: (isLastUser?: boolean) => void;
  $el: HTMLElement;
};

let make: (role: string, isLastUser: boolean) => Message;

beforeAll(async () => {
  await import("./sensai");
  make = (window as unknown as { sensaiMsgData: typeof make }).sensaiMsgData;
});

beforeEach(() => {
  vi.stubGlobal("Alpine", { store: () => ({ copyText: vi.fn() }) });
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

// a message holding a reply, with a stand-in for measuring it
function messageHolding(markdown: string) {
  const el = document.createElement("div");
  el.innerHTML = renderMarkdown(markdown);
  document.body.appendChild(el);
  const m = make("assistant", false);
  m.$el = el;
  m.measure = vi.fn();
  return { m, el };
}

// lets the typesetter's fetch and render finish
const settle = async () => {
  for (let i = 0; i < 20; i++) await new Promise<void>((resolve) => setTimeout(resolve, 0));
};

describe("a message once it is on the page", () => {
  it("is measured, and measured again once its math is typeset, since math is taller than its source", async () => {
    const { m, el } = messageHolding("so $x^2$ holds");

    m.hydrate(true);
    expect(m.measure).toHaveBeenCalledTimes(1);
    expect(m.measure).toHaveBeenLastCalledWith(true);
    await settle();

    expect(el.querySelector(".katex")).not.toBeNull();
    expect(m.measure).toHaveBeenCalledTimes(2);
    expect(m.measure).toHaveBeenLastCalledWith(true);
  });

  it("is measured once when it has no math", async () => {
    const { m } = messageHolding("just words and a price of $5");

    m.hydrate(false);
    await settle();

    expect(m.measure).toHaveBeenCalledTimes(1);
  });

  it("has its code blocks turned into editors", async () => {
    const { m, el } = messageHolding("```bash\nls -l\n```");

    m.hydrate(false);
    await settle();

    expect(el.querySelector(".sensai-cm-block .cm-editor")).not.toBeNull();
  });

  it("does code blocks and math together", async () => {
    const { m, el } = messageHolding("$x$\n\n```bash\nls\n```");

    m.hydrate(false);
    await settle();

    expect(el.querySelector(".katex")).not.toBeNull();
    expect(el.querySelector(".cm-editor")).not.toBeNull();
  });

  it("does not typeset math twice when it is done again, as it is whenever the window is opened", async () => {
    const { m, el } = messageHolding("$x$");
    m.hydrate(false);
    await settle();
    const first = el.querySelector(".katex");

    m.hydrate(false);
    await settle();

    expect(el.querySelector(".katex")).toBe(first);
    // measured when first shown, again after its math, and once more now: nothing more for math that is done
    expect(m.measure).toHaveBeenCalledTimes(3);
  });
});

describe("in the page", () => {
  const template = readFileSync(resolve(import.meta.dirname, "../../../partials/_sensai.html"), "utf-8");

  it("does all of it when a message appears and when the window asks for a fresh layout", () => {
    expect(template).toContain('x-init="$nextTick(() => hydrate(isLastUserMessage(group.start + i)))"');
    expect(template).toContain('@sensai-remeasure.window="$nextTick(() => hydrate(isLastUserMessage(group.start + i)))"');
  });

  it("no longer starts the code blocks and the measuring by itself", () => {
    expect(template).not.toMatch(/\{ initSensAICodeBlocks\(\$el\); measure\(/);
  });
});
