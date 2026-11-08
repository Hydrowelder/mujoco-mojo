import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { renderMarkdown } from "./lib/markdown";

// the Jinja templates sit beside static/, not under it
const template = readFileSync(resolve(import.meta.dirname, "../../../partials/_sensai.html"), "utf-8");

// the tag that opens at `start`, up to its `>`: an attribute can hold a `>`, as `tabs.length > 1` does, so
// quotes are followed
function openingTag(from: number): string {
  let quote = "";
  for (let i = from; i < template.length; i++) {
    const c = template[i]!;
    if (quote) {
      if (c === quote) quote = "";
    } else if (c === '"' || c === "'") quote = c;
    else if (c === ">") return template.slice(from, i + 1);
  }
  throw new Error("a tag that does not end");
}

// the whole element that opens at `start`, to its closing tag, counting nested ones of the same kind
function elementAt(start: number): string {
  const name = /^<(\w+)/.exec(template.slice(start))![1]!;
  const tags = new RegExp(`<(/?)${name}\\b`, "g");
  tags.lastIndex = start;
  let depth = 0;
  for (let m = tags.exec(template); m; m = tags.exec(template)) {
    depth += m[1] ? -1 : 1;
    if (depth === 0) return template.slice(start, template.indexOf(">", m.index) + 1);
  }
  throw new Error("an element that does not close");
}

const classOf = (tag: string) => /\sclass="([^"]*)"/.exec(tag)![1]!.split(/\s+/);

describe("the list is flush with the top, so a question that sticks there has no gap above it", () => {
  const list = classOf(openingTag(template.lastIndexOf("<div", template.indexOf('x-ref="messages"'))));

  it("has padding at the sides and below, and none above", () => {
    expect(list).toContain("px-3");
    expect(list).toContain("pb-3");
    for (const name of list) {
      expect(name, name).not.toMatch(/^(p|pt|py)-\d/);
    }
  });

  it("leaves the space between exchanges to the exchanges, not to the list", () => {
    expect(list.some((name) => name.startsWith("space-y"))).toBe(false);
    const exchange = classOf(openingTag(template.indexOf('<div class="sensai-exchange')));

    // the room above a question, and between its parts
    expect(exchange).toContain("pt-3");
    expect(exchange).toContain("space-y-3");
  });
});

