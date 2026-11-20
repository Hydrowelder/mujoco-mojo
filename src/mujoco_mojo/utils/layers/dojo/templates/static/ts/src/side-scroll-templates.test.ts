import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

// the Jinja templates sit beside static/, not under it
const read = (name: string) => readFileSync(resolve(import.meta.dirname, "../../../partials", name), "utf-8");

// every opening <div> of `template`, up to its `>` (an attribute can hold one, so quotes are followed)
function divs(template: string): string[] {
  const found: string[] = [];
  for (let at = template.indexOf("<div"); at !== -1; at = template.indexOf("<div", at + 1)) {
    let quote = "";
    let end = at;
    for (; end < template.length; end++) {
      const c = template[end]!;
      if (quote) {
        if (c === quote) quote = "";
      } else if (c === '"' || c === "'") quote = c;
      else if (c === ">") break;
    }
    found.push(template.slice(at, end + 1));
  }
  return found;
}

const strips = (template: string) => divs(template).filter((tag) => tag.includes("overflow-x-auto"));

// a strip that scrolls only sideways, with nothing under it to scroll the other way, so the wheel can be given to it.
// the distributions table is not one: it scrolls both ways, and a wheel turn over it is the page's
describe("every strip that scrolls sideways lets the wheel scroll it", () => {
  const templates: Record<string, string> = {
    "_sensai.html": read("_sensai.html"),
    "trial_viewer/_macros.html": read("trial_viewer/_macros.html"),
    "trial_viewer/_series_panel.html": read("trial_viewer/_series_panel.html"),
    "trial_viewer/_signal_lab.html": read("trial_viewer/_signal_lab.html"),
  };

  for (const [name, template] of Object.entries(templates)) {
    it(`${name}`, () => {
      const found = strips(template);
      expect(found.length).toBeGreaterThan(0);
      for (const tag of found) expect(tag, tag).toMatch(/\sx-hscroll(\.[\w-]+)*[\s>=]/);
    });
  }

  it("keeps the wheel on the selected signals at their ends, so the page does not scroll", () => {
    const [ribbon, ...rest] = divs(templates["trial_viewer/_series_panel.html"]!).filter((tag) => tag.includes('x-ref="ribbon"'));
    expect(rest).toEqual([]);
    expect(ribbon).toMatch(/\sx-hscroll\.contain[\s>=]/);
    // and a sideways swipe at their end does not carry on to the page either
    expect(ribbon).toMatch(/class="[^"]*\boverscroll-contain\b/);
  });

  it("keeps the open tab of the shared tab strip (the plot tabs and the Lab's) in view", () => {
    const [strip, ...rest] = divs(templates["trial_viewer/_macros.html"]!).filter((tag) => tag.includes("x-reveal-active"));
    expect(rest).toEqual([]);
    expect(strip).toContain('x-reveal-active="{{ active_id_expr }}"');
    // on the strip that scrolls, which is the one the tabs are in
    expect(strip).toContain("overflow-x-auto");
  });

  // SensAI keeps its own tab markup rather than the shared macro, so it needs the same two marks: the id the
  // strip follows, and the id on each tab for it to find. it had neither, and its open chat was never revealed
  it("keeps the open chat of SensAI's tab strip in view", () => {
    const sensai = templates["_sensai.html"]!;
    const [strip, ...rest] = divs(sensai).filter((tag) => tag.includes("x-reveal-active"));
    expect(rest).toEqual([]);
    expect(strip).toContain('x-reveal-active="activeId"');
    expect(strip).toContain("overflow-x-auto");
    expect(divs(sensai).filter((tag) => tag.includes(':data-tab-id="tab.id"'))).toHaveLength(1);
  });

  // a strip that follows an id finds the tabs by `data-tab-id`, so a template that marks one has to mark the other
  for (const [name, template] of Object.entries(templates)) {
    it(`${name} marks the tabs of every strip that follows the open one`, () => {
      const marked = divs(template).filter((tag) => tag.includes("x-reveal-active")).length;
      const tabs = divs(template).filter((tag) => tag.includes("data-tab-id")).length;
      expect(tabs).toBeGreaterThanOrEqual(marked);
    });
  }

  it("does not mark the distributions table, which also scrolls the other way", () => {
    const distributions = read("trial_viewer/_distributions.html");
    expect(strips(distributions).length).toBeGreaterThan(0);
    expect(distributions).not.toContain("x-hscroll");
  });
});
