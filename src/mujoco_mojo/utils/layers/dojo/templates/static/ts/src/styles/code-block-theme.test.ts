import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// what makes a code block in a SensAI reply readable in both themes, checked
// where it is decided: the theme tokens and the rules in the chat's stylesheet.
// a block that looked fine in light mode and vanished in dark mode was the
// sunken surface being the same slate as the bubble it sits in

const THEME = readFileSync(resolve(import.meta.dirname, "theme.css"), "utf-8");
const CHAT = readFileSync(resolve(import.meta.dirname, "../../../../partials/_sensai.html"), "utf-8");

// the text between the braces of the block that starts at `opener`
function block(css: string, opener: string): string {
  const start = css.indexOf(opener);
  if (start === -1) throw new Error(`no ${opener} in the stylesheet`);
  let depth = 0;
  for (let i = css.indexOf("{", start); i < css.length; i++) {
    if (css[i] === "{") depth++;
    if (css[i] === "}" && --depth === 0) return css.slice(css.indexOf("{", start) + 1, i);
  }
  throw new Error(`${opener} is not closed`);
}

const LIGHT = block(THEME, "@theme static");
const DARK = block(THEME, ".dark {");

function token(scope: string, name: string): string | undefined {
  return new RegExp(`${name}:\\s*([^;]+);`).exec(scope)?.[1]?.trim();
}

// the declarations of the chat's rule for `selector`
function rule(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const found = new RegExp(`${escaped}\\s*\\{([^}]*)\\}`).exec(CHAT);
  if (!found) throw new Error(`no rule for ${selector}`);
  return found[1]!;
}

const codeTokens = [...new Set([...CHAT.matchAll(/var\((--color-code-[a-z]+)\)/g)].map((m) => m[1]!))];

describe("the colors of a code block", () => {
  it("are tokens the chat's stylesheet uses, and there are some", () => {
    expect(codeTokens.sort()).toEqual([
      "--color-code-atom",
      "--color-code-comment",
      "--color-code-key",
      "--color-code-number",
      "--color-code-punct",
      "--color-code-string",
    ]);
  });

  it("each have a light value and a dark one", () => {
    for (const name of codeTokens) {
      expect(token(LIGHT, name), `${name} in light`).toBeDefined();
      expect(token(DARK, name), `${name} under .dark`).toBeDefined();
    }
  });

  it("are lighter steps in dark mode, for the syntax colors that carry meaning", () => {
    for (const name of ["--color-code-key", "--color-code-string", "--color-code-number", "--color-code-atom"]) {
      const light = /-(\d+)\)/.exec(token(LIGHT, name)!)![1]!;
      const dark = /-(\d+)\)/.exec(token(DARK, name)!)![1]!;
      expect(Number(dark), name).toBeLessThan(Number(light));
    }
  });
});

describe("the block itself", () => {
  const body = rule(".sensai-cm-block");

  it("is a well, which is darker than the surface of the bubble in dark mode", () => {
    expect(body).toContain("background: var(--color-well)");
    expect(token(DARK, "--color-well")).toBeDefined();
    expect(token(DARK, "--color-well")).not.toBe(token(DARK, "--color-surface"));
  });

  it("is not the sunken surface, which is the same as the bubble's surface in dark mode", () => {
    expect(body).not.toContain("--color-surface-sunken");
  });

  it("is not the same as the surface in light mode either", () => {
    expect(token(LIGHT, "--color-well")).not.toBe(token(LIGHT, "--color-surface"));
  });

  it("has an edge that shows against both the bubble and the block in dark mode", () => {
    expect(body).toContain("border: 1px solid var(--color-subtle)");
    expect(token(DARK, "--color-subtle")).not.toBe(token(DARK, "--color-surface"));
    expect(token(DARK, "--color-subtle")).not.toBe(token(DARK, "--color-well"));
  });

  it("writes its text in a token that is readable on the well in both themes", () => {
    expect(rule(".sensai-cm-block .cm-editor")).toContain("color: var(--color-ink-strong)");
    expect(token(LIGHT, "--color-ink-strong")).not.toBe(token(LIGHT, "--color-well"));
    expect(token(DARK, "--color-ink-strong")).not.toBe(token(DARK, "--color-well"));
  });
});

describe("the copy button", () => {
  it("is filled like the block, so code scrolling under it does not show through", () => {
    expect(rule(".sensai-cm-copy")).toContain("background: var(--color-well)");
  });

  it("turns the success color once it has copied", () => {
    expect(rule('.sensai-cm-copy[data-copied="true"]')).toContain("color: var(--color-success-500)");
  });

  it("uses no color that is written out, in the block's rules or the button's", () => {
    const css = CHAT.slice(CHAT.indexOf(".sensai-cm-block {"), CHAT.indexOf("</style>"));

    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(css).not.toMatch(/\brgba?\(/);
  });
});
