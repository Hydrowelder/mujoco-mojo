// the mouse wheel over a strip that scrolls sideways (the tab bars, the selected signals, the rows of
// quick-filter chips): a mouse with only a vertical wheel has no other way to move one, so the turn of the
// wheel scrolls the strip along instead. marked in the templates with `x-hscroll`, which store.ts registers

// the parts of a wheel event and of a scroller that the decision reads, so it can be tested without a browser
export interface WheelLike {
  deltaX: number;
  deltaY: number;
  /** 0 for pixels, 1 for lines, 2 for pages. */
  deltaMode: number;
  ctrlKey: boolean;
}

export interface ScrollerLike {
  scrollLeft: number;
  scrollWidth: number;
  clientWidth: number;
}

// pixels in a line of wheel travel (Firefox reports a notch as three lines), chosen so a notch moves a strip
// about as far as the 100 or so pixels the other browsers report
const LINE_PX = 40;

// how far to scroll `strip` sideways for `wheel`, or null when the wheel should be left to the browser:
// - a pinch or ctrl-wheel is a zoom
// - a turn that is mostly sideways already (a trackpad swipe, a tilt wheel) is scrolled by the browser
// - a strip that does not overflow has nothing to scroll
// - a strip already at the end the wheel is turning towards passes it on, so the page can still scroll,
//   unless `contain` is set: then the wheel is still the strip's and the answer is 0, scroll nothing
export function sideScrollAmount(
  wheel: WheelLike,
  strip: ScrollerLike,
  contain = false,
): number | null {
  if (wheel.ctrlKey) return null;
  if (Math.abs(wheel.deltaX) >= Math.abs(wheel.deltaY)) return null;
  const end = strip.scrollWidth - strip.clientWidth;
  if (end <= 0) return null;
  const amount =
    wheel.deltaMode === 1
      ? wheel.deltaY * LINE_PX
      : wheel.deltaMode === 2
        ? wheel.deltaY * strip.clientWidth
        : wheel.deltaY;
  if (amount === 0) return null;
  // a pixel of slack at the far end: a scroll position is often a fraction short of it
  const atEnd = amount < 0 ? strip.scrollLeft <= 0 : strip.scrollLeft >= end - 1;
  if (atEnd) return contain ? 0 : null;
  return amount;
}

// scrolls `strip` sideways for the wheel event, and keeps the page from scrolling for it
export function sideScroll(event: WheelEvent, strip: HTMLElement, contain = false): void {
  const amount = sideScrollAmount(event, strip, contain);
  if (amount === null) return;
  event.preventDefault();
  strip.scrollLeft += amount;
}

// what `x-hscroll` does to its element: listens for the wheel, and stops when Alpine removes the element.
// `x-hscroll.contain` keeps the wheel at the ends too, so the page does not scroll when the strip has
// been scrolled as far as it goes. the listener is not passive, since it has to be able to cancel the
// page's own scroll
export function installSideScroll(
  strip: HTMLElement,
  cleanup: (undo: () => void) => void,
  modifiers: string[] = [],
): void {
  const contain = modifiers.includes("contain");
  const onWheel = (event: WheelEvent) => sideScroll(event, strip, contain);
  strip.addEventListener("wheel", onWheel, { passive: false });
  cleanup(() => strip.removeEventListener("wheel", onWheel));
}
