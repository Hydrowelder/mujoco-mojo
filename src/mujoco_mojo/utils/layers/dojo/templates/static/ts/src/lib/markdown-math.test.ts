import { describe, expect, it } from "vitest";

import { renderMarkdown } from "./markdown";

// the placeholder math leaves: the TeX carried url-encoded, and the source as its text
const math = (tex: string, display = false, source = display ? `$$${tex}$$` : `$${tex}$`) =>
  `<span class="sensai-math${display ? " sensai-math-display" : ""}" data-tex="${encodeURIComponent(tex)}" data-display="${display}">${source}</span>`;

describe("math in a line", () => {
  it("is a placeholder carrying the TeX and, as its text, the source", () => {
    expect(renderMarkdown("the area is $\\pi r^2$ here")).toBe(`<p>the area is ${math("\\pi r^2")} here</p>\n`);
  });

  it("can be several in one paragraph", () => {
    expect(renderMarkdown("$a$ and $b$, then $c$")).toBe(`<p>${math("a")} and ${math("b")}, then ${math("c")}</p>\n`);
  });

  it("keeps its TeX intact: underscores, stars and carets are not emphasis", () => {
    expect(renderMarkdown("$a_1 * b_2 + c^{*}$ and $x_i$")).toBe(
      `<p>${math("a_1 * b_2 + c^{*}")} and ${math("x_i")}</p>\n`,
    );
  });

  it("can have an escaped dollar sign and a backslash in it", () => {
    expect(renderMarkdown("$a \\$ b \\\\ c$")).toBe(`<p>${math("a \\$ b \\\\ c")}</p>\n`);
  });

  it("may sit next to punctuation and the end of a word", () => {
    expect(renderMarkdown("($x$), ($y$.) and $z$s")).toBe(
      `<p>(${math("x")}), (${math("y")}.) and ${math("z")}s</p>\n`,
    );
  });

  it("is display math when written with two dollar signs, wherever they are", () => {
    expect(renderMarkdown("then $$x = 1$$ holds")).toBe(`<p>then ${math("x = 1", true)} holds</p>\n`);
  });

  it("can be display math over several lines of a paragraph", () => {
    expect(renderMarkdown("so $$a\n= b$$ done")).toBe(`<p>so ${math("a\n= b", true, "$$a\n= b$$")} done</p>\n`);
  });

  it("is not found when a later line of it starts like a list item, since markdown splits the paragraph there first", () => {
    // a known limit: display math that is wanted whole belongs on lines of its own, which is taken before this
    expect(renderMarkdown("so $$a\n+ b$$ done")).not.toContain("sensai-math");
  });
});

describe("what is not math", () => {
  it.each([
    ["from $5 to $10", "prices"],
    ["it costs $5. Or $10.", "prices with full stops"],
    ["between $5-$10 and $20", "a range of prices"],
    ["a $ b", "a lone dollar sign"],
    ["$ x $", "spaces just inside the dollars"],
    ["$x $", "a space before the closing one"],
    ["$ x$", "a space after the opening one"],
    ["$x$5", "a digit right after the closing one"],
    ["$$", "two dollars and nothing"],
    ["$$ $$", "display math that is empty"],
    ["$x", "an opening one with no end"],
    ["costs $5 each\nand $6 total", "prices on two lines"],
    ["a $x\ny$ b", "an opening one whose end is on the next line"],
  ])("is left as text: %s (%s)", (text) => {
    expect(renderMarkdown(text)).not.toContain("sensai-math");
  });

  it("keeps the text of such a line as it was", () => {
    expect(renderMarkdown("from $5 to $10")).toBe("<p>from $5 to $10</p>\n");
  });

  it("is an escaped dollar sign, which is just a dollar sign", () => {
    expect(renderMarkdown("\\$x\\$ is not math")).toBe("<p>$x$ is not math</p>\n");
  });

  it("is not looked for in inline code", () => {
    expect(renderMarkdown("run `echo $HOME and $x$` now")).toBe(
      '<p>run <code class="md-inline-code">echo $HOME and $x$</code> now</p>\n',
    );
  });

  it("is not looked for in a code block", () => {
    const html = renderMarkdown("```bash\necho $x$ and $$y$$\n```");

    expect(html).not.toContain("sensai-math");
    expect(html).toContain("sensai-cm-block");
  });
});

