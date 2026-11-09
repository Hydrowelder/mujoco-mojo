// the data extent behind a plot's autoscaled axis range

type Dataset = Record<string, number[]>;

// the versus-mode datasets that count toward the range: those whose trial
// number (the digits after the last "_" in the id) is inside [start, end], or
// pinned
export function selectVsDatasets(
  vsDatasets: Record<string, Dataset>,
  range: [number, number],
  pinned: number[],
): Dataset[] {
  const [start, end] = range;
  const pinnedSet = new Set(pinned);
  const selected: Dataset[] = [];
  Object.entries(vsDatasets).forEach(([vsId, dataset]) => {
    const n = parseInt(vsId.split("_").pop() ?? "");
    if ((n >= start && n <= end) || pinnedSet.has(n)) selected.push(dataset);
  });
  return selected;
}

// [min, max] over every named series in every dataset, widened by a sixteenth
// of the span on each side (unless `padding` is off). no data gives [0, 1] and
// a flat line gives one unit either side, so an axis never collapses
export function paddedRange(datasets: Dataset[], keys: string[], padding = true): [number, number] {
  let globalMin = Infinity;
  let globalMax = -Infinity;

  datasets.forEach((dataset) => {
    keys.forEach((key) => {
      const series = dataset[key];
      if (!series) return;
      for (let j = 0; j < series.length; j++) {
        const val = series[j] ?? 0;
        if (val < globalMin) globalMin = val;
        if (val > globalMax) globalMax = val;
      }
    });
  });

  if (globalMin === Infinity) return [0, 1];
  if (globalMin === globalMax) return [globalMin - 1, globalMax + 1];
  const pad = padding ? (globalMax - globalMin) / 16 : 0;
  return [globalMin - pad, globalMax + pad];
}
