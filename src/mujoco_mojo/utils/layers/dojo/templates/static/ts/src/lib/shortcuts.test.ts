import { describe, expect, it } from "vitest";

import {
  anyPanelOpen,
  isTextInputTarget,
  shortcutsFor,
  stepPlaybackRate,
  type KeyInfo,
  type PanelState,
  type ShortcutAction,
  type ShortcutContext,
} from "./shortcuts";

const key = (k: string, mods: Partial<KeyInfo> = {}): KeyInfo => ({
  key: k,
  metaKey: false,
  ctrlKey: false,
  shiftKey: false,
  repeat: false,
  ...mods,
});

const ctx = (over: Partial<ShortcutContext> = {}): ShortcutContext => ({
  dialogOpen: false,
  isTextInput: false,
  labOpen: false,
  ...over,
});

const actions = (k: KeyInfo, c: ShortcutContext = ctx()): ShortcutAction[] => shortcutsFor(k, c).map((s) => s.action);

const CTRL = { ctrlKey: true };
const META = { metaKey: true };

describe("a held key", () => {
  it("does nothing after the first press", () => {
    expect(actions(key("z", { ...CTRL, repeat: true }))).toEqual([]);
    expect(actions(key("Escape", { repeat: true }))).toEqual([]);
    expect(actions(key("Escape", { repeat: true }), ctx({ dialogOpen: true }))).toEqual([]);
  });
});

describe("with a dialog open", () => {
  const open = ctx({ dialogOpen: true });

  it("cancels on escape and confirms on enter, keeping the key from everything else", () => {
    expect(shortcutsFor(key("Escape"), open)).toEqual([{ action: "dialog-cancel", preventDefault: true, stopPropagation: true }]);
    expect(shortcutsFor(key("Enter"), open)).toEqual([{ action: "dialog-confirm", preventDefault: true, stopPropagation: true }]);
  });

  it("blocks every other shortcut", () => {
    for (const k of [key("/"), key("z", CTRL), key("s", CTRL), key("<"), key("ArrowLeft", CTRL), key("y", META)]) {
      expect(shortcutsFor(k, open)).toEqual([]);
      expect(shortcutsFor(k, { ...open, labOpen: true })).toEqual([]);
    }
  });
});

describe("the / key", () => {
  it("jumps to the trial box", () => {
    expect(shortcutsFor(key("/"), ctx())).toEqual([{ action: "focus-warp", preventDefault: true, stopPropagation: false }]);
  });

  it("types a slash when you are in a field", () => {
    expect(actions(key("/"), ctx({ isTextInput: true }))).toEqual([]);
  });
});

describe("escape", () => {
  it("is passed on to close whatever is open, without blocking the browser", () => {
    expect(shortcutsFor(key("Escape"), ctx())).toEqual([{ action: "escape", preventDefault: false, stopPropagation: false }]);
  });

  it("works in a field and with the lab open", () => {
    expect(actions(key("Escape"), ctx({ isTextInput: true }))).toEqual(["escape"]);
    expect(actions(key("Escape"), ctx({ labOpen: true }))).toEqual(["escape"]);
  });
});

describe("ctrl or cmd + c", () => {
  it("clears the lab, when the lab is open and you are not in a field", () => {
    expect(actions(key("c", CTRL), ctx({ labOpen: true }))).toEqual(["lab-clear"]);
    expect(actions(key("c", META), ctx({ labOpen: true }))).toEqual(["lab-clear"]);
    expect(actions(key("C", CTRL), ctx({ labOpen: true }))).toEqual(["lab-clear"]);
  });

  it("leaves copy alone otherwise", () => {
    expect(actions(key("c", CTRL), ctx())).toEqual([]);
    expect(actions(key("c", CTRL), ctx({ labOpen: true, isTextInput: true }))).toEqual([]);
    expect(actions(key("c"), ctx({ labOpen: true }))).toEqual([]);
  });
});

describe("ctrl or cmd + s", () => {
  it("saves the lab when it is open, even from a field", () => {
    expect(actions(key("s", CTRL), ctx({ labOpen: true }))).toEqual(["lab-save"]);
    expect(actions(key("s", META), ctx({ labOpen: true }))).toEqual(["lab-save"]);
    expect(actions(key("S", CTRL), ctx({ labOpen: true, isTextInput: true }))).toEqual(["lab-save"]);
  });

  it("opens the profiles panel otherwise", () => {
    expect(actions(key("s", CTRL), ctx())).toEqual(["open-profiles"]);
    expect(actions(key("s", META), ctx())).toEqual(["open-profiles"]);
  });

  it("only blocks the browser's save while you are typing in a field", () => {
    expect(shortcutsFor(key("s", CTRL), ctx({ isTextInput: true }))).toEqual([
      { action: "none", preventDefault: true, stopPropagation: false },
    ]);
  });

  it("is ignored without ctrl or cmd", () => {
    expect(actions(key("s"), ctx())).toEqual([]);
    expect(actions(key("s", { shiftKey: true }), ctx())).toEqual([]);
  });
});

