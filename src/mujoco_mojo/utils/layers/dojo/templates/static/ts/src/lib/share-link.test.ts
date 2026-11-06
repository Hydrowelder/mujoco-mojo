import { describe, expect, it } from "vitest";

import LZString from "lz-string";

import type { PlotConfig } from "../models";
import { decodeShareConfig, encodeShareConfig, extractShareBlob } from "./share-link";

const config = (over: Record<string, unknown> = {}) =>
  ({
    xAxis: { col: "time", filters: [] },
    yAxes: { "Bodies/B/xpos:x": { color: "#ff0000", width: 3 } },
    refFrame: [null, null],
    title: "Falling box",
    ...over,
  }) as unknown as PlotConfig;

describe("encodeShareConfig and decodeShareConfig", () => {
  it("round-trips a config", () => {
    const original = config();
    expect(decodeShareConfig(encodeShareConfig(original))).toEqual(original);
  });

  it("produces text that is safe to put in a URL as it is", () => {
    expect(encodeShareConfig(config())).toMatch(/^[A-Za-z0-9+$-]+$/);
  });

  it("is much shorter than the JSON for a repetitive config", () => {
    const big = config({ title: "abc".repeat(200) });
    expect(encodeShareConfig(big).length).toBeLessThan(JSON.stringify(big).length / 3);
  });

  it("resets a reference frame saved in the old format", () => {
    const legacy = LZString.compressToEncodedURIComponent(JSON.stringify({ ...config(), refFrame: "Bodies/B/quat" }));
    expect(decodeShareConfig(legacy).refFrame).toEqual([null, null]);
    const current = encodeShareConfig(config({ refFrame: ["q", "o"] }));
    expect(decodeShareConfig(current).refFrame).toEqual(["q", "o"]);
  });

  it.each([
    ["an empty string", ""],
    ["text that was never compressed", "not a share link"],
    ["compressed text that is not JSON", LZString.compressToEncodedURIComponent("not json")],
  ])("throws on %s", (_label, blob) => {
    expect(() => decodeShareConfig(blob)).toThrow();
  });
});

describe("extractShareBlob", () => {
  it("returns a bare code as it is, trimmed", () => {
    expect(extractShareBlob("  N4IgLgpg  ")).toBe("N4IgLgpg");
  });

  it("takes the v parameter out of a full link", () => {
    expect(extractShareBlob("http://10.0.0.5:8000/mosaic/trial_00?v=N4IgLgpg")).toBe("N4IgLgpg");
    expect(extractShareBlob("http://host/mosaic/trial_00?x=1&v=abc&y=2")).toBe("abc");
  });

  it("returns null for blank input", () => {
    expect(extractShareBlob("")).toBeNull();
    expect(extractShareBlob("   \n")).toBeNull();
  });

  it("returns a link with no v parameter whole, to be rejected when decoded", () => {
    expect(extractShareBlob("http://host/mosaic/trial_00")).toBe("http://host/mosaic/trial_00");
  });

  it("gives a link a full paste of the copied link can be decoded from, even when the code has a plus sign", () => {
    // a + in a query string reads back as a space; decoding has to undo that
    let original: PlotConfig | null = null;
    let encoded = "";
    for (let i = 0; i < 200 && !encoded.includes("+"); i++) {
      original = config({ title: `plot ${i} ${"xyz".repeat(i)}` });
      encoded = encodeShareConfig(original);
    }
    expect(encoded).toContain("+");
    const link = `http://host:8000/mosaic/trial_00?v=${encoded}`;
    expect(extractShareBlob(link)).toContain(" ");
    expect(decodeShareConfig(extractShareBlob(link)!)).toEqual(original);
  });
});