describe("math on lines of its own", () => {
  it("is a paragraph holding display math", () => {
    expect(renderMarkdown("$$\nE = mc^2\n$$")).toBe(`<p>${math("E = mc^2", true, "$$\nE = mc^2\n$$")}</p>\n`);
  });

  it("can be written on a single line", () => {
    expect(renderMarkdown("$$E = mc^2$$")).toBe(`<p>${math("E = mc^2", true)}</p>\n`);
  });

  it("keeps lines that would otherwise be a list, a heading or a quote inside it", () => {
    const html = renderMarkdown("$$\na\n- b\n# c\n> d\n$$");

    expect(html).toBe(`<p>${math("a\n- b\n# c\n> d", true, "$$\na\n- b\n# c\n&gt; d\n$$")}</p>\n`);
    expect(html).not.toContain("<li>");
    expect(html).not.toContain("<h1>");
  });

  it("can have a blank line inside it", () => {
    const html = renderMarkdown("$$\na\n\nb\n$$");

    expect(html).toContain("sensai-math-display");
    expect(html.match(/<p>/g)).toHaveLength(1);
  });

  it("sits between paragraphs without joining them", () => {
    expect(renderMarkdown("before\n\n$$\nx\n$$\n\nafter")).toBe(
      `<p>before</p>\n<p>${math("x", true, "$$\nx\n$$")}</p>\n<p>after</p>\n`,
    );
  });

  it("can follow a line of text with no blank line between", () => {
    const html = renderMarkdown("where\n$$\nx\n$$");

    expect(html).toContain("sensai-math-display");
    expect(html).toContain("where");
  });

  it("is in a list item too", () => {
    expect(renderMarkdown("- the area is $a$\n- done")).toBe(
      `<ul>\n<li>the area is ${math("a")}</li>\n<li>done</li>\n</ul>\n`,
    );
  });

  it("can be two of them in a row", () => {
    const html = renderMarkdown("$$\na\n$$\n\n$$\nb\n$$");

    expect(html.match(/sensai-math-display/g)).toHaveLength(2);
  });

  it("is still math in the line when text follows the closing dollars", () => {
    expect(renderMarkdown("$$x$$ and more")).toBe(`<p>${math("x", true)} and more</p>\n`);
  });
});

describe("what math can carry", () => {
  it("shows the source as text, never as markup", () => {
    const html = renderMarkdown("$<img src=x onerror=alert(1)>$");

    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img src=x onerror=alert(1)&gt;");
  });

  it("carries the TeX in the attribute in a form that cannot break out of it", () => {
    const html = renderMarkdown('$a" onmouseover="x$');
    const tex = /data-tex="([^"]*)"/.exec(html)![1]!;

    expect(decodeURIComponent(tex)).toBe('a" onmouseover="x');
    expect(html.match(/data-tex=/g)).toHaveLength(1);
    expect(html).not.toContain(' onmouseover="x"');
  });

  it("carries TeX with angle brackets and ampersands exactly", () => {
    const html = renderMarkdown("$a < b \\& c > d$");
    const tex = /data-tex="([^"]*)"/.exec(html)![1]!;

    expect(decodeURIComponent(tex)).toBe("a < b \\& c > d");
  });

  it("works beside the other things a reply holds", () => {
    const html = renderMarkdown("**bold $x$** and [a link $y$](https://example.com)");

    expect(html).toContain(`<strong>bold ${math("x")}</strong>`);
    expect(html).toContain(`<a href="https://example.com">a link ${math("y")}</a>`);
  });
});
