// escaping text that goes into a string of html set with innerHTML or x-html,
// so what a reply, a column name or a distribution parameter says is shown as
// written instead of read as markup

// the text with `&`, `<`, `>` and both kinds of quote written as entities, safe
// in element content and inside a quoted attribute
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
