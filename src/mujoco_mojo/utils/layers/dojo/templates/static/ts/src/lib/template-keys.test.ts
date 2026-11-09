import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

// the Jinja templates sit beside static/, not under it
const TEMPLATES = resolve(import.meta.dirname, "../../../..");

// every page and partial template, not the built or vendored files in static/
function templateFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "static" ? [] : templateFiles(path);
    return entry.name.endsWith(".html") ? [path] : [];
  });
}

// the names of the alpine key handlers in a template, such as `@keydown.enter.window`
function keyHandlerNames(html: string): string[] {
  return [...html.matchAll(/@(?:keydown|keyup|keypress)(?:\.[\w-]+)*(?==)/g)].map((m) => m[0]);
}

describe("the templates", () => {
  it("are found", () => {
    const files = templateFiles(TEMPLATES);
    expect(files.some((f) => f.endsWith("base.html"))).toBe(true);
    expect(files.some((f) => f.endsWith("_sensai.html"))).toBe(true);
    expect(files.length).toBeGreaterThan(10);
  });

  // alpine's .prevent calls preventDefault() before the expression runs, so on
  // a window-level key handler it cancels what that key does on the whole page:
  // no newline from Enter in a textarea, no click from Enter on a button. a
  // handler that only sometimes wants to stop the key has to call
  // $event.preventDefault() itself, inside its condition.
  it("never prevent a key's default from a window-level handler", () => {
    const offenders = templateFiles(TEMPLATES).flatMap((file) =>
      keyHandlerNames(readFileSync(file, "utf-8"))
        .filter((name) => name.includes(".window") && name.includes(".prevent"))
        .map((name) => `${file.slice(TEMPLATES.length + 1)}: ${name}`),
    );
    expect(offenders).toEqual([]);
  });

  it("recognize a window-level .prevent handler when one is written", () => {
    expect(keyHandlerNames('<div @keydown.enter.window.prevent="go()">')).toEqual(["@keydown.enter.window.prevent"]);
    expect(keyHandlerNames('<div @keydown.window.prevent.enter="go()">')).toEqual(["@keydown.window.prevent.enter"]);
    expect(keyHandlerNames('<div @keydown.enter="go()" @click.prevent="x()">')).toEqual(["@keydown.enter"]);
  });
});
