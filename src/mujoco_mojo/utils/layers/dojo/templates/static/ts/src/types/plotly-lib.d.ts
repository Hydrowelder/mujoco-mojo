// plotly.js only ships a `.d.ts` for its main entry point (`plotly.js/lib/index.d.ts`,
// exposed as the package's `types` field); the `lib/core` + individual
// trace-type submodules used for a trimmed custom bundle (see lib/plotly.ts)
// have no types of their own. `lib/core`'s runtime shape (react/newPlot/
// register/etc.) is the same Plotly object the main entry re-exports, just
// without any trace types pre-registered, so its type is the same.
declare module "plotly.js/lib/core" {
  import Plotly from "plotly.js";
  export default Plotly;
}

declare module "plotly.js/lib/bar" {
  import type { PlotlyModule } from "plotly.js";
  const trace: PlotlyModule;
  export default trace;
}

declare module "plotly.js/lib/scatter" {
  import type { PlotlyModule } from "plotly.js";
  const trace: PlotlyModule;
  export default trace;
}

declare module "plotly.js/lib/scatterpolar" {
  import type { PlotlyModule } from "plotly.js";
  const trace: PlotlyModule;
  export default trace;
}
