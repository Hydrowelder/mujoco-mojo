import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

// what the committed build holds of the font the Dojo ships (styles/fonts.css). it is inlined into main.css, because dist/ is
// served at /mojo-static/dist/ and a font file named by a root-relative url() there would be a 404 that no test would see: the
// text would just fall back to the system font, which is the case the shipped font is there to end
const dist = resolve(import.meta.dirname, "../../../dist");
const css = readFileSync(resolve(dist, "main.css"), "utf-8");

describe("the built Roboto, which the Dojo ships so its text looks the same on every machine", () => {
  it("is declared in the stylesheet, in an upright and an italic face that each cover every weight", () => {
    const faces = css.match(/@font-face\{[^}]*Roboto Variable[^}]*\}/g) ?? [];
    expect(faces).toHaveLength(2);
    expect(faces.filter((face) => face.includes("font-style:normal"))).toHaveLength(1);
    expect(faces.filter((face) => face.includes("font-style:italic"))).toHaveLength(1);
    for (const face of faces) {
      expect(face).toContain("font-weight:100 900");
    }
  });

  it("is inside the stylesheet, so there is no url for the Dojo to fail to serve", () => {
    const faces = css.match(/@font-face\{[^}]*Roboto Variable[^}]*\}/g) ?? [];
    for (const face of faces) {
      expect(face).toContain("url(data:font/woff2;base64,");
      expect(face).not.toMatch(/url\((?!data:)/);
    }
    expect(readdirSync(dist).filter((name) => /\.(woff2?|ttf|otf|eot)$/i.test(name))).toEqual([]);
  });

  it("is the first font of the Dojo's text, ahead of the system's", () => {
    expect(css).toMatch(/--font-sans:"Roboto Variable",/);
  });

  it("is the latin subset only, so none of the package's other scripts are built in", () => {
    // each face is about 60 KB as a data url; a full set of subsets would be many times that
    const faces = css.match(/@font-face\{[^}]*Roboto Variable[^}]*\}/g) ?? [];
    for (const face of faces) {
      expect(face.length).toBeLessThan(100_000);
    }
  });

  it("travels with its license", () => {
    expect(existsSync(resolve(dist, "roboto-LICENSE.txt"))).toBe(true);
    expect(readFileSync(resolve(dist, "roboto-LICENSE.txt"), "utf-8")).toContain("SIL Open Font License");
  });
});
