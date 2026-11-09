// plot-profile logic for the trial viewer, moved out of trial-viewer.ts so it
// can be tested without an Alpine component: the URL, the save request and
// its overwrite check, the payload a save sends, the tabs a load builds, and
// the two "columns this trial does not have" checks (the profile list's
// warning badges and the notice shown after loading).

import { encodeNamePath } from "./name-path";
import type { PlotProfile } from "./plot-profile";
import { refFrameActive, refFrameAvailable, refFrameLabel } from "./ref-frame";
import { newTabId } from "./tab-session";
import { versusState } from "./vs-sync";
import type { PlotTab } from "./plot-tabs";

export function profileUrl(name: string): string {
  return `/mosaic/api/profiles/${encodeNamePath(name)}`;
}

export type SaveProfileResult = { saved: true; name: string } | { saved: false };

// saves the profile under `name`, asking `confirmOverwrite` (with the name it
// is stored under) before replacing one that is already there. the server
// decides whether it is the same profile, since it is the one that turns a
// typed name into a file name (case, punctuation, spaces and slashes all
// count there), so the question is asked exactly when a save would replace
// something. false when the answer was no; throws when the save failed
export async function saveProfileRequest(
  name: string,
  payload: PlotProfile,
  confirmOverwrite: (existingName: string) => Promise<boolean>,
): Promise<SaveProfileResult> {
  const post = (query: string) =>
    fetch(profileUrl(name) + query, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  let resp = await post("?overwrite=false");
  if (resp.status === 409) {
    const body = (await resp.json().catch(() => ({}))) as { detail?: { name?: string } };
    if (!(await confirmOverwrite(body.detail?.name ?? name))) return { saved: false };
    resp = await post("");
  }
  if (!resp.ok) throw new Error("Save failed");
  const result = (await resp.json()) as { name: string };
  return { saved: true, name: result.name };
}

// a profile saves every open tab, not just the active one
export function buildProfilePayload(
  tabs: PlotTab[],
  activeTabId: string | null,
  vs: { enabled: boolean; range: [number, number]; pinned: number[] },
): PlotProfile {
  const activeTabIndex = Math.max(
    0,
    tabs.findIndex((t) => t.id === activeTabId),
  );
  return {
    version: 2,
    tabs: tabs.map((t) => ({ config: t.config })),
    activeTabIndex,
    // VS is workspace-level - saved once for the whole profile, not per tab
    ...versusState(vs),
  };
}

// a profile is a saved workspace - loading one replaces every open tab, it
// doesn't patch the currently active one
export function tabsFromProfile(profile: PlotProfile): PlotTab[] {
  return profile.tabs.map((t) => ({
    id: newTabId(),
    config: t.config,
    data: null,
    filterFingerprints: {},
    xAxisFilterFingerprint: "[]",
    historyStack: [],
    historyIndex: -1,
    savedSnapshot: JSON.stringify(t.config),
  }));
}

export function profileActiveIndex(profile: PlotProfile, tabCount: number): number {
  return Math.min(Math.max(profile.activeTabIndex ?? 0, 0), tabCount - 1);
}

// the trial's column names, plus the reference frames it can offer (every
// quaternion's `:w` family)
function columnContext(columns: string[]): { colSet: Set<string>; frames: Set<string> } {
  const colSet = new Set(columns);
  const frames = new Set(
    columns.filter((c) => c.endsWith(":w")).map((c) => c.replace(":w", "")),
  );
  return { colSet, frames };
}

// what the profile list's warning badge says: the signals, x-axes and frames a
// saved profile uses that this trial does not have. Every column is checked,
// Signal Lab outputs included.
export function profileWarnings(profile: Partial<PlotProfile>, columns: string[]): string[] {
  const { colSet, frames } = columnContext(columns);
  const w: string[] = [];
  (profile.tabs ?? []).forEach((t, idx) => {
    const cfg = t.config;
    const label = cfg.title || `tab ${idx + 1}`;
    if (cfg.xAxis?.col && !colSet.has(cfg.xAxis.col))
      w.push(`${label}: x-axis "${cfg.xAxis.col}"`);
    for (const key of Object.keys(cfg.yAxes ?? {})) {
      if (!colSet.has(key)) w.push(`${label}: "${key}"`);
    }
    if (refFrameActive(cfg.refFrame) && !refFrameAvailable(cfg.refFrame, frames, colSet))
      w.push(`${label}: frame "${refFrameLabel(cfg.refFrame)}"`);
  });
  return w;
}

// what loading a profile reports as "won't plot until added to this trial".
// Columns not present in this trial are tolerated: the profile still loads
// (so it can be used as a starting point), but those signals won't plot until
// matching columns exist. Signal Lab outputs (`Lab/<name>/<output>`) are
// skipped; validatePlotConfig checks those against the lab's own requirements.
export function profileMissing(profile: PlotProfile, columns: string[]): string[] {
  const { colSet, frames } = columnContext(columns);
  const missing: string[] = [];
  profile.tabs.forEach((t, idx) => {
    const cfg = t.config;
    const label = cfg.title || `tab ${idx + 1}`;
    if (
      cfg.xAxis?.col &&
      !cfg.xAxis.col.startsWith("Lab/") &&
      !colSet.has(cfg.xAxis.col)
    )
      missing.push(`${label}: x-axis "${cfg.xAxis.col}"`);
    for (const key of Object.keys(cfg.yAxes ?? {})) {
      if (!key.startsWith("Lab/") && !colSet.has(key))
        missing.push(`${label}: signal "${key}"`);
    }
    if (refFrameActive(cfg.refFrame) && !refFrameAvailable(cfg.refFrame, frames, colSet))
      missing.push(`${label}: frame "${refFrameLabel(cfg.refFrame)}"`);
  });
  return missing;
}
