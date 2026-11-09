// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from "vitest";

import type { KatexOptions } from "katex";

import { renderMarkdown } from "./markdown";
import { KATEX_OPTIONS, fetchedOnce, loadKatex, renderMath, type Katex } from "./math";

// the Dojo's pages have a doctype, so they are in the browser's standards mode, which KaTeX needs and
// checks once, when it is loaded. happy-dom reports no mode, which KaTeX takes for quirks mode and then
// will not render, so this says what the pages are before anything loads it
Object.defineProperty(document, "compatMode", { value: "CSS1Compat", configurable: true });

// a reply as the page has it before its math is typeset: the placeholders markdown leaves
function reply(markdown: string): HTMLElement {
  const container = document.createElement("div");
  container.innerHTML = renderMarkdown(markdown);
  document.body.appendChild(container);
  return container;
}

// a stand-in for KaTeX that writes the TeX it was given in brackets
function standIn() {
  const render = vi.fn((tex: string, el: HTMLElement, _options?: KatexOptions) => {
    el.textContent = `[${tex}]`;
  });
  const katex: Katex = { render };
  return { katex, render, load: () => Promise.resolve(katex) };
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("renderMath with a stand-in typesetter", () => {
  it("typesets each placeholder from the TeX it carries", async () => {
    const container = reply("the area is $\\pi r^2$ and $$E = mc^2$$");
    const { load, render } = standIn();

    const typeset = await renderMath(container, load);

    expect(typeset).toBe(true);
    expect(render).toHaveBeenCalledTimes(2);
    expect([...container.querySelectorAll(".sensai-math")].map((el) => el.textContent)).toEqual(["[\\pi r^2]", "[E = mc^2]"]);
  });

  it("sets display mode for display math and not for math in a line", async () => {
    const container = reply("in a line $a$ and\n\n$$\nb\n$$");
    const { load, render } = standIn();

    await renderMath(container, load);

    expect(render.mock.calls.map(([tex, , options]) => [tex, options?.displayMode])).toEqual([
      ["a", false],
      ["b", true],
    ]);
  });

  it("gives the typesetter the narrow options: no links or images, no failure for a mistake", async () => {
    const container = reply("$x$");
    const { load, render } = standIn();

    await renderMath(container, load);

    const options = render.mock.calls[0]![2]!;
    expect(options.trust).toBe(false);
    expect(options.throwOnError).toBe(false);
    expect(options.strict).toBe("ignore");
    expect(options.output).toBe("mathml");
    expect(KATEX_OPTIONS.trust).toBe(false);
    expect(KATEX_OPTIONS.output).toBe("mathml");
  });

  it("decodes TeX that was encoded for the attribute, special characters and all", async () => {
    const tex = '\\text{50% of "x" & ü} < 1';
    const container = reply(`$${tex}$`);
    const { load, render } = standIn();

    await renderMath(container, load);

    expect(render.mock.calls[0]![0]).toBe(tex);
  });

  it("does nothing, and does not load the typesetter, for a reply with no math", async () => {
    const container = reply("just **words** and `code $x$`\n\n```bash\necho $y$\n```");
    const load = vi.fn(() => Promise.resolve(standIn().katex));

    const typeset = await renderMath(container, load);

    expect(typeset).toBe(false);
    expect(load).not.toHaveBeenCalled();
  });

  it("leaves what is not math alone", async () => {
    const container = reply("`code` and $x$\n\n```bash\nls\n```");
    const { load } = standIn();

    await renderMath(container, load);

    expect(container.querySelector("code")!.textContent).toBe("code");
    expect(container.querySelector(".sensai-cm-block")!.textContent).toBe("");
  });

  it("does not typeset the same placeholder twice", async () => {
    const container = reply("$x$");
    const { load, render } = standIn();

    expect(await renderMath(container, load)).toBe(true);
    expect(await renderMath(container, load)).toBe(false);

    expect(render).toHaveBeenCalledTimes(1);
  });

  it("does it once when called again before the first call is done", async () => {
    const container = reply("$x$ and $y$");
    const { katex, render } = standIn();
    let release!: () => void;
    const load = () => new Promise<Katex>((resolve) => (release = () => resolve(katex)));

    const first = renderMath(container, load);
    const second = renderMath(container, load);
    release();

    expect(await first).toBe(true);
    expect(await second).toBe(false);
    expect(render).toHaveBeenCalledTimes(2);
  });

  it("picks up math that arrives later in the same container", async () => {
    const container = reply("$x$");
    const { load, render } = standIn();
    await renderMath(container, load);

    container.insertAdjacentHTML("beforeend", renderMarkdown("and $y$"));

    expect(await renderMath(container, load)).toBe(true);
    expect(render).toHaveBeenCalledTimes(2);
  });

  describe("when the typesetter cannot be loaded", () => {
    it("says it did nothing and leaves the source showing", async () => {
      const container = reply("so $x^2$ holds");

      const typeset = await renderMath(container, () => Promise.reject(new Error("offline")));

      expect(typeset).toBe(false);
      expect(container.querySelector(".sensai-math")!.textContent).toBe("$x^2$");
    });

    it("tries again on the next call, since it is not marked done", async () => {
      const container = reply("so $x^2$ holds");
      await renderMath(container, () => Promise.reject(new Error("offline")));
      const { load, render } = standIn();

      const typeset = await renderMath(container, load);

      expect(typeset).toBe(true);
      expect(render).toHaveBeenCalledTimes(1);
    });

    it("is the same when typesetting itself throws", async () => {
      const container = reply("$x$");
      const broken: Katex = {
        render() {
          throw new Error("boom");
        },
      };

      expect(await renderMath(container, () => Promise.resolve(broken))).toBe(false);
      expect(container.querySelector(".sensai-math")!.hasAttribute("data-math-init")).toBe(false);
    });
  });
});

describe("renderMath with KaTeX", () => {
  it("typesets math in a line", async () => {
    const container = reply("Euler: $e^{i\\pi} + 1 = 0$ is neat");

    expect(await renderMath(container)).toBe(true);

    const typeset = container.querySelector(".sensai-math")!;
    expect(typeset.querySelector(".katex")).not.toBeNull();
    expect(typeset.querySelector("math")).not.toBeNull();
    expect(typeset.querySelector('math[display="block"]')).toBeNull();
    // the TeX stays available to anything reading the page, as KaTeX's own annotation
    expect(typeset.querySelector('annotation[encoding="application/x-tex"]')!.textContent).toBe("e^{i\\pi} + 1 = 0");
  });

  it("typesets display math as a block", async () => {
    const container = reply("$$\n\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}\n$$");

    await renderMath(container);

    expect(container.querySelector('.sensai-math-display math[display="block"]')).not.toBeNull();
  });

  it("writes MathML alone, with none of the HTML that would need KaTeX's fonts and stylesheet", async () => {
    const container = reply("in a line $\\frac{a}{b}$ and\n\n$$\\sum_{i=1}^{n} x_i$$");

    await renderMath(container);

    expect(container.querySelectorAll("math")).toHaveLength(2);
    // the layer of positioned HTML boxes that KaTeX's default output adds, and the classes its stylesheet styles
    for (const html of [".katex-html", ".katex-mathml", ".katex-display", ".strut", ".vlist", ".base", ".mfrac"]) {
      expect(container.querySelector(html), html).toBeNull();
    }
  });

  it("shows a mistake in the TeX as the source and does not fail", async () => {
    const container = reply("bad $\\frac{1}{$ and good $x$");

    expect(await renderMath(container)).toBe(true);

    const [bad, good] = [...container.querySelectorAll(".sensai-math")];
    expect(bad!.querySelector(".katex-error")).not.toBeNull();
    expect(good!.querySelector(".katex")).not.toBeNull();
  });

  it("does not make a link, an image or a style from the TeX", async () => {
    const container = reply(
      "$\\href{https://evil.test}{click}$ $\\url{https://evil.test}$ $\\includegraphics{https://evil.test/x.png}$ $\\htmlClass{admin}{x}$ $\\htmlStyle{color:red}{x}$",
    );

    expect(await renderMath(container)).toBe(true);

    // each was handled: typeset or, for a refused command, shown as an error
    for (const el of container.querySelectorAll(".sensai-math")) {
      expect(el.querySelector(".katex, .katex-error"), el.textContent ?? "").not.toBeNull();
    }
    // a refused command is shown as its source in red text, which is harmless: what matters is that
    // nothing was made that the browser would follow, load or style
    expect(container.querySelector("a")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("[href]")).toBeNull();
    expect(container.querySelector("[src]")).toBeNull();
    expect(container.querySelector(".admin")).toBeNull();
    expect(container.querySelector('[style*="color:red"]')).toBeNull();
  });

  it("makes no markup from a script written as math", async () => {
    const container = reply("$<script>alert(1)</script>$ and $\\text{<img src=x onerror=alert(1)>}$");

    expect(await renderMath(container)).toBe(true);

    for (const el of container.querySelectorAll(".sensai-math")) {
      expect(el.querySelector(".katex, .katex-error"), el.textContent ?? "").not.toBeNull();
    }
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("is loaded once and shared", () => {
    expect(loadKatex()).toBe(loadKatex());
  });
});

describe("fetchedOnce", () => {
  it("fetches the first time it is asked and not again, giving the same thing", async () => {
    const fetchIt = vi.fn(() => Promise.resolve({ loaded: true }));
    const get = fetchedOnce(fetchIt);

    const [a, b] = await Promise.all([get(), get()]);
    const c = await get();

    expect(fetchIt).toHaveBeenCalledTimes(1);
    expect(b).toBe(a);
    expect(c).toBe(a);
  });

  it("fetches once when asked twice before the first fetch is done", async () => {
    let finish!: (value: string) => void;
    const fetchIt = vi.fn(() => new Promise<string>((resolve) => (finish = resolve)));
    const get = fetchedOnce(fetchIt);

    const first = get();
    const second = get();
    finish("done");

    expect(await first).toBe("done");
    expect(await second).toBe("done");
    expect(fetchIt).toHaveBeenCalledTimes(1);
  });

  it("passes a failure on, and forgets it so the next ask fetches again", async () => {
    const fetchIt = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce("loaded");
    const get = fetchedOnce(fetchIt);

    await expect(get()).rejects.toThrow("offline");
    await expect(get()).resolves.toBe("loaded");

    expect(fetchIt).toHaveBeenCalledTimes(2);
  });

  it("does not fetch again after it has loaded once following a failure", async () => {
    const fetchIt = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue("loaded");
    const get = fetchedOnce(fetchIt);
    await get().catch(() => undefined);

    await get();
    await get();

    expect(fetchIt).toHaveBeenCalledTimes(2);
  });
});
