import { describe, expect, it } from "vitest";

import { escapeHtml } from "./html";

describe("escapeHtml", () => {
  it("leaves plain text as it is", () => {
    expect(escapeHtml("plain text 123")).toBe("plain text 123");
    expect(escapeHtml("")).toBe("");
  });

  it("writes each markup character as an entity", () => {
    expect(escapeHtml("&")).toBe("&amp;");
    expect(escapeHtml("<")).toBe("&lt;");
    expect(escapeHtml(">")).toBe("&gt;");
    expect(escapeHtml('"')).toBe("&quot;");
    expect(escapeHtml("'")).toBe("&#39;");
  });

  it("escapes the ampersand first so an entity it writes is not escaped again", () => {
    expect(escapeHtml("<&>")).toBe("&lt;&amp;&gt;");
    expect(escapeHtml("&lt;")).toBe("&amp;lt;");
  });

  it("escapes every occurrence", () => {
    expect(escapeHtml("<<>>&&\"\"''")).toBe("&lt;&lt;&gt;&gt;&amp;&amp;&quot;&quot;&#39;&#39;");
  });

  it("turns a tag into text", () => {
    expect(escapeHtml('<img src="x" onerror=\'alert(1)\'>')).toBe(
      "&lt;img src=&quot;x&quot; onerror=&#39;alert(1)&#39;&gt;",
    );
  });

  it("leaves other characters, such as non-ASCII text, alone", () => {
    expect(escapeHtml("ü ☃ θ")).toBe("ü ☃ θ");
  });
});
