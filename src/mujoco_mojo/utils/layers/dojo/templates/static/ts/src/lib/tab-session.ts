// Generic tab-session helpers shared by every tab strip in the trial viewer
// (Signal Lab tabs, plot tabs). Only the mechanical parts of tab bookkeeping
// live here - id generation, localStorage load/persist with a legacy-format
// fallback, drag-to-reorder, and pick-next-active-on-close. What a
// "snapshot" or "activate" means for a given tab's content is domain
// knowledge each feature owns itself (see trial-viewer.ts's
// _snapshotActiveTab/_activateTab for Lab and their plot-tab counterparts).

export interface TabLike {
  id: string;
}

export function newTabId(): string {
  return `t${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
}

export function loadTabsFromStorage<T extends TabLike>(
  tabsKey: string,
  activeKey: string,
  legacyFallback: () => { tabs: T[]; activeId: string },
): { tabs: T[]; activeId: string } {
  try {
    const raw = localStorage.getItem(tabsKey);
    if (raw) {
      const tabs = JSON.parse(raw) as T[];
      if (Array.isArray(tabs) && tabs.length > 0) {
        const storedActive = localStorage.getItem(activeKey) ?? "";
        const activeId =
          tabs.find((t) => t.id === storedActive)?.id ?? tabs[0]!.id;
        return { tabs, activeId };
      }
    }
  } catch {}
  return legacyFallback();
}

export function persistTabsToStorage<T extends TabLike>(
  tabsKey: string,
  activeKey: string,
  tabs: T[],
  activeId: string,
): void {
  try {
    localStorage.setItem(tabsKey, JSON.stringify(tabs));
    localStorage.setItem(activeKey, activeId);
  } catch {}
}

export function reorderTabs<T extends TabLike>(
  tabs: T[],
  draggedId: string,
  dropIndex: number,
): T[] {
  const from = tabs.findIndex((t) => t.id === draggedId);
  if (from === -1) return tabs;
  const next = [...tabs];
  const moved = next.splice(from, 1)[0]!;
  next.splice(dropIndex, 0, moved);
  return next;
}

// Inclusive id range between anchorId and targetId, by current array index
// (not by any timestamp/order the ids were selected in) - the usual
// shift-click "extend selection to here" behavior. Empty if either id isn't
// found (e.g. the anchor tab was closed since it was set as the anchor).
export function selectRange<T extends TabLike>(
  tabs: T[],
  anchorId: string,
  targetId: string,
): string[] {
  const ids = tabs.map((t) => t.id);
  const anchorIdx = ids.indexOf(anchorId);
  const targetIdx = ids.indexOf(targetId);
  if (anchorIdx === -1 || targetIdx === -1) return [];
  const [lo, hi] =
    anchorIdx < targetIdx ? [anchorIdx, targetIdx] : [targetIdx, anchorIdx];
  return ids.slice(lo, hi + 1);
}

// ctrl/cmd-click "add or remove this one id" toggle.
export function toggleSelection(selected: string[], id: string): string[] {
  return selected.includes(id)
    ? selected.filter((x) => x !== id)
    : [...selected, id];
}

// Splices out the tab at `closedIdx`, pushing a blank tab (from
// `makeBlank()`) if that empties the list. `activeChanged` is true only
// when the caller needs to actually activate `nextActiveId` - closing a
// background tab while others remain leaves the current active tab as-is.
export function pickNextActiveOnClose<T extends TabLike>(
  tabs: T[],
  closedIdx: number,
  currentActiveId: string,
  makeBlank: () => T,
): { tabs: T[]; nextActiveId: string; activeChanged: boolean } {
  const closedId = tabs[closedIdx]!.id;
  const next = [...tabs];
  next.splice(closedIdx, 1);
  if (next.length === 0) {
    const blank = makeBlank();
    next.push(blank);
    return { tabs: next, nextActiveId: blank.id, activeChanged: true };
  }
  if (closedId === currentActiveId) {
    const nextActive = next[Math.min(closedIdx, next.length - 1)]!;
    return { tabs: next, nextActiveId: nextActive.id, activeChanged: true };
  }
  return { tabs: next, nextActiveId: currentActiveId, activeChanged: false };
}