describe("ctrl or cmd + arrows", () => {
  it("steps to the previous trial on left and down, the next on right and up", () => {
    for (const mods of [CTRL, META]) {
      expect(actions(key("ArrowLeft", mods))).toEqual(["nav-prev"]);
      expect(actions(key("ArrowDown", mods))).toEqual(["nav-prev"]);
      expect(actions(key("ArrowRight", mods))).toEqual(["nav-next"]);
      expect(actions(key("ArrowUp", mods))).toEqual(["nav-next"]);
    }
  });

  it("is ignored in a field, and without ctrl or cmd", () => {
    expect(actions(key("ArrowLeft", CTRL), ctx({ isTextInput: true }))).toEqual([]);
    expect(actions(key("ArrowRight"))).toEqual([]);
    expect(actions(key("ArrowUp", { shiftKey: true }))).toEqual([]);
  });

  it("works with the lab open too", () => {
    expect(actions(key("ArrowLeft", CTRL), ctx({ labOpen: true }))).toEqual(["nav-prev"]);
  });
});

describe("< and >", () => {
  it("slow down and speed up the video", () => {
    expect(actions(key("<"))).toEqual(["rate-down"]);
    expect(actions(key(">"))).toEqual(["rate-up"]);
    expect(actions(key("<", { shiftKey: true }))).toEqual(["rate-down"]);
  });

  it("are ignored in a field", () => {
    expect(actions(key("<"), ctx({ isTextInput: true }))).toEqual([]);
    expect(actions(key(">"), ctx({ isTextInput: true }))).toEqual([]);
  });
});

describe("undo and redo", () => {
  it.each([
    ["z", false, false, "undo"],
    ["z", true, false, "redo"],
    ["Z", true, false, "redo"],
    ["y", false, false, "redo"],
    ["Y", false, false, "redo"],
    ["z", false, true, "lab-undo"],
    ["z", true, true, "lab-redo"],
    ["y", false, true, "lab-redo"],
  ] as const)("ctrl+%s (shift %s, lab open %s) is %s", (k, shift, labOpen, expected) => {
    expect(actions(key(k, { ...CTRL, shiftKey: shift }), ctx({ labOpen }))).toEqual([expected]);
    expect(actions(key(k, { ...META, shiftKey: shift }), ctx({ labOpen }))).toEqual([expected]);
  });

  it("is ignored in a field, so the field keeps its own undo", () => {
    expect(actions(key("z", CTRL), ctx({ isTextInput: true }))).toEqual([]);
    expect(actions(key("y", CTRL), ctx({ isTextInput: true }))).toEqual([]);
  });

  it("is ignored without ctrl or cmd", () => {
    expect(actions(key("z"))).toEqual([]);
    expect(actions(key("y"), ctx({ labOpen: true }))).toEqual([]);
  });
});

describe("lab layout shortcuts", () => {
  it("arrange on ctrl+shift+a and fit the view on ctrl+shift+f, with the lab open", () => {
    const open = ctx({ labOpen: true });
    expect(actions(key("a", { ...CTRL, shiftKey: true }), open)).toEqual(["lab-arrange"]);
    expect(actions(key("A", { ...META, shiftKey: true }), open)).toEqual(["lab-arrange"]);
    expect(actions(key("f", { ...CTRL, shiftKey: true }), open)).toEqual(["lab-fit"]);
    expect(actions(key("F", { ...META, shiftKey: true }), open)).toEqual(["lab-fit"]);
  });

  it("do nothing with the lab closed, without shift, or in a field", () => {
    expect(actions(key("a", { ...CTRL, shiftKey: true }), ctx())).toEqual([]);
    expect(actions(key("a", CTRL), ctx({ labOpen: true }))).toEqual([]);
    expect(actions(key("f", { ...CTRL, shiftKey: true }), ctx({ labOpen: true, isTextInput: true }))).toEqual([]);
  });
});

describe("other keys", () => {
  it("do nothing", () => {
    for (const k of ["x", "Tab", "Enter", "a", "ArrowLeft", " "]) {
      expect(actions(key(k))).toEqual([]);
      expect(actions(key(k), ctx({ labOpen: true }))).toEqual([]);
    }
  });
});

