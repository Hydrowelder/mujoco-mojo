// which CodeMirror language colors a fenced code block, by the name after its
// opening fence. a name with no language here is shown as plain text

import { StreamLanguage, json, pythonMode, shellMode, type Extension } from "./codemirror";

// the names a model writes after a fence, by language
const NAMES: Record<string, string[]> = {
  json: ["json"],
  python: ["python", "py", "python3"],
  shell: ["bash", "sh", "shell", "zsh", "console"],
};

const BY_NAME = new Map<string, string>(
  Object.entries(NAMES).flatMap(([language, names]) => names.map((name) => [name, language] as const)),
);

// the language extension for a fence's name (any case), or null when there is none
export function codeLanguage(name: string): Extension | null {
  switch (BY_NAME.get(name.trim().toLowerCase())) {
    case "json":
      return json();
    case "python":
      return StreamLanguage.define(pythonMode);
    case "shell":
      return StreamLanguage.define(shellMode);
    default:
      return null;
  }
}
