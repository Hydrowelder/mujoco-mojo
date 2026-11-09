import { describe, expect, it } from "vitest";

import { renderMarkdown } from "./markdown";

describe("renderMarkdown", () => {
  it("renders ordinary markdown", () => {
    expect(renderMarkdown("plain **bold** and _italic_")).toBe("<p>plain <strong>bold</strong> and <em>italic</em></p>\n");
    expect(renderMarkdown("- one\n- two")).toContain("<li>one</li>");
    expect(renderMarkdown("# Title")).toContain("<h1>Title</h1>");
  });

  it("is empty for empty text", () => {
    expect(renderMarkdown("")).toBe("");
  });

  it("turns a fenced code block into a placeholder carrying its code, url-encoded", () => {
    expect(renderMarkdown('```\nx = "a" & <b>\n```')).toBe(
      `<div class="sensai-cm-block" data-code="${encodeURIComponent('x = "a" & <b>')}"></div>`,
    );
  });

  it("carries the block's language too, url-encoded", () => {
    expect(renderMarkdown('```json\n{"a": 1}\n```')).toBe(
      `<div class="sensai-cm-block" data-code="${encodeURIComponent('{"a": 1}')}" data-lang="json"></div>`,
    );
    expect(renderMarkdown("```c++\nint x;\n```")).toContain('data-lang="c%2B%2B"');
  });

  it("keeps a block's code intact for the editor, even with characters that would break an attribute", () => {
    const code = 'say "hi" & <tag> \'x\' ü ☃\nsecond line';
    const html = renderMarkdown("```\n" + code + "\n```");
    const encoded = /data-code="([^"]*)"/.exec(html)![1]!;
    expect(decodeURIComponent(encoded)).toBe(code);
    expect(html).not.toContain("<tag>");
  });

  it("styles inline code", () => {
    expect(renderMarkdown("use `x = 1` here")).toBe('<p>use <code class="md-inline-code">x = 1</code> here</p>\n');
  });

  it("does not share its renderers with other marked users", async () => {
    const { Marked } = await import("marked");
    expect(new Marked().parse("`x`")).toBe("<p><code>x</code></p>\n");
  });

  // a reply is shown with x-html, so whatever the renderer lets through is what
  // the page runs: nothing a reply repeats may become markup of its own
  describe("raw html in a reply", () => {
    it("is shown as text, as a block", () => {
      expect(renderMarkdown("<img src=x onerror=alert(1)>")).toBe("<p>&lt;img src=x onerror=alert(1)&gt;</p>\n");
      expect(renderMarkdown("<div>\nhello\n</div>")).toBe("<p>&lt;div&gt;\nhello\n&lt;/div&gt;</p>\n");
    });

    it("is shown as text, inline", () => {
      expect(renderMarkdown("text <script>alert(1)</script>")).toBe(
        "<p>text &lt;script&gt;alert(1)&lt;/script&gt;</p>\n",
      );
      expect(renderMarkdown('<a href="javascript:alert(1)">x</a>')).toBe(
        "<p>&lt;a href=&quot;javascript:alert(1)&quot;&gt;x&lt;/a&gt;</p>\n",
      );
    });

    it("is shown as text inside a list, a quote and a link", () => {
      expect(renderMarkdown("- item <b>bold</b>")).toBe("<ul>\n<li>item &lt;b&gt;bold&lt;/b&gt;</li>\n</ul>\n");
      expect(renderMarkdown("> quote <i>x</i>")).toContain("<p>quote &lt;i&gt;x&lt;/i&gt;</p>");
      expect(renderMarkdown("[**bold** <i>x</i>](https://a.b)")).toBe(
        '<p><a href="https://a.b"><strong>bold</strong> &lt;i&gt;x&lt;/i&gt;</a></p>\n',
      );
    });

    it("never leaves a tag of the reply's own in the output", () => {
      for (const text of ["<img src=x onerror=alert(1)>", "text <script>alert(1)</script>", "<iframe src=x></iframe>", "<svg onload=alert(1)>"]) {
        expect(renderMarkdown(text), text).not.toMatch(/<(img|script|iframe|svg)/i);
      }
    });

    it("leaves a plain less-than, greater-than and ampersand readable", () => {
      expect(renderMarkdown("x < 5 and y > 3 & z")).toBe("<p>x &lt; 5 and y &gt; 3 &amp; z</p>\n");
    });
  });

  it("shows html inside inline code literally", () => {
    expect(renderMarkdown("`<b>x</b> & y`")).toBe(
      '<p><code class="md-inline-code">&lt;b&gt;x&lt;/b&gt; &amp; y</code></p>\n',
    );
  });

  describe("a link in a reply", () => {
    it("keeps a web, mail, same-site or fragment address", () => {
      expect(renderMarkdown("[x](https://a.b/c)")).toBe('<p><a href="https://a.b/c">x</a></p>\n');
      expect(renderMarkdown("[x](http://a.b)")).toBe('<p><a href="http://a.b">x</a></p>\n');
      expect(renderMarkdown("[x](mailto:a@b.c)")).toBe('<p><a href="mailto:a@b.c">x</a></p>\n');
      expect(renderMarkdown("[x](/trial/3)")).toBe('<p><a href="/trial/3">x</a></p>\n');
      expect(renderMarkdown("[x](#top)")).toBe('<p><a href="#top">x</a></p>\n');
    });

    it("keeps an address of any case of scheme", () => {
      expect(renderMarkdown("[x](HTTPS://a.b)")).toBe('<p><a href="HTTPS://a.b">x</a></p>\n');
    });

    it("writes an ampersand in the address as an entity", () => {
      expect(renderMarkdown("[x](https://a.b/c?q=1&r=2)")).toBe('<p><a href="https://a.b/c?q=1&amp;r=2">x</a></p>\n');
    });

    it("keeps its title, escaped", () => {
      expect(renderMarkdown('[x](/trial/3 "a \\"t\\" <b>")')).toBe(
        '<p><a href="/trial/3" title="a &quot;t&quot; &lt;b&gt;">x</a></p>\n',
      );
    });

    it("drops a script, data or other scheme and shows only its text", () => {
      for (const href of ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,hi", "vbscript:x", "file:///etc/passwd"]) {
        expect(renderMarkdown(`[x](${href})`), href).toBe("<p>x</p>\n");
      }
    });

    it("drops a scheme written with an entity, which the browser would read as one", () => {
      expect(renderMarkdown("[x](jav&#x61;script:alert(1))")).toBe("<p>x</p>\n");
      expect(renderMarkdown("[x](&#106;avascript:alert(1))")).toBe("<p>x</p>\n");
    });

    it("drops an address that is not a full one, since a relative path means nothing here", () => {
      expect(renderMarkdown("[x](foo/bar)")).toBe("<p>x</p>\n");
    });

    it("drops a script address in an autolink", () => {
      expect(renderMarkdown("<javascript:alert(1)>")).toBe("<p>javascript:alert(1)</p>\n");
    });

    it("keeps an autolink and a bare web address", () => {
      expect(renderMarkdown("<https://a.b>")).toBe('<p><a href="https://a.b">https://a.b</a></p>\n');
      expect(renderMarkdown("www.example.com")).toBe('<p><a href="http://www.example.com">www.example.com</a></p>\n');
    });
  });

  describe("an image in a reply", () => {
    it("keeps a web address, with its alt text and title", () => {
      expect(renderMarkdown('![alt](https://a.b/i.png "T")')).toBe(
        '<p><img src="https://a.b/i.png" alt="alt" title="T"></p>\n',
      );
      expect(renderMarkdown("![alt](/static/i.png)")).toBe('<p><img src="/static/i.png" alt="alt"></p>\n');
    });

    it("escapes the title and writes an ampersand in the address as an entity", () => {
      expect(renderMarkdown('![a](/i.png?x=1&y=2 "t \\"q\\" <z>")')).toBe(
        '<p><img src="/i.png?x=1&amp;y=2" alt="a" title="t &quot;q&quot; &lt;z&gt;"></p>\n',
      );
    });

    it("escapes the alt text", () => {
      expect(renderMarkdown('![a "b" <c>](https://a.b/i.png)')).toContain('alt="a &quot;b&quot; &lt;c&gt;"');
    });

    it("drops a script or data address and shows only the alt text", () => {
      expect(renderMarkdown("![alt <b>](javascript:alert(1))")).toBe("<p>alt &lt;b&gt;</p>\n");
      expect(renderMarkdown("![alt](data:image/svg+xml,x)")).toBe("<p>alt</p>\n");
    });
  });
});