describe("what each action asks the browser to do", () => {
  it("blocks the browser's own handling for every action but escape", () => {
    const cases: Array<[KeyInfo, ShortcutContext]> = [
      [key("/"), ctx()],
      [key("c", CTRL), ctx({ labOpen: true })],
      [key("s", CTRL), ctx()],
      [key("ArrowLeft", CTRL), ctx()],
      [key("<"), ctx()],
      [key("z", CTRL), ctx()],
      [key("y", CTRL), ctx()],
      [key("a", { ...CTRL, shiftKey: true }), ctx({ labOpen: true })],
    ];
    for (const [k, c] of cases) {
      const out = shortcutsFor(k, c);
      expect(out.length).toBeGreaterThan(0);
      expect(out.every((s) => s.preventDefault)).toBe(true);
      expect(out.some((s) => s.stopPropagation)).toBe(false);
    }
  });
});

describe("isTextInputTarget", () => {
  it("is true for inputs, text areas, selects and editable elements", () => {
    for (const tagName of ["INPUT", "TEXTAREA", "SELECT"]) {
      expect(isTextInputTarget({ tagName, isContentEditable: false })).toBe(true);
    }
    expect(isTextInputTarget({ tagName: "DIV", isContentEditable: true })).toBe(true);
  });

  it("is false for anything else", () => {
    for (const tagName of ["DIV", "BUTTON", "BODY", "A", "input"]) {
      expect(isTextInputTarget({ tagName, isContentEditable: false })).toBe(false);
    }
  });
});

describe("anyPanelOpen", () => {
  const none = (): PanelState => ({
    placementMode: null,
    annotationsOpen: false,
    shapesOpen: false,
    xMenuOpen: false,
    yMenuOpen: false,
    refFrameMenuOpen: false,
    refFrameOriginMenuOpen: false,
    plotConfigOpen: false,
    downloadOpen: false,
    editorOpen: false,
    profilesOpen: false,
    vsMenuOpen: false,
    shareOpen: false,
    notifOpen: false,
    labOpen: false,
    overlayCount: 0,
    isTextInput: false,
  });

  it("is false when nothing is open", () => {
    expect(anyPanelOpen(none())).toBe(false);
  });

  it.each([
    ["placementMode", "vline"],
    ["annotationsOpen", true],
    ["shapesOpen", true],
    ["xMenuOpen", true],
    ["yMenuOpen", true],
    ["refFrameMenuOpen", true],
    ["refFrameOriginMenuOpen", true],
    ["plotConfigOpen", true],
    ["downloadOpen", true],
    ["editorOpen", true],
    ["profilesOpen", true],
    ["vsMenuOpen", true],
    ["shareOpen", true],
    ["notifOpen", true],
    ["labOpen", true],
    ["overlayCount", 1],
    ["overlayCount", 3],
    ["isTextInput", true],
  ] as const)("is true for %s alone (%s)", (field, value) => {
    expect(anyPanelOpen({ ...none(), [field]: value })).toBe(true);
  });

  it("is true with several open at once", () => {
    expect(anyPanelOpen({ ...none(), shapesOpen: true, labOpen: true })).toBe(true);
  });

  it("is false for an empty placement mode", () => {
    expect(anyPanelOpen({ ...none(), placementMode: "" })).toBe(false);
  });
});

describe("stepPlaybackRate", () => {
  const presets = [0.2, 0.5, 1.0, 2.0, 4.0];

  it("steps down to the next slower preset", () => {
    expect(stepPlaybackRate(presets, 1, "down")).toBe(0.5);
    expect(stepPlaybackRate(presets, 4, "down")).toBe(2);
    expect(stepPlaybackRate(presets, 0.5, "down")).toBe(0.2);
  });

  it("steps up to the next faster preset", () => {
    expect(stepPlaybackRate(presets, 1, "up")).toBe(2);
    expect(stepPlaybackRate(presets, 0.2, "up")).toBe(0.5);
    expect(stepPlaybackRate(presets, 2, "up")).toBe(4);
  });

  it("goes from a speed between presets to the nearest preset in that direction", () => {
    expect(stepPlaybackRate(presets, 0.7, "down")).toBe(0.5);
    expect(stepPlaybackRate(presets, 0.7, "up")).toBe(1);
    expect(stepPlaybackRate(presets, 9, "down")).toBe(4);
    expect(stepPlaybackRate(presets, 0.1, "up")).toBe(0.2);
  });

  it("stays put at either end", () => {
    expect(stepPlaybackRate(presets, 0.2, "down")).toBeUndefined();
    expect(stepPlaybackRate(presets, 4, "up")).toBeUndefined();
    expect(stepPlaybackRate(presets, 0.1, "down")).toBeUndefined();
    expect(stepPlaybackRate(presets, 9, "up")).toBeUndefined();
  });

  it("has nowhere to go without presets", () => {
    expect(stepPlaybackRate([], 1, "down")).toBeUndefined();
    expect(stepPlaybackRate([], 1, "up")).toBeUndefined();
  });

  it("does not reorder the presets it is given", () => {
    const copy = [...presets];
    stepPlaybackRate(copy, 1, "down");
    expect(copy).toEqual(presets);
  });
});
