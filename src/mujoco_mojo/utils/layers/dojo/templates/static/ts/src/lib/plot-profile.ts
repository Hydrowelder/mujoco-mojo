// Hand-written mirror of dojo/plot_config.py's PlotProfile/PlotProfileTab.
// Not generated: scripts/gen_ts_models.py is hardcoded around a single
// top-level model (PlotConfig itself), and this wrapper shape is small and
// stable enough that hand-writing it once keeps plot-config.generated.ts
// and its regen workflow untouched by the profile format.

import type { PlotConfig } from "./plot-config.generated";

export interface PlotProfileTab {
  config: PlotConfig;
}

// versus mode's settings (the comparison-trial overlay), shared across every
// tab, not nested in any one tab's PlotConfig. a saved profile carries them and
// so does SensAI's view of the trial viewer; SensAI can set no range (null),
// which leaves only the pinned trials
export interface VersusState {
  vsEnabled: boolean;
  vsRange: [number, number] | null;
  vsPinned: number[];
}

export interface PlotProfile extends Omit<VersusState, "vsRange"> {
  version: 2;
  tabs: PlotProfileTab[];
  activeTabIndex: number;
  vsRange: [number, number];
}
