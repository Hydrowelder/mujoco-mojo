// keeping the open tab of a strip in view. a strip of many tabs scrolls sideways, and the tab that is
// open can be out of sight to the right of what shows: on a page that has just loaded (the tabs come back
// from the browser's storage, and the strip starts at its left end), or after a tab is opened some other
// way. marked in the templates with `x-reveal-active="<the open tab's id>"`, which store.ts registers

// the parts of two boxes the decision reads, in the page's coordinates (a bounding rect's `left` and
// `right`), plus how far the strip is scrolled now
export interface StripBox {
  left: number;
  right: number;
  scrollLeft: number;
}

export interface TabBox {
  left: number;
  right: number;
}

// room left between a revealed tab and the edge of the strip, so the next tab is seen to be there
const MARGIN = 8;

// where to scroll the strip so the tab is in view, or null when it already is. it moves no further than
// it has to, and when the tab is wider than the strip it lines up its left end
export function revealOffset(strip: StripBox, tab: TabBox, margin = MARGIN): number | null {
  const beforeStart = tab.left - (strip.left + margin);
  const pastEnd = tab.right - (strip.right - margin);
  if (beforeStart < 0) return Math.max(0, strip.scrollLeft + beforeStart);
  if (pastEnd > 0) return Math.max(0, strip.scrollLeft + Math.min(pastEnd, beforeStart));
  return null;
}

// whether a tab that was in view while the strip was `before` wide is out of view now that it is `after`
// wide, which is what a button appearing beside the strip does to the tab at its far end. the left edge and
// the scroll position are the same on both sides of a resize, so the strip's old box is its new one with the
// old width. a tab that was already out of view is not lost, which keeps a strip the user scrolled away
// from the open tab where they left it
export function lostFromView(strip: StripBox, tab: TabBox, before: number, after: number): boolean {
  const was = revealOffset({ ...strip, right: strip.left + before }, tab) === null;
  const now = revealOffset({ ...strip, right: strip.left + after }, tab) !== null;
  return was && now;
}

// the tab of `strip` whose `data-tab-id` is `id`
function findTab(strip: HTMLElement, id: string): HTMLElement | undefined {
  // compared as text rather than put in a selector, so an id needs no escaping
  return [...strip.querySelectorAll<HTMLElement>("[data-tab-id]")].find((el) => el.dataset["tabId"] === id);
}

// scrolls `strip` to the tab whose `data-tab-id` is `id`. false when there is no such tab (yet)
export function revealTab(strip: HTMLElement, id: string): boolean {
  const tab = findTab(strip, id);
  if (!tab) return false;
  const box = strip.getBoundingClientRect();
  const to = revealOffset(
    { left: box.left, right: box.right, scrollLeft: strip.scrollLeft },
    tab.getBoundingClientRect(),
  );
  if (to !== null) strip.scrollLeft = to;
  return true;
}

// what `x-reveal-active` does to its strip. `watch` calls its listener with the open tab's id now and
// every time it changes (Alpine's effect, in the template). the tab is revealed
// - when the id is first known and when it changes: on the next frame, once the tabs it names are drawn
// - the first time the strip has a width, since one that was hidden (the Signal Lab's, until the Lab
//   is opened) has none to scroll in
// - once the fonts are in, which change the width of every tab
// - when the strip loses room (a button shown beside it, a narrower window) that takes the open tab out of
//   view. a strip that is resized with the open tab already out of view is left alone, which would
//   otherwise fight the user's own scrolling
export function installRevealActive(
  strip: HTMLElement,
  watch: (listener: (id: string) => void) => void,
  cleanup: (undo: () => void) => void,
): void {
  let active = "";
  const reveal = () => {
    if (active) revealTab(strip, active);
  };

  const openTabLost = (before: number, after: number) => {
    const tab = active ? findTab(strip, active) : undefined;
    if (!tab) return false;
    const box = strip.getBoundingClientRect();
    return lostFromView({ left: box.left, right: box.right, scrollLeft: strip.scrollLeft }, tab.getBoundingClientRect(), before, after);
  };

  watch((id) => {
    active = id;
    requestAnimationFrame(reveal);
  });

  if (typeof ResizeObserver !== "undefined") {
    let width = strip.clientWidth;
    const observer = new ResizeObserver(() => {
      const before = width;
      width = strip.clientWidth;
      if (before === 0 && width > 0) reveal();
      else if (width > 0 && width < before && openTabLost(before, width)) reveal();
    });
    observer.observe(strip);
    cleanup(() => observer.disconnect());
  }

  void document.fonts?.ready.then(reveal);
}
