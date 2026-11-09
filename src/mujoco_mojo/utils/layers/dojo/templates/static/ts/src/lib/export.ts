// what the trial viewer's exports write, moved out of trial-viewer.ts so it
// can be tested without a browser: image sizes and file names, and the
// filtered csv.

// plotly calls a jpg a jpeg
export function plotImageFormat(format: string): string {
  return format === "jpg" ? "jpeg" : format;
}

// an image export is 1280x720 times the scale, rounded
export function plotExportSize(scale: number): { width: number; height: number } {
  return { width: Math.round(1280 * scale), height: Math.round(720 * scale) };
}

export function plotExportFileName(trialId: string, width: number, format: string): string {
  return `${trialId}_${width}p.${format}`;
}

export function csvFileName(trialId: string): string {
  return `${trialId}_filtered.csv`;
}

export function configFileName(trialId: string): string {
  return `${trialId}_config.json`;
}

export function manifestFileName(trialId: string): string {
  return `${trialId}_column_manifest.json`;
}

// the filtered data as csv: a header of the column names, then one row per
// point of the x column, with a blank where a column has no value
export function csvText(
  data: Record<string, number[]>,
  xCol: string,
  yCols: string[],
): string {
  const activeCols = [xCol, ...yCols];
  const rowCount = data[xCol]?.length ?? 0;
  let csv = activeCols.join(",") + "\n";
  for (let i = 0; i < rowCount; i++) {
    csv += activeCols.map((col) => data[col]?.[i] ?? "").join(",") + "\n";
  }
  return csv;
}
