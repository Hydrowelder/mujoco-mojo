// Hand-written mirror of dojo/plot_config.py's PlotProfile/PlotProfileTab.
// Not generated: scripts/gen_ts_models.py is hardcoded around a single
// top-level model (PlotConfig itself), and this wrapper shape is small and
// stable enough that hand-writing it once keeps plot-config.generated.ts
// and its regen workflow untouched by the profile format.

import type { PlotConfig } from "./plot-config.generated";

export interface PlotProfileTab {
  config: PlotConfig;
}

export interface PlotProfile {
  version: 2;
  tabs: PlotProfileTab[];
  activeTabIndex: number;
}