describe("the question stuck to the top, which is the panel's own color from its top edge and fades out softly below", () => {
  // the declarations of every rule in the page's style that names `selector` among its selectors
  const css = template.replace(/\/\*[\s\S]*?\*\//g, "");
  const rules = (selector: string): string[] =>
    [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
      .filter(([, selectors]) => selectors!.split(",").some((s) => s.trim() === selector))
      .map(([, , declarations]) => declarations!);
  const rule = (selector: string) => {
    const found = rules(selector);
    expect(found.length, selector).toBeGreaterThan(0);
    return found.join("\n");
  };
  const question = rule(".sensai-question");
  const before = rule(".sensai-question::before");
  const after = rule(".sensai-question::after");

  // the declaration of `property` that is not a prefixed one, so that a prefixed one cannot stand in for it
  const plain = (declarations: string, property: string) =>
    new RegExp(`(?<![-\\w])${property}:\\s*([^;]+);`).exec(declarations)?.[1]?.trim();

  // the colored stops of the fade: how opaque each is, and how far down the fade it is (0 at the solid edge, 1 at the end)
  const fadeStops = [
    ...question.matchAll(/color-mix\(in srgb, var\(--color-surface\) (\d+)%, transparent\) calc\(100% - var\(--sensai-fade\) \* ([\d.]+)\)/g),
  ].map(([, opacity, left]) => ({ opacity: Number(opacity), down: 1 - Number(left) }));

  // the stops of a mask: how opaque each is and where
  const maskStops = (declarations: string) =>
    [...(plain(declarations, "mask-image") ?? "").matchAll(/rgb\(0 0 0 \/ ([\d.]+)\) ([\d.]+)%/g)].map(([, opacity, at]) => ({
      opacity: Number(opacity),
      at: Number(at),
    }));

  describe("the fade of its color", () => {
    it("has a solid color first, for a browser that cannot read the fade, and the fade after it", () => {
      const solid = question.indexOf("background: var(--color-surface);");
      const fade = question.indexOf("background: linear-gradient(");

      expect(solid).toBeGreaterThan(-1);
      expect(fade).toBeGreaterThan(solid);
    });

    it("is solid down to where the fade starts and clear at the very end", () => {
      expect(question).toMatch(/linear-gradient\(\s*to bottom,\s*var\(--color-surface\) calc\(100% - var\(--sensai-fade\)\)/);
      expect(question).toMatch(/transparent 100%\s*\)/);
    });

    it("has many stops between, so it is a curve and not a line", () => {
      expect(fadeStops.length).toBeGreaterThanOrEqual(6);
    });

    it("falls through the fade from nearly solid to nearly clear, never rising", () => {
      const opacities = fadeStops.map((stop) => stop.opacity);

      expect(opacities[0]).toBeGreaterThan(90);
      expect(opacities[opacities.length - 1]).toBeLessThan(10);
      for (let i = 1; i < opacities.length; i++) expect(opacities[i]!, `stop ${i}`).toBeLessThan(opacities[i - 1]!);
    });

    it("has its stops evenly down the fade, in order", () => {
      const downs = fadeStops.map((stop) => stop.down);

      for (let i = 1; i < downs.length; i++) expect(downs[i]! - downs[i - 1]!).toBeCloseTo(downs[1]! - downs[0]!, 5);
      expect(downs[0]).toBeGreaterThan(0);
      expect(downs[downs.length - 1]).toBeLessThan(1);
    });

    it("is an S-curve: slow at the start and the end, quickest in the middle, and the same either side of it", () => {
      const opacity = (down: number) => fadeStops.find((stop) => Math.abs(stop.down - down) < 1e-9)!.opacity;

      // the straight line would be at 75 and 25 here
      expect(opacity(0.25)).toBeGreaterThan(75);
      expect(opacity(0.75)).toBeLessThan(25);
      expect(opacity(0.5)).toBe(50);
      for (const down of [0.125, 0.25, 0.375]) expect(opacity(down) + opacity(1 - down), `at ${down}`).toBeGreaterThanOrEqual(99);
      for (const down of [0.125, 0.25, 0.375]) expect(opacity(down) + opacity(1 - down), `at ${down}`).toBeLessThanOrEqual(101);
    });

    it("takes its color from the theme alone, so it follows light and dark mode and matches the panel", () => {
      expect(question).not.toMatch(/#[0-9a-f]{3,8}\b/i);
      expect(question).not.toMatch(/\brgba?\(/);
      expect(question.replace(/var\(--color-surface\)/g, "")).not.toMatch(/\b(white|black)\b/);
    });
  });

  describe("how big it is", () => {
    it("is two rem, with the room for it under the bubble, and none added by the list's own spacing", () => {
      expect(question).toContain("--sensai-fade: 2rem;");
      const tag = openingTag(template.lastIndexOf("<div", template.indexOf('x-data="sensaiMsgData(')));
      const user = /msg\.role === 'user' \? '([^']*)'/.exec(tag)![1]!.split(/\s+/);

      // Tailwind's pb-8 is two rem; mb-0 stops the list's spacing between children adding to it
      expect(user).toContain("pb-8");
      expect(user).toContain("mb-0");
    });

    it("is as tall in each of the layers over it", () => {
      for (const layer of [before, after]) expect(layer).toContain("height: var(--sensai-fade)");
    });

    it("is drawn by the question's own pseudo-elements across its whole width, at the bottom of it", () => {
      const shared = rules(".sensai-question::before").find((declarations) => declarations.includes("content"))!;

      expect(shared).toContain('content: ""');
      expect(shared).toContain("position: absolute");
      expect(shared).toContain("inset: auto 0 0 0");
      // the same rule serves both layers
      expect(rules(".sensai-question::after").some((declarations) => declarations === shared)).toBe(true);
    });

    it("lets clicks through to what is under it", () => {
      const shared = rules(".sensai-question::before").find((declarations) => declarations.includes("content"))!;

      expect(shared).toContain("pointer-events: none");
    });
  });

  describe("the blur", () => {
    it("is two layers, a light one and a stronger one, each both prefixed and plain", () => {
      expect(plain(before, "backdrop-filter")).toBe("blur(2px)");
      expect(plain(after, "backdrop-filter")).toBe("blur(6px)");
      expect(before).toContain("-webkit-backdrop-filter: blur(2px);");
      expect(after).toContain("-webkit-backdrop-filter: blur(6px);");
    });

    it("has each mask both prefixed and plain, and the same", () => {
      for (const layer of [before, after]) {
        const prefixed = /-webkit-mask-image:\s*([^;]+);/.exec(layer)![1]!.trim();

        expect(prefixed).toBe(plain(layer, "mask-image"));
      }
    });

    it("is full where the question is and falls to nothing, along the same S-curve, so it has gone by the bottom", () => {
      for (const layer of [before, after]) {
        const stops = maskStops(layer);

        expect(stops.length).toBeGreaterThanOrEqual(6);
        expect(stops[0]).toEqual({ opacity: 1, at: 0 });
        expect(stops[stops.length - 1]!.opacity).toBe(0);
        for (let i = 1; i < stops.length; i++) {
          expect(stops[i]!.opacity, `stop ${i}`).toBeLessThan(stops[i - 1]!.opacity);
          expect(stops[i]!.at, `stop ${i}`).toBeGreaterThan(stops[i - 1]!.at);
        }
      }
    });

    it("is eased in the light layer too: more than a straight line has at the quarter and the three quarters", () => {
      const stops = maskStops(before);
      const at = (position: number) => stops.find((stop) => stop.at === position)!.opacity;

      expect(at(25)).toBeGreaterThan(0.75);
      expect(at(75)).toBeLessThan(0.25);
    });

    it("ends the light layer at the bottom and the stronger layer well before it, so the blur lessens as it goes down", () => {
      expect(maskStops(before).at(-1)!.at).toBe(100);
      expect(maskStops(after).at(-1)!.at).toBeLessThan(80);
      expect(maskStops(after).at(-1)!.at).toBeGreaterThan(40);
    });

    it("is stronger in the layer that ends sooner, which is what makes it strongest by the question", () => {
      const radius = (declarations: string) => Number(/blur\((\d+)px\)/.exec(plain(declarations, "backdrop-filter")!)![1]);

      expect(radius(after)).toBeGreaterThan(radius(before));
      expect(maskStops(after).at(-1)!.at).toBeLessThan(maskStops(before).at(-1)!.at);
    });

    it("is a mask of black with only its opacity changing, so it carries no color of its own", () => {
      for (const layer of [before, after]) {
        const colors = [...(plain(layer, "mask-image") ?? "").matchAll(/rgb\(([^/)]*)\//g)].map((m) => m[1]!.trim());

        expect(colors.length).toBeGreaterThan(0);
        expect(new Set(colors)).toEqual(new Set(["0 0 0"]));
      }
    });
  });

  it("is the class the question is given in the page, along with sticking to the top", () => {
    const at = template.indexOf('x-data="sensaiMsgData(');
    const tag = openingTag(template.lastIndexOf("<div", at));
    const user = /msg\.role === 'user' \? '([^']*)'/.exec(tag)![1]!.split(/\s+/);

    for (const name of ["sticky", "top-0", "z-10", "sensai-question"]) expect(user).toContain(name);
  });
});

describe("a message's header row holds its name, when it was sent, and its copy button", () => {
  const rowStart = template.indexOf('<div class="flex items-center gap-1">', template.indexOf("<!-- header:"));
  const row = elementAt(rowStart);
  const bubble = template.indexOf('x-ref="bubble"');

  it("is above the bubble", () => {
    expect(rowStart).toBeGreaterThan(-1);
    expect(rowStart + row.length).toBeLessThan(bubble);
  });

  it("has the toggle first and the copy button after it, beside the name and time", () => {
    expect(row.indexOf('@mousedown.prevent="toggle()"')).toBeGreaterThan(-1);
    expect(row.indexOf('@click="copy(msg.content)"')).toBeGreaterThan(row.indexOf('@mousedown.prevent="toggle()"'));
    expect(row).toContain("notifTimeAgo(msg.ts");
    expect(row).toContain("'You' : 'SensAI'");
  });

  it("has the only copy button of a message, and none below the bubble any more", () => {
    expect(template.match(/copy\(msg\.content\)/g)).toHaveLength(1);
    expect(template.lastIndexOf("copy(msg.content)")).toBeLessThan(bubble);
    expect(template).not.toContain("copy button: below the bubble");
  });

  it("is a button of its own, so copying does not open or close the message", () => {
    const copyAt = template.lastIndexOf("<button", template.indexOf('@click="copy(msg.content)"'));
    const copy = elementAt(copyAt);
    const toggleAt = template.lastIndexOf("<button", template.indexOf('@mousedown.prevent="toggle()"'));
    const toggle = elementAt(toggleAt);

    expect(copy).not.toContain("toggle()");
    expect(toggle).not.toContain("copy(");
    expect(toggle).not.toContain("copied");
    expect(copyAt).toBeGreaterThan(toggleAt + toggle.length - 1);
  });

  it("is still labelled, and shows when it has copied", () => {
    const copyAt = template.lastIndexOf("<button", template.indexOf('@click="copy(msg.content)"'));
    const copy = elementAt(copyAt);

    expect(copy).toContain('aria-label="Copy message"');
    expect(copy).toContain(":title=\"copied ? 'Copied' : 'Copy message'\"");
    expect(copy).toContain('x-show="!copied"');
    expect(copy).toContain('x-show="copied"');
  });

  it("is in the question that sticks, so the copy button is with it", () => {
    const sticky = template.lastIndexOf("<div", template.indexOf("x-data=\"sensaiMsgData("));
    const message = elementAt(sticky);

    expect(message).toContain('@click="copy(msg.content)"');
    expect(message.indexOf('@click="copy(msg.content)"')).toBeLessThan(message.indexOf('x-ref="bubble"'));
  });
});

// the declarations of every rule in the page's style block whose selector list has `selector` in it, comments left out
const css = template.replace(/\/\*[\s\S]*?\*\//g, "");
const declarations = (selector: string): string => {
  const found = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter(([, selectors]) =>
    selectors!.split(",").some((s) => s.trim() === selector),
  );
  expect(found.length, selector).toBeGreaterThan(0);
  return found.map(([, , body]) => body!).join("\n");
};

describe("a table in a reply has a border around every cell and a recessed header", () => {
  it("is drawn in the code block's own two theme colors, so it follows light and dark mode", () => {
    const cells = declarations(".sensai-md td");

    expect(declarations(".sensai-md th")).toContain("border: 1px solid var(--color-subtle);");
    expect(cells).toContain("border: 1px solid var(--color-subtle);");
    expect(declarations(".sensai-md th")).toContain("background: var(--color-well);");
    expect(declarations(".sensai-cm-block")).toContain("border: 1px solid var(--color-subtle);");
    expect(declarations(".sensai-cm-block")).toContain("background: var(--color-well);");
  });

  it("has no color of its own that is not a theme token", () => {
    const rules = ["table", "th", "td"].map((tag) => declarations(`.sensai-md ${tag}`)).join("\n");

    expect(rules).not.toMatch(/#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i);
  });

  it("collapses the borders, so two cells share one line and not a double one", () => {
    expect(declarations(".sensai-md table")).toContain("border-collapse: collapse;");
  });

  it("gives the cells room, and the header more weight than the rows", () => {
    expect(declarations(".sensai-md td")).toContain("padding: 0.25rem 0.625rem;");
    expect(declarations(".sensai-md th")).toContain("padding: 0.25rem 0.625rem;");
    expect(declarations(".sensai-md th")).toContain("font-weight: 600;");
  });

  it("is a block as wide as its table, up to the bubble, that scrolls sideways when the table is wider", () => {
    const table = declarations(".sensai-md table");

    expect(table).toContain("display: block;");
    expect(table).toContain("width: max-content;");
    expect(table).toContain("max-width: 100%;");
    expect(table).toContain("overflow-x: auto;");
  });

  it("has room above and below it, as a code block does", () => {
    expect(declarations(".sensai-md table")).toContain("margin: 0.5rem 0;");
  });

  it("left-aligns a header that has no alignment of its own, and leaves one that has to its align attribute", () => {
    expect(declarations(".sensai-md th:not([align])")).toContain("text-align: left;");
    // a rule on every header would beat the align attribute, which is only a hint to the browser
    expect(declarations(".sensai-md th")).not.toContain("text-align");
  });

  it("is written by marked with the pieces these rules name", () => {
    const html = renderMarkdown("| Job | Trials |\n| --- | ---: |\n| a | 200 |\n");

    expect(html).toContain("<table>");
    expect(html).toContain("<th>Job</th>");
    expect(html).toContain('<th align="right">Trials</th>');
    expect(html).toContain('<td align="right">200</td>');
  });

  it("keeps a code span and a price in a cell as they are", () => {
    const html = renderMarkdown("| a | b |\n| --- | --- |\n| `x<y` | $5 or $10 |\n");

    expect(html).toContain('<td><code class="md-inline-code">x&lt;y</code></td>');
    expect(html).toContain("<td>$5 or $10</td>");
  });
});

describe("math in a reply, which the browser draws with its own math fonts", () => {
  it("has the formula a little larger than the text around it", () => {
    expect(declarations(".sensai-md math")).toContain("font-size: 1.05em;");
  });

  it("has a formula on its own as a centered block that scrolls sideways when it is wider than the bubble", () => {
    const block = declarations(".sensai-md .sensai-math-display");

    expect(block).toContain("display: block;");
    expect(block).toContain("text-align: center;");
    expect(block).toContain("overflow-x: auto;");
    expect(block).toContain("overflow-y: hidden;");
    expect(block).toContain("margin: 0.5rem 0;");
  });

  it("has no rule left for the HTML KaTeX writes by default, which is not written any more", () => {
    expect(css).not.toMatch(/\.katex/);
    expect(css).not.toContain("katex-display");
  });
});
