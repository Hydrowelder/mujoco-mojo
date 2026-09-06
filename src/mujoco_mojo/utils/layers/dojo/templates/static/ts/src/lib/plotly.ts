// custom trimmed Plotly build: only the trace types Dojo actually charts
// (bar, scatter, scatterpolar), per Plotly's own documented "lib/core"
// pattern -- pulls in only what's imported here instead of the full
// 37-trace-type package or the strict-dist bundle.
import RealPlotly from "plotly.js/lib/core";
import bar from "plotly.js/lib/bar";
import scatter from "plotly.js/lib/scatter";
import scatterpolar from "plotly.js/lib/scatterpolar";

RealPlotly.register([bar, scatter, scatterpolar]);

// monitor.ts/trial-viewer.ts build trace/layout objects loosely (plain
// object literals, not plotly.js's strict Data[]/Partial<Layout> types --
// that's how they were already written against the old hand-rolled ambient
// `declare const Plotly: {...}` type, and retyping every chart call site to
// satisfy plotly.js's full strict types is a separate, much larger project
// than this migration). This cast preserves that exact same loose surface
// so existing call sites keep type-checking unchanged, backed by the real
// import instead of an ambient declaration.
interface LoosePlotly {
  react(
    el: string | HTMLElement,
    data: object[],
    layout: object,
    config?: object,
  ): Promise<void>;
  newPlot(
    el: string | HTMLElement,
    data: object[],
    layout: object,
    config?: object,
  ): Promise<void>;
  purge(el: string | HTMLElement): void;
  relayout(el: string | HTMLElement, update: object): Promise<void>;
  toImage(el: string | HTMLElement, opts: object): Promise<string>;
  Plots: { resize(el: HTMLElement): void };
}

const Plotly = RealPlotly as unknown as LoosePlotly;
export default Plotly;
