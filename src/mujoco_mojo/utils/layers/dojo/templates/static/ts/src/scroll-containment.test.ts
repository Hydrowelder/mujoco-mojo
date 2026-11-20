import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

// the Jinja templates sit beside static/, not under it
const read = (name: string) => readFileSync(resolve(import.meta.dirname, "../../../partials", name), "utf-8");

// the opening tags in `template` whose text contains `marker`, with their class lists. a tag is read up to its
// `>`, following quotes, since an attribute can hold one
function tagsWith(template: string, marker: string): string[][] {
  const found: string[][] = [];
  for (let at = template.indexOf(marker); at !== -1; at = template.indexOf(marker, at + 1)) {
    const start = template.lastIndexOf("<", at);
    let quote = "";
    let end = start;
    for (; end < template.length; end++) {
      const c = template[end]!;
      if (quote) {
        if (c === quote) quote = "";
      } else if (c === '"' || c === "'") quote = c;
      else if (c === ">") break;
    }
    const tag = template.slice(start, end + 1);
    const classes = /\sclass="([^"]*)"/.exec(tag)?.[1]?.split(/\s+/) ?? [];
    // one tag can hold the marker twice, so it is only listed once
    if (!found.some((f) => f.join(" ") === classes.join(" "))) found.push(classes);
  }
  return found;
}

// a scroll that reaches the end of one of these goes on to the page behind it unless the
// element contains it, which is what overscroll-contain says. the lists nested inside them (a code
// block, a table) are left to chain into the one around them on purpose, or the wheel would stick
// to every code block it passed over
describe("the scrollers that sit over the page do not scroll it when they reach their end", () => {
  const sensai = read("_sensai.html");
  const distributions = read("trial_viewer/_distributions.html");

  it("the SensAI message list", () => {
    const [list, ...rest] = tagsWith(sensai, 'x-ref="messages"');
    expect(rest).toEqual([]);
    expect(list).toContain("overflow-y-auto");
    expect(list).toContain("overscroll-contain");
  });

  it("the SensAI tab strip", () => {
    const [strip, ...rest] = tagsWith(sensai, "flex items-stretch overflow-x-auto");
    expect(rest).toEqual([]);
    expect(strip).toContain("overscroll-contain");
  });

  it("the SensAI message box", () => {
    const [box] = tagsWith(sensai, 'x-ref="inputArea"');
    expect(box).toContain("overscroll-contain");
  });

  it("the distributions list, which the popup over it lets the wheel through to", () => {
    const [list, ...rest] = tagsWith(distributions, "max-h-96 overflow-y-auto");
    expect(rest).toEqual([]);
    expect(list).toContain("overscroll-contain");
  });

  it("the lists of the distributions' column filters", () => {
    const lists = tagsWith(distributions, "max-h-56 overflow-y-auto");
    expect(lists.length).toBeGreaterThan(0);
    for (const list of lists) expect(list).toContain("overscroll-contain");
  });

  it("the profile list", () => {
    const chart = read("trial_viewer/_chart.html");
    const at = chart.indexOf("max-h-80 overflow-y-auto overscroll-contain custom-scrollbar");
    expect(at).toBeGreaterThan(-1);
    // and it is the one that holds the profile rows
    expect(chart.slice(at, at + 300)).toContain("profileVisibleRows");
  });

  it("leaves the markdown tables and code blocks inside a chat message to chain into the list", () => {
    expect(sensai).not.toMatch(/\.sensai-cm-block[^{]*\{[^}]*overscroll-behavior/);
    expect(sensai).not.toMatch(/\.sensai-md table[^{]*\{[^}]*overscroll-behavior/);
  });
});
