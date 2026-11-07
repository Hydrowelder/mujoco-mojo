// markdown rendering for sensai's assistant message bubbles. a marked
// instance of its own, so the renderers below apply here and nowhere else (the
// shared `marked` singleton would hand them to anything else that imports it,
// see settings-panel.ts's own instance).
//
// a reply is set with x-html and can repeat text a user or a trial controls
// (a column name, a value), so nothing it says may become markup of its own:
// raw html and the contents of inline code are shown as written, and a link or
// image is only kept when its address is one of the kinds in isSafeUrl.

import { Marked, type Tokens } from "marked";

import { escapeHtml } from "./html";

// whether a link or image address may be kept: a web or mail address, a
// same-site path or a fragment. anything else (javascript:, data:, vbscript:,
// or a scheme written as an entity so that it only reads as one in the browser)
// is dropped. this is an allowlist from the start of the address on purpose
function isSafeUrl(href: string): boolean {
  return /^(?:https?:|mailto:|#|\/)/i.test(href);
}

const sensaiMarked = new Marked({
  renderer: {
    code({ text, lang }: Tokens.Code): string {
      const encoded = encodeURIComponent(text);
      const langAttr = lang ? ` data-lang="${encodeURIComponent(lang)}"` : "";
      return `<div class="sensai-cm-block" data-code="${encoded}"${langAttr}></div>`;
    },
    codespan({ text }: Tokens.Codespan): string {
      return `<code class="md-inline-code">${escapeHtml(text)}</code>`;
    },
    html({ text, block }: Tokens.HTML | Tokens.Tag): string {
      const shown = escapeHtml(text);
      return block ? `<p>${shown.trim()}</p>\n` : shown;
    },
    link({ href, title, tokens }: Tokens.Link): string {
      const text = this.parser.parseInline(tokens);
      if (!isSafeUrl(href)) return text;
      const titleAttr = title ? ` title="${escapeHtml(title)}"` : "";
      return `<a href="${escapeHtml(href)}"${titleAttr}>${text}</a>`;
    },
    image({ href, title, text }: Tokens.Image): string {
      if (!isSafeUrl(href)) return escapeHtml(text);
      const titleAttr = title ? ` title="${escapeHtml(title)}"` : "";
      return `<img src="${escapeHtml(href)}" alt="${escapeHtml(text)}"${titleAttr}>`;
    },
  },
});

// a fenced code block becomes an empty placeholder div carrying its code (and
// language) url-encoded, which initSensAICodeBlocks later turns into a
// read-only code editor
export function renderMarkdown(text: string): string {
  return sensaiMarked.parse(text) as string;
}
