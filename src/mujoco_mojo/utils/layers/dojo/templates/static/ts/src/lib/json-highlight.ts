// syntax coloring for the JSON editor's read-only overlay: the text turned into
// HTML spans classed with the design tokens. the text is HTML-escaped first, so
// whatever is in the config can't add markup of its own

const TOKEN =
  /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?|[\[\]{},])|(\S+)/g;

// keys, strings, numbers, true/false and null each get a color, punctuation
// stays neutral, and anything that isn't JSON at all is underlined in red
export function highlightJson(raw: string): string {
  if (!raw) return "";
  const html = raw.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return html.replace(TOKEN, (match, _token, _i1, _i2, _i3, garbage: string | undefined) => {
    if (garbage)
      return `<span class="text-danger-500 underline decoration-wavy underline-offset-2 font-bold">${garbage}</span>`;
    let cls = "text-ink-secondary";
    if (/^"/.test(match)) {
      cls = /:$/.test(match) ? "text-accent-600 dark:text-accent-300" : "text-success-600 dark:text-success-400";
    } else if (/true|false/.test(match)) {
      cls = "text-secondary-600 dark:text-secondary-400";
    } else if (/null/.test(match)) {
      cls = "text-danger-500";
    } else if (/-?\d/.test(match)) {
      cls = "text-warning-600 dark:text-warning-500";
    }
    return `<span class="${cls}">${match}</span>`;
  });
}
