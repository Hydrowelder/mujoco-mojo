import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

// what the committed build holds of KaTeX. it is asked for MathML only, which the browser draws with its own math fonts, so
// the package carries KaTeX's script and nothing else of it: its fonts and its stylesheet were three quarters of its size
const dist = resolve(import.meta.dirname, "../../../dist");
const config = readFileSync(resolve(import.meta.dirname, "../../vite.config.ts"), "utf-8");
const pageScript = readFileSync(resolve(dist, "sensai.js"), "utf-8");

describe("the built KaTeX, which the Dojo serves from /mojo-static/dist/", () => {
  it("is one script, fetched when a reply has math and not with the page", () => {
    expect(existsSync(resolve(dist, "assets/katex.js"))).toBe(true);
    // the page script reaches it through a dynamic import, which is what makes it lazy
    expect(pageScript).toMatch(/import\(`\.\/assets\/katex\.js`\)/);
    // and none of the other bundles hold it
    for (const name of ["main.js", "monitor.js", "mosaic.js", "trial-viewer.js", "assets/html.js"]) {
      expect(readFileSync(resolve(dist, name), "utf-8"), name).not.toContain("KaTeX parse error");
    }
  });

  it("brings no fonts with it", () => {
    expect(readdirSync(dist).filter((name) => /katex/i.test(name))).toEqual([]);
    expect(readdirSync(dist).filter((name) => /\.(woff2?|ttf|otf|eot)$/i.test(name))).toEqual([]);
  });

  it("brings no stylesheet with it", () => {
    expect(existsSync(resolve(dist, "katex.css"))).toBe(false);
    expect(readdirSync(dist).filter((name) => /^katex.*\.css$/i.test(name))).toEqual([]);
    // the page script does not ask for one along with the script
    expect(pageScript).not.toContain("katex.css");
    expect(pageScript).not.toMatch(/__vite__mapDeps\(\[\d/);
    // and what every page loads has none of KaTeX's rules in it
    expect(readFileSync(resolve(dist, "main.css"), "utf-8")).not.toMatch(/\.katex/);
  });

  it("is run in a way that needs neither: MathML output is what the script is asked for", () => {
    const script = readFileSync(resolve(dist, "assets/katex.js"), "utf-8");
    const source = readFileSync(resolve(import.meta.dirname, "math.ts"), "utf-8");

    // KaTeX itself still holds the code for its HTML output, as it always does: what keeps it from
    // being used is the option the Dojo gives it, so that is what is checked
    expect(script).toContain("katex-html");
    expect(source).toMatch(/output:\s*"mathml"/);
  });
});

describe("the build's configuration", () => {
  it("has nothing in it for KaTeX: no plugin for its fonts, and no settings made for its stylesheet", () => {
    expect(config).not.toMatch(/katex/i);
    expect(config).not.toContain("woff");
  });

  it("is not told to build for a folder, which only the stylesheet and its fonts needed", () => {
    expect(config).not.toMatch(/^ {2}base:/m);
  });
});
