// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// happy-dom has no canvas, which is what themeColor leans on to turn whatever
// color string the browser resolved (often lab(...)) into hex. so the canvas is
// replaced by a stand-in that "renders" a lookup table of known colors and
// reads the pixel back, the same two calls the real one makes

const PIXELS: Record<string, [number, number, number]> = {
  "lab(67.8% -35.4 -30.2)": [6, 182, 212],
  "#000000": [0, 0, 0],
  "rgb(255, 255, 255)": [255, 255, 255],
  "#0a0b0c": [10, 11, 12],
};

function stubCanvas(): { contexts: number } {
  const seen = { contexts: 0 };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation((() => {
    seen.contexts += 1;
    let current = "";
    return {
      set fillStyle(value: string) {
        current = value;
      },
      fillRect() {},
      getImageData: () => ({ data: PIXELS[current] ?? [0, 0, 0] }),
    };
  }) as unknown as typeof HTMLCanvasElement.prototype.getContext);
  return seen;
}

const setToken = (name: string, value: string) => document.documentElement.style.setProperty(`--color-${name}`, value);

// the module keeps its canvas between calls, so each test gets a fresh copy of it
async function load() {
  vi.resetModules();
  return import("./theme-colors");
}

beforeEach(() => {
  document.documentElement.removeAttribute("style");
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("themeColor", () => {
  it("reads a design token and returns it as a hex string, whatever color syntax the browser resolved it to", async () => {
    stubCanvas();
    const { themeColor } = await load();
    setToken("accent-500", "lab(67.8% -35.4 -30.2)");
    expect(themeColor("accent-500")).toBe("#06b6d4");
    setToken("canvas", "rgb(255, 255, 255)");
    expect(themeColor("canvas")).toBe("#ffffff");
  });

  it("pads each channel to two digits", async () => {
    stubCanvas();
    const { themeColor } = await load();
    setToken("ink", "#0a0b0c");
    expect(themeColor("ink")).toBe("#0a0b0c");
    setToken("black", "#000000");
    expect(themeColor("black")).toBe("#000000");
  });

  it("ignores whitespace around the token's value", async () => {
    stubCanvas();
    const { themeColor } = await load();
    setToken("accent-500", "  lab(67.8% -35.4 -30.2)  ");
    expect(themeColor("accent-500")).toBe("#06b6d4");
  });

  it("returns an empty string for a token that is not defined, without touching the canvas", async () => {
    const seen = stubCanvas();
    const { themeColor } = await load();
    expect(themeColor("no-such-token")).toBe("");
    expect(seen.contexts).toBe(0);
  });

  it("reads the token fresh on every call, so a theme change shows up", async () => {
    stubCanvas();
    const { themeColor } = await load();
    setToken("accent-500", "#000000");
    expect(themeColor("accent-500")).toBe("#000000");
    setToken("accent-500", "rgb(255, 255, 255)");
    expect(themeColor("accent-500")).toBe("#ffffff");
  });

  it("makes its canvas once and reuses it", async () => {
    const seen = stubCanvas();
    const { themeColor } = await load();
    setToken("a", "#000000");
    themeColor("a");
    themeColor("a");
    themeColor("a");
    expect(seen.contexts).toBe(1);
  });

  it("falls back to the color as the browser gave it when there is no canvas to convert with", async () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    const { themeColor } = await load();
    setToken("accent-500", "lab(67.8% -35.4 -30.2)");
    expect(themeColor("accent-500")).toBe("lab(67.8% -35.4 -30.2)");
  });
});

describe("themeColorAlpha", () => {
  it("appends the alpha as two hex digits", async () => {
    stubCanvas();
    const { themeColorAlpha } = await load();
    setToken("accent-500", "lab(67.8% -35.4 -30.2)");
    expect(themeColorAlpha("accent-500", 1)).toBe("#06b6d4ff");
    expect(themeColorAlpha("accent-500", 0)).toBe("#06b6d400");
    expect(themeColorAlpha("accent-500", 0.5)).toBe("#06b6d480");
    expect(themeColorAlpha("accent-500", 0.1)).toBe("#06b6d41a");
  });
});
