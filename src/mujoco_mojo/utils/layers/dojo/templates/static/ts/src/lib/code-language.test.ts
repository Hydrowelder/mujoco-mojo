// @vitest-environment happy-dom
import { afterEach, describe, expect, it } from "vitest";

import { EditorState, EditorView, classHighlighter, syntaxHighlighting } from "./codemirror";
import { codeLanguage } from "./code-language";

afterEach(() => {
  document.body.innerHTML = "";
});

// the token classes CodeMirror gives `code` when it is shown as the language `name`
function tokens(name: string, code: string): Set<string> {
  const parent = document.createElement("div");
  document.body.appendChild(parent);
  const language = codeLanguage(name);
  new EditorView({
    state: EditorState.create({
      doc: code,
      extensions: [...(language ? [language] : []), syntaxHighlighting(classHighlighter)],
    }),
    parent,
  });
  return new Set(
    [...parent.querySelectorAll(".cm-line [class]")].flatMap((el) => [...el.classList]).filter((c) => c.startsWith("tok-")),
  );
}

describe("which names have a language", () => {
  it.each(["json", "python", "py", "python3", "bash", "sh", "shell", "zsh", "console"])("%s has one", (name) => {
    expect(codeLanguage(name)).not.toBeNull();
  });

  it.each(["", "text", "toml", "yaml", "mermaid", "javascript", "pythonic"])("%j has none", (name) => {
    expect(codeLanguage(name)).toBeNull();
  });

  it("ignores case and stray spaces, which a model may write after a fence", () => {
    expect(codeLanguage("Python")).not.toBeNull();
    expect(codeLanguage(" BASH ")).not.toBeNull();
    expect(codeLanguage("JSON")).not.toBeNull();
  });
});

describe("what each language colors", () => {
  it("JSON: its keys, strings, numbers and true", () => {
    const classes = tokens("json", '{"a": 1, "b": "x", "c": true}');

    for (const expected of ["tok-propertyName", "tok-string", "tok-number", "tok-bool"]) {
      expect(classes, expected).toContain(expected);
    }
  });

  it("Python: its keywords, strings, numbers and comments", () => {
    const classes = tokens("python", '# hi\ndef f(n=3):\n    return "x"\n');

    for (const expected of ["tok-comment", "tok-keyword", "tok-number", "tok-string", "tok-definition"]) {
      expect(classes, expected).toContain(expected);
    }
  });

  it("shell: its options, strings and comments", () => {
    const classes = tokens("bash", '# hi\nmojo run --n-trial 10 "a b"\n');

    for (const expected of ["tok-comment", "tok-propertyName", "tok-number", "tok-string"]) {
      expect(classes, expected).toContain(expected);
    }
  });

  it("each language is its own: a Python keyword is not one in a shell command, nor a shell option in Python", () => {
    expect(tokens("python", "def f(): pass")).toContain("tok-keyword");
    expect(tokens("bash", "def f(): pass")).not.toContain("tok-keyword");
    expect(tokens("bash", "run --flag")).toContain("tok-propertyName");
    expect(tokens("python", "run --flag")).not.toContain("tok-propertyName");
  });

  it("a name with no language gets no colors", () => {
    expect(tokens("toml", 'name = "x"').size).toBe(0);
  });
});
