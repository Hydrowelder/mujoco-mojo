// markdown rendering for sensai's assistant message bubbles. a marked
// instance of its own, so the renderers below apply here and nowhere else (the
// shared `marked` singleton would hand them to anything else that imports it,
// see settings-panel.ts's own instance).
//
// a reply is set with x-html and can repeat text a user or a trial controls
// (a column name, a value), so nothing it says may become markup of its own:
// raw html and the contents of inline code are shown as written, and a link or
// image is only kept when its address is one of the kinds in isSafeUrl.

import { Marked, type Tokens, type TokenizerAndRendererExtension } from "marked";

import { escapeHtml } from "./html";

// whether a link or image address may be kept: a web or mail address, a
// same-site path or a fragment. anything else (javascript:, data:, vbscript:,
// or a scheme written as an entity so that it only reads as one in the browser)
// is dropped. this is an allowlist from the start of the address on purpose
function isSafeUrl(href: string): boolean {
  return /^(?:https?:|mailto:|#|\/)/i.test(href);
}

// math is written $x^2$ in a line and $$...$$ on lines of its own. like a code
// block it leaves an inert placeholder, which carries the TeX url-encoded and,
// for anything that cannot load the typesetter, the source as its text (escaped,
// so nothing in it can become markup): renderMath in lib/math.ts typesets it
function mathPlaceholder(tex: string, display: boolean, source: string): string {
  const kind = display ? "sensai-math sensai-math-display" : "sensai-math";
  return `<span class="${kind}" data-tex="${encodeURIComponent(tex)}" data-display="${display}">${escapeHtml(source)}</span>`;
}

// math in the middle of a line. `$$...$$` is display math wherever it is; a single
// `$` follows the rule that keeps prices out of it: the opening one has no space
// after it, the closing one none before it and no digit after it, so that
// "from $5 to $10" is not math, and a line cannot hold an unfinished one
const inlineMath: TokenizerAndRendererExtension = {
  name: "inlineMath",
  level: "inline",
  start: (src) => src.indexOf("$"),
  tokenizer(src) {
    const display = /^\$\$([\s\S]+?)\$\$/.exec(src);
    if (display?.[1]?.trim()) {
      return { type: "inlineMath", raw: display[0], text: display[1].trim(), display: true };
    }
    const inline = /^\$(?!\s)((?:[^$\\\n]|\\.)+?)(?<!\s)\$(?!\d)/.exec(src);
    if (inline?.[1]) return { type: "inlineMath", raw: inline[0], text: inline[1], display: false };
    return undefined;
  },
  renderer: (token) => mathPlaceholder(String(token["text"]), token["display"] === true, token.raw),
};

// display math on lines of its own, which may have blank lines and lines that
// look like a list or a heading inside it, so it is taken before a paragraph can
// split it. it has to begin a line, and end its last line
const blockMath: TokenizerAndRendererExtension = {
  name: "blockMath",
  level: "block",
  start: (src) => src.search(/^\$\$[ \t]*$|^\$\$[^\n]*\$\$[ \t]*$/m),
  tokenizer(src) {
    const found = /^\$\$[ \t]*\n?([\s\S]+?)\n?[ \t]*\$\$[ \t]*(?:\n|$)/.exec(src);
    if (found?.[1]?.trim()) {
      return { type: "blockMath", raw: found[0], text: found[1].trim(), display: true };
    }
    return undefined;
  },
  renderer: (token) => `<p>${mathPlaceholder(String(token["text"]), true, token.raw.trim())}</p>\n`,
};

const sensaiMarked = new Marked({
  extensions: [blockMath, inlineMath],
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
