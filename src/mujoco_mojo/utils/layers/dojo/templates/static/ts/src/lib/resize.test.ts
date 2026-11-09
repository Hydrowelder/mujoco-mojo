// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { attachVerticalResizeHandle, restorePersistedHeight } from "./resize";

const KEY = "mojo:test:height";

let host: HTMLElement;

// happy-dom does no layout, so a host's offsetHeight is 0 and a drag's result
// is exactly where the pointer moved to
const mouse = (type: string, clientY: number) => new MouseEvent(type, { clientY, bubbles: true, cancelable: true });

beforeEach(() => {
  localStorage.clear();
  document.body.innerHTML = '<div id="host"></div>';
  document.body.style.userSelect = "";
  document.body.style.cursor = "";
  host = document.getElementById("host")!;
  vi.spyOn(window, "scrollBy").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("restorePersistedHeight", () => {
  it("applies the saved height", () => {
    localStorage.setItem(KEY, "420px");
    restorePersistedHeight(host, KEY);
    expect(host.style.height).toBe("420px");
  });

  it("leaves the element alone when nothing was saved", () => {
    host.style.height = "100px";
    restorePersistedHeight(host, KEY);
    expect(host.style.height).toBe("100px");
  });
});

describe("attachVerticalResizeHandle", () => {
  it("puts the handle right after the host and returns it", () => {
    const handle = attachVerticalResizeHandle(host, { storageKey: KEY });
    expect(host.nextElementSibling).toBe(handle);
  });

  describe("dragging", () => {
    it("sets the host's height from how far the pointer moved, and tells the caller", () => {
      const onResize = vi.fn();
      const handle = attachVerticalResizeHandle(host, { storageKey: KEY, onResize });
      handle.dispatchEvent(mouse("mousedown", 100));
      document.dispatchEvent(mouse("mousemove", 400));
      expect(host.style.height).toBe("300px");
      expect(onResize).toHaveBeenLastCalledWith(300);
      document.dispatchEvent(mouse("mousemove", 350));
      expect(host.style.height).toBe("250px");
    });

    it("never goes below the minimum height", () => {
      const handle = attachVerticalResizeHandle(host, { storageKey: KEY, minHeight: 200 });
      handle.dispatchEvent(mouse("mousedown", 100));
      document.dispatchEvent(mouse("mousemove", 120));
      expect(host.style.height).toBe("200px");
    });

    it("defaults the minimum to 128 pixels", () => {
      const handle = attachVerticalResizeHandle(host, { storageKey: KEY });
      handle.dispatchEvent(mouse("mousedown", 100));
      document.dispatchEvent(mouse("mousemove", 90));
      expect(host.style.height).toBe("128px");
    });

    it("scrolls the page down with a downward drag but not an upward one", () => {
      const handle = attachVerticalResizeHandle(host, { storageKey: KEY });
      handle.dispatchEvent(mouse("mousedown", 100));
      document.dispatchEvent(mouse("mousemove", 140));
      expect(window.scrollBy).toHaveBeenLastCalledWith(0, 40);
      vi.mocked(window.scrollBy).mockClear();
      document.dispatchEvent(mouse("mousemove", 120));
      expect(window.scrollBy).not.toHaveBeenCalled();
    });

    it("stops text selection and shows the resize cursor only while dragging", () => {
      const handle = attachVerticalResizeHandle(host, { storageKey: KEY });
      handle.dispatchEvent(mouse("mousedown", 100));
      expect(document.body.style.userSelect).toBe("none");
      expect(document.body.style.cursor).toBe("ns-resize");
      document.dispatchEvent(mouse("mouseup", 100));
      expect(document.body.style.userSelect).toBe("");
      expect(document.body.style.cursor).toBe("");
    });

    it("saves the final height on release and stops following the pointer", () => {
      const onResize = vi.fn();
      const handle = attachVerticalResizeHandle(host, { storageKey: KEY, onResize });
      handle.dispatchEvent(mouse("mousedown", 100));
      document.dispatchEvent(mouse("mousemove", 400));
      document.dispatchEvent(mouse("mouseup", 400));
      expect(localStorage.getItem(KEY)).toBe("300px");

      onResize.mockClear();
      document.dispatchEvent(mouse("mousemove", 900));
      expect(onResize).not.toHaveBeenCalled();
      expect(host.style.height).toBe("300px");
    });

    it("saves the height as it stands on release, even if the pointer never moved", () => {
      host.style.height = "180px";
      const handle = attachVerticalResizeHandle(host, { storageKey: KEY });
      handle.dispatchEvent(mouse("mousedown", 100));
      document.dispatchEvent(mouse("mouseup", 100));
      expect(host.style.height).toBe("180px");
      expect(localStorage.getItem(KEY)).toBe("180px");
    });

    it("is not stopped by a storage failure on release", () => {
      vi.stubGlobal("localStorage", {
        setItem() {
          throw new Error("quota exceeded");
        },
      });
      const handle = attachVerticalResizeHandle(host, { storageKey: KEY });
      handle.dispatchEvent(mouse("mousedown", 100));
      document.dispatchEvent(mouse("mousemove", 300));
      expect(() => document.dispatchEvent(mouse("mouseup", 300))).not.toThrow();
      vi.unstubAllGlobals();
    });
  });

  describe("double-click", () => {
    const dblclick = (el: HTMLElement) => el.dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));

    it("resets to the height the caller names, and saves it", () => {
      const onResize = vi.fn();
      const handle = attachVerticalResizeHandle(host, { storageKey: KEY, onResize, getResetHeight: () => "320px" });
      host.style.height = "700px";
      dblclick(handle);
      expect(host.style.height).toBe("320px");
      expect(localStorage.getItem(KEY)).toBe("320px");
      expect(onResize).toHaveBeenCalledTimes(1);
    });

    it("does nothing when the caller has no reset height", () => {
      const withNone = attachVerticalResizeHandle(host, { storageKey: KEY });
      host.style.height = "700px";
      dblclick(withNone);
      expect(host.style.height).toBe("700px");

      const declines = attachVerticalResizeHandle(host, { storageKey: KEY, getResetHeight: () => undefined });
      dblclick(declines);
      expect(host.style.height).toBe("700px");
      expect(localStorage.getItem(KEY)).toBeNull();
    });
  });

  it("highlights its grip while the pointer is over the handle", () => {
    const handle = attachVerticalResizeHandle(host, { storageKey: KEY });
    const grip = handle.firstElementChild as HTMLElement;
    expect(grip.style.width).toBe("36px");
    handle.dispatchEvent(new MouseEvent("mouseenter"));
    expect(grip.style.width).toBe("52px");
    handle.dispatchEvent(new MouseEvent("mouseleave"));
    expect(grip.style.width).toBe("36px");
  });
});
