// the trial viewer's keyboard shortcuts, moved out of trial-viewer.ts so which
// key does what can be tested without a browser. `shortcutsFor` only decides;
// the component does what each action says.

export interface KeyInfo {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
  repeat: boolean;
}

export interface ShortcutContext {
  // a confirm or prompt dialog is open
  dialogOpen: boolean;
  // the key was pressed in a field you type in
  isTextInput: boolean;
  // the signal lab is open
  labOpen: boolean;
}

export type ShortcutAction =
  | "dialog-cancel"
  | "dialog-confirm"
  | "focus-warp"
  | "escape"
  | "lab-clear"
  | "lab-save"
  | "open-profiles"
  // ctrl+s inside a field you type in: only the browser's save is blocked
  | "none"
  | "nav-prev"
  | "nav-next"
  | "rate-down"
  | "rate-up"
  | "undo"
  | "redo"
  | "lab-undo"
  | "lab-redo"
  | "lab-arrange"
  | "lab-fit";

export interface Shortcut {
  action: ShortcutAction;
  // stop the browser doing its own thing with the key
  preventDefault: boolean;
  // keep other listeners from seeing the key (dialogs only)
  stopPropagation: boolean;
}

const act = (action: ShortcutAction, stopPropagation = false): Shortcut => ({
  action,
  preventDefault: true,
  stopPropagation,
});

// whether the key was pressed in a field you type in
export function isTextInputTarget(el: { tagName: string; isContentEditable: boolean }): boolean {
  return ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) || el.isContentEditable;
}

// what a key press does, in the order the actions should run. An open dialog
// takes escape and enter and nothing else; a key held down does nothing after
// the first press; most shortcuts are ignored while typing in a field, except
// escape and ctrl+s.
export function shortcutsFor(e: KeyInfo, ctx: ShortcutContext): Shortcut[] {
  if (e.repeat) return [];

  // dialog open: handle escape and enter exclusively, block all other shortcuts
  if (ctx.dialogOpen) {
    if (e.key === "Escape") return [act("dialog-cancel", true)];
    if (e.key === "Enter") return [act("dialog-confirm", true)];
    return [];
  }

  const out: Shortcut[] = [];
  const { isTextInput, labOpen } = ctx;
  const cmdOrCtrl = e.metaKey || e.ctrlKey;
  const lower = e.key.toLowerCase();

  if (e.key === "/" && !isTextInput) out.push(act("focus-warp"));
  if (e.key === "Escape") out.push({ action: "escape", preventDefault: false, stopPropagation: false });
  if (cmdOrCtrl && lower === "c" && !isTextInput && labOpen) out.push(act("lab-clear"));
  if (cmdOrCtrl && lower === "s") {
    out.push(act(labOpen ? "lab-save" : !isTextInput ? "open-profiles" : "none"));
  }
  if (cmdOrCtrl && !isTextInput) {
    // up/down mirror left/right (increment/decrement, matching the usual
    // numeric-stepper convention) as a second way to jog between trials
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") out.push(act("nav-prev"));
    else if (e.key === "ArrowRight" || e.key === "ArrowUp") out.push(act("nav-next"));
  }
  if (isTextInput) return out;

  if (e.key === "<") out.push(act("rate-down"));
  else if (e.key === ">") out.push(act("rate-up"));

  if (cmdOrCtrl && lower === "z") {
    out.push(act(labOpen ? (e.shiftKey ? "lab-redo" : "lab-undo") : e.shiftKey ? "redo" : "undo"));
  }
  if (cmdOrCtrl && lower === "y") out.push(act(labOpen ? "lab-redo" : "redo"));
  if (labOpen && cmdOrCtrl && e.shiftKey) {
    if (lower === "a") out.push(act("lab-arrange"));
    else if (lower === "f") out.push(act("lab-fit"));
  }
  return out;
}

export interface PanelState {
  placementMode: string | null;
  annotationsOpen: boolean;
  shapesOpen: boolean;
  xMenuOpen: boolean;
  yMenuOpen: boolean;
  refFrameMenuOpen: boolean;
  refFrameOriginMenuOpen: boolean;
  plotConfigOpen: boolean;
  downloadOpen: boolean;
  editorOpen: boolean;
  profilesOpen: boolean;
  vsMenuOpen: boolean;
  shareOpen: boolean;
  // the notification history in the page header
  notifOpen: boolean;
  labOpen: boolean;
  // how many overlays (dialogs, popups) the page has open
  overlayCount: number;
  isTextInput: boolean;
}

// whether escape has something to close, which decides if the key is kept from
// other listeners (so it does not also, say, exit fullscreen)
export function anyPanelOpen(s: PanelState): boolean {
  return !!(
    s.placementMode ||
    s.annotationsOpen ||
    s.shapesOpen ||
    s.xMenuOpen ||
    s.yMenuOpen ||
    s.refFrameMenuOpen ||
    s.refFrameOriginMenuOpen ||
    s.plotConfigOpen ||
    s.downloadOpen ||
    s.editorOpen ||
    s.profilesOpen ||
    s.vsMenuOpen ||
    s.shareOpen ||
    s.notifOpen ||
    s.labOpen ||
    s.overlayCount > 0 ||
    s.isTextInput
  );
}

// the next slower (`<`) or faster (`>`) playback speed from the presets, or
// undefined when already at the end
export function stepPlaybackRate(
  presets: number[],
  rate: number,
  direction: "down" | "up",
): number | undefined {
  return direction === "down"
    ? [...presets].reverse().find((p) => p < rate)
    : presets.find((p) => p > rate);
}
