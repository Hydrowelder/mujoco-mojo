// @vitest-environment happy-dom
import { describe, expect, it } from "vitest";

import { installSideScroll, sideScrollAmount, type ScrollerLike, type WheelLike } from "./wheel-scroll";

const wheel = (over: Partial<WheelLike> = {}): WheelLike => ({ deltaX: 0, deltaY: 100, deltaMode: 0, ctrlKey: false, ...over });
// 500 px of content in a 200 px box, so it can scroll 300 px
const strip = (scrollLeft: number, over: Partial<ScrollerLike> = {}): ScrollerLike => ({ scrollLeft, scrollWidth: 500, clientWidth: 200, ...over });

describe("sideScrollAmount", () => {
  it("scrolls along by as much as the wheel turned, either way", () => {
    expect(sideScrollAmount(wheel({ deltaY: 100 }), strip(50))).toBe(100);
    expect(sideScrollAmount(wheel({ deltaY: -100 }), strip(50))).toBe(-100);
  });

  it("counts a line of wheel as about 40 pixels, and a page as the width of the strip", () => {
    expect(sideScrollAmount(wheel({ deltaY: 3, deltaMode: 1 }), strip(0))).toBe(120);
    expect(sideScrollAmount(wheel({ deltaY: 1, deltaMode: 2 }), strip(0))).toBe(200);
    expect(sideScrollAmount(wheel({ deltaY: -1, deltaMode: 2 }), strip(100))).toBe(-200);
  });

  it("leaves a turn that is mostly sideways to the browser, which already scrolls it", () => {
    expect(sideScrollAmount(wheel({ deltaX: 80, deltaY: 10 }), strip(50))).toBeNull();
    expect(sideScrollAmount(wheel({ deltaX: 100, deltaY: 100 }), strip(50))).toBeNull();
    expect(sideScrollAmount(wheel({ deltaX: -100, deltaY: 0 }), strip(50))).toBeNull();
  });

  it("leaves a zoom alone", () => {
    expect(sideScrollAmount(wheel({ ctrlKey: true }), strip(50))).toBeNull();
  });

  it("leaves a turn of nothing alone", () => {
    expect(sideScrollAmount(wheel({ deltaY: 0 }), strip(50))).toBeNull();
  });

  it("leaves a strip that does not overflow to the page", () => {
    expect(sideScrollAmount(wheel(), strip(0, { scrollWidth: 200 }))).toBeNull();
    expect(sideScrollAmount(wheel(), strip(0, { scrollWidth: 150 }))).toBeNull();
  });

  it("passes the wheel on at the end it is turning towards, so the page can still scroll", () => {
    expect(sideScrollAmount(wheel({ deltaY: -100 }), strip(0))).toBeNull();
    expect(sideScrollAmount(wheel({ deltaY: 100 }), strip(300))).toBeNull();
    // a position a fraction short of the end is the end
    expect(sideScrollAmount(wheel({ deltaY: 100 }), strip(299.5))).toBeNull();
  });

  it("with contain, keeps the wheel at the ends too, and scrolls nothing", () => {
    expect(sideScrollAmount(wheel({ deltaY: -100 }), strip(0), true)).toBe(0);
    expect(sideScrollAmount(wheel({ deltaY: 100 }), strip(300), true)).toBe(0);
    expect(sideScrollAmount(wheel({ deltaY: 100 }), strip(299.5), true)).toBe(0);
  });

  it("with contain, still scrolls everywhere else, and leaves alone what it always left alone", () => {
    expect(sideScrollAmount(wheel({ deltaY: 100 }), strip(50), true)).toBe(100);
    expect(sideScrollAmount(wheel({ deltaY: 100 }), strip(0, { scrollWidth: 200 }), true)).toBeNull();
    expect(sideScrollAmount(wheel({ deltaX: 90, deltaY: 10 }), strip(300), true)).toBeNull();
    expect(sideScrollAmount(wheel({ ctrlKey: true }), strip(300), true)).toBeNull();
    expect(sideScrollAmount(wheel({ deltaY: 0 }), strip(300), true)).toBeNull();
  });

  it("still scrolls away from an end, whichever end that is", () => {
    expect(sideScrollAmount(wheel({ deltaY: 100 }), strip(0))).toBe(100);
    expect(sideScrollAmount(wheel({ deltaY: -100 }), strip(300))).toBe(-100);
  });
});

describe("installSideScroll", () => {
  // happy-dom has no layout, so the strip's size is stated
  const makeStrip = (scrollLeft = 0): HTMLElement => {
    const el = document.createElement("div");
    Object.defineProperty(el, "scrollWidth", { value: 500, configurable: true });
    Object.defineProperty(el, "clientWidth", { value: 200, configurable: true });
    el.scrollLeft = scrollLeft;
    return el;
  };
  const turn = (el: HTMLElement, deltaY: number): WheelEvent => {
    const event = new WheelEvent("wheel", { deltaY, cancelable: true, bubbles: true });
    el.dispatchEvent(event);
    return event;
  };

  it("scrolls the strip along and keeps the page from scrolling", () => {
    const el = makeStrip(0);
    installSideScroll(el, () => {});

    const event = turn(el, 100);

    expect(el.scrollLeft).toBe(100);
    expect(event.defaultPrevented).toBe(true);
  });

  it("does not stop the page when the strip is at the end the wheel is turning towards", () => {
    const el = makeStrip(300);
    installSideScroll(el, () => {});

    const event = turn(el, 100);

    expect(el.scrollLeft).toBe(300);
    expect(event.defaultPrevented).toBe(false);
  });

  it("with the contain modifier, stops the page at the end as well", () => {
    const el = makeStrip(300);
    installSideScroll(el, () => {}, ["contain"]);

    const event = turn(el, 100);

    expect(el.scrollLeft).toBe(300);
    expect(event.defaultPrevented).toBe(true);
  });

  it("with the contain modifier, does not take the wheel from a strip with nothing to scroll", () => {
    const el = makeStrip(0);
    Object.defineProperty(el, "scrollWidth", { value: 200, configurable: true });
    installSideScroll(el, () => {}, ["contain"]);

    expect(turn(el, 100).defaultPrevented).toBe(false);
  });

  it("stops listening when it is cleaned up", () => {
    const el = makeStrip(0);
    let undo = () => {};
    installSideScroll(el, (fn) => (undo = fn));

    undo();
    const event = turn(el, 100);

    expect(el.scrollLeft).toBe(0);
    expect(event.defaultPrevented).toBe(false);
  });
});
