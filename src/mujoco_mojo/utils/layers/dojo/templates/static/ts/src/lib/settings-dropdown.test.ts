// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { inView, settingsDropdown } from "./settings-panel";

describe("inView", () => {
  const pane = { top: 100, bottom: 500 };

  it("is true for a trigger inside the pane, or partly inside it", () => {
    expect(inView({ top: 200, bottom: 224 }, pane)).toBe(true);
    expect(inView({ top: 90, bottom: 114 }, pane)).toBe(true);
    expect(inView({ top: 490, bottom: 514 }, pane)).toBe(true);
  });

  it("is false once the trigger has scrolled wholly above or below it", () => {
    expect(inView({ top: 60, bottom: 100 }, pane)).toBe(false);
    expect(inView({ top: 500, bottom: 524 }, pane)).toBe(false);
    expect(inView({ top: -50, bottom: -26 }, pane)).toBe(false);
  });
});

describe("a settings dropdown", () => {
  let pane: HTMLElement;
  let trigger: HTMLElement;
  let hint: HTMLElement;

  // where an element is on the window, which the test moves to scroll it
  const at = (el: HTMLElement, top: number, bottom = top + 24) => {
    el.getBoundingClientRect = () => new DOMRect(40, top, 200, bottom - top);
  };

  const dropdown = () => Object.assign(settingsDropdown(), { $refs: { trigger } });

  beforeEach(() => {
    Object.defineProperty(document.documentElement, "clientHeight", { value: 800, configurable: true });
    pane = document.createElement("div");
    pane.setAttribute("data-settings-pane", "");
    trigger = document.createElement("button");
    pane.append(trigger);
    hint = document.createElement("div");
    hint.setAttribute("data-settings-hint", "");
    document.body.append(pane, hint);
    at(pane, 100, 650);
    at(hint, 650, 800);
    at(trigger, 200);
  });

  afterEach(() => {
    document.body.replaceChildren();
  });

  it("starts closed and opens with its list placed under the button", () => {
    const d = dropdown();
    expect(d.open).toBe(false);

    d.toggle();

    expect(d.open).toBe(true);
    expect(d.panelStyle).toContain("position:fixed");
    expect(d.panelStyle).toContain("top:226px");
    expect(d.panelStyle).toContain("left:40px");
    expect(d.panelStyle).toContain("width:200px");
  });

  it("closes when the button is clicked again", () => {
    const d = dropdown();

    d.toggle();
    d.toggle();

    expect(d.open).toBe(false);
  });

  it("follows the button as the pane scrolls", () => {
    const d = dropdown();
    d.toggle();

    at(trigger, 150);
    d.place();
    expect(d.panelStyle).toContain("top:176px");

    at(trigger, 300);
    d.place();
    expect(d.panelStyle).toContain("top:326px");
    expect(d.open).toBe(true);
  });

  it("hides its list, still open, once the button has scrolled out of the pane", () => {
    const d = dropdown();
    d.toggle();

    at(trigger, 40, 64);
    d.place();

    expect(d.open).toBe(true);
    expect(d.panelStyle).toContain("visibility:hidden");
  });

  it("shows its list again when the button scrolls back into view", () => {
    const d = dropdown();
    d.toggle();
    at(trigger, 40, 64);
    d.place();

    at(trigger, 200);
    d.place();

    expect(d.open).toBe(true);
    expect(d.panelStyle).not.toContain("visibility");
    expect(d.panelStyle).toContain("top:226px");
  });

  it("hides it below the pane as well, where the button has scrolled under the hint bar", () => {
    const d = dropdown();
    d.toggle();

    at(trigger, 660);
    d.place();

    expect(d.panelStyle).toContain("visibility:hidden");
  });

  it("keeps it shown while any of the button is still in view", () => {
    const d = dropdown();
    d.toggle();

    at(trigger, 90, 114);
    d.place();

    expect(d.open).toBe(true);
    expect(d.panelStyle).not.toContain("visibility");
  });

  it("opens above the button when it is too close to the hint bar for room below", () => {
    const d = dropdown();
    at(trigger, 560);

    d.toggle();

    expect(d.panelStyle).toContain("top:auto;bottom:");
  });

  it("measures its room from the bottom of the window when there is no hint bar", () => {
    hint.remove();
    at(pane, 100, 800);
    const d = dropdown();
    at(trigger, 700);

    d.toggle();

    expect(d.panelStyle).toContain("max-height:");
    expect(d.panelStyle).toContain("bottom:");
  });

  it("does nothing without its button", () => {
    const d = Object.assign(settingsDropdown(), { $refs: {} });

    d.place();

    expect(d.panelStyle).toBe("");
  });
});
