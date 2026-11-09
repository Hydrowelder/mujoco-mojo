// typesets the math in a reply. markdown.ts leaves each piece as a placeholder
// carrying its TeX; this turns them into math with KaTeX, asked for MathML only: the
// browser draws that with the math fonts it already has, so no KaTeX fonts or
// stylesheet are shipped (they were three quarters of what KaTeX added to the
// package). KaTeX is about 74 KB gzipped and most replies have no math, so it is
// fetched the first time a placeholder is shown and not with the page

import type { KatexOptions } from "katex";

// the part of KaTeX that is used, so a test can give a stand-in
export interface Katex {
  render(tex: string, element: HTMLElement, options?: KatexOptions): void;
}

// a reply is text a model wrote from data a user or a trial controls, so what
// KaTeX is allowed to do is kept narrow: no links, images or styling by name
// (trust off), a mistake shows as the source in red and not as a failure
// (throwOnError off), and a construct KaTeX only warns about is let go quietly. the
// output is MathML alone: KaTeX's default also writes an HTML layer, which is what
// needs its fonts and its stylesheet
export const KATEX_OPTIONS: KatexOptions = {
  throwOnError: false,
  trust: false,
  strict: "ignore",
  output: "mathml",
};

// a function that fetches something the first time it is asked and gives the same
// thing after, but forgets a failure, so a fetch that failed (the page was offline)
// is tried again the next time
export function fetchedOnce<T>(fetchIt: () => Promise<T>): () => Promise<T> {
  let loading: Promise<T> | null = null;
  return () =>
    (loading ??= fetchIt().catch((error: unknown) => {
      loading = null;
      throw error;
    }));
}

// KaTeX, with no stylesheet: MathML needs none
export const loadKatex = fetchedOnce<Katex>(async () => (await import("katex")).default);

// typesets each placeholder in `container` that has not been done, and says
// whether it did any (so what is shown can be measured again, since math is
// taller than its source). each is marked at once, so two calls close together
// do not both do it, and the mark is taken off if KaTeX could not be loaded, which
// leaves the source showing and lets a later call try again
export async function renderMath(
  container: HTMLElement,
  load: () => Promise<Katex> = loadKatex,
): Promise<boolean> {
  const placeholders = [...container.querySelectorAll<HTMLElement>(".sensai-math:not([data-math-init])")];
  if (placeholders.length === 0) return false;
  for (const el of placeholders) el.setAttribute("data-math-init", "1");
  try {
    const katex = await load();
    for (const el of placeholders) {
      katex.render(decodeURIComponent(el.dataset["tex"] ?? ""), el, {
        ...KATEX_OPTIONS,
        displayMode: el.dataset["display"] === "true",
      });
    }
    return true;
  } catch {
    for (const el of placeholders) el.removeAttribute("data-math-init");
    return false;
  }
}
