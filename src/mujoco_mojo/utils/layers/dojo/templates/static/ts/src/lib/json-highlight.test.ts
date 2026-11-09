// @vitest-environment happy-dom
import { describe, expect, it } from "vitest";

import { highlightJson } from "./json-highlight";

// the highlighted text goes into the page as HTML, so these read it back with a
// real HTML parser rather than looking at the string

const parse = (text: string) => {
  const box = document.createElement("div");
  box.innerHTML = highlightJson(text);
  return box;
};

// each colored token, in order, with the color word its class carries
const tokens = (text: string) =>
  [...parse(text).querySelectorAll("span")].map((s) => ({ text: s.textContent, cls: s.className }));

describe("highlightJson", () => {
  it("returns nothing for empty text", () => {
    expect(highlightJson("")).toBe("");
  });

  it("gives keys, strings, numbers, booleans and null each their own color", () => {
    const out = tokens('{"key": "text", "n": -2.5e3, "yes": true, "no": false, "nothing": null}');
    const byText = Object.fromEntries(out.map((t) => [t.text, t.cls]));
    expect(byText['"key":']).toContain("text-accent");
    expect(byText['"text"']).toContain("text-success");
    expect(byText["-2.5e3"]).toContain("text-warning");
    expect(byText["true"]).toContain("text-secondary");
    expect(byText["false"]).toContain("text-secondary");
    expect(byText["null"]).toBe("text-danger-500");
  });

  it("keeps punctuation neutral", () => {
    const out = tokens("[1, 2]");
    const brackets = out.filter((t) => t.text === "[" || t.text === "]" || t.text === ",");
    expect(brackets).toHaveLength(3);
    for (const b of brackets) expect(b.cls).toBe("text-ink-secondary");
  });

  it("treats a string that contains a keyword or digits as a string", () => {
    const out = tokens('["true", "null", "12"]');
    for (const t of out.filter((x) => x.text?.startsWith('"'))) expect(t.cls).toContain("text-success");
  });

  it("underlines anything that is not JSON in red", () => {
    const out = tokens("{bad json here}");
    const garbage = out.filter((t) => t.cls.includes("decoration-wavy"));
    // a run of non-space characters is underlined as one, so the closing brace stuck to "here" goes with it
    expect(garbage.map((t) => t.text)).toEqual(["bad", "json", "here}"]);
    expect(garbage[0]!.cls).toContain("text-danger-500");
  });

  it("does not treat a keyword with letters stuck to it as the keyword", () => {
    expect(tokens("true1")[0]!.cls).toContain("decoration-wavy");
  });

  it("leaves whitespace, including newlines, exactly as it was", () => {
    const text = '  {\n    "a":   1\n}\n';
    expect(parse(text).textContent).toBe(text);
  });

  describe("with hostile text", () => {
    const hostile = [
      '{"<img src=x onerror=alert(1)>": "</span><script>alert(1)</script>"}',
      "<script>alert(1)</script>",
      '"><svg onload=alert(1)>',
      "a & b < c > d &amp; &lt;b&gt;",
      '"unterminated <b>bold',
      "<!-- comment --><iframe src=javascript:alert(1)>",
    ];

    it.each(hostile)("shows %j as text and adds no markup of its own", (text) => {
      const box = parse(text);
      expect(box.textContent).toBe(text);
      for (const el of box.querySelectorAll("*")) expect(el.tagName).toBe("SPAN");
    });

    it("never produces an element with an attribute other than class", () => {
      for (const text of hostile) {
        for (const el of parse(text).querySelectorAll("*")) {
          expect([...el.attributes].map((a) => a.name)).toEqual(["class"]);
        }
      }
    });

    it("holds for text made of random fragments", () => {
      const pieces = ['"k"', ":", "1", "-2.0", "true", "null", "{", "}", "[", "]", ",", " ", "\n", "<b>", "&", "<", ">", "x", '"'];
      let seed = 1;
      const rnd = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
      for (let i = 0; i < 200; i++) {
        const text = Array.from({ length: 14 }, () => pieces[Math.floor(rnd() * pieces.length)]!).join("");
        const box = parse(text);
        expect(box.textContent).toBe(text);
        for (const el of box.querySelectorAll("*")) expect(el.tagName).toBe("SPAN");
      }
    });
  });
});
