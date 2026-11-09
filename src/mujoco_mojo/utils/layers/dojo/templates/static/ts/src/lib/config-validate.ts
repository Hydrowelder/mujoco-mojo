// the plot config's semantic checks: whether the signals it plots actually
// exist, on top of the structural checks the JSON Schema gives

import type { PlotConfig } from "../models";
import { validateAgainstSchema } from "./schema-validate";

// the part of a Signal Lab config's schema these checks read
export interface LabRequirements {
  name: string;
  signal_in_columns: string[];
  missing: string[];
}

export interface PlotConfigContext {
  // the plot config's JSON Schema; null until it has been fetched, which just
  // skips the structural pass
  schema: Record<string, unknown> | null;
  labSchemas: LabRequirements[];
  // every column in the trial's telemetry
  columns: string[];
}

// human-readable problems with `cfg`, empty when it is fine. Lab signals
// ("Lab/<name>/<output>") are checked against the lab's requirements, and only
// once the lab schemas have loaded; each lab is reported at most once
export function validatePlotConfig(cfg: PlotConfig, { schema, labSchemas, columns }: PlotConfigContext): string[] {
  // schema-level checks (types, required fields, enums, discriminated
  // unions, ...) - skipped entirely before the schema has been fetched rather
  // than blocking on it; the semantic checks below still run regardless
  const errors: string[] = schema ? validateAgainstSchema(cfg, schema) : [];
  const labsNoted = new Set<string>();
  const schemasLoaded = labSchemas.length > 0;

  const checkCol = (col: string, label: string) => {
    if (col.startsWith("Lab/")) {
      if (!schemasLoaded) return; // wait for schemas before reporting Lab issues
      // lab names may contain '/' (nested folders); the output label is
      // always the final segment, so split from the right
      const labRest = col.slice(4);
      const labSplitIdx = labRest.lastIndexOf("/");
      const labName = labSplitIdx >= 0 ? labRest.slice(0, labSplitIdx) : labRest;
      if (labsNoted.has(labName)) return;
      const lab = labSchemas.find((l) => l.name === labName);
      if (!lab) {
        labsNoted.add(labName);
        errors.push(`Lab "${labName}" not found.`);
      } else if (lab.missing.length > 0) {
        labsNoted.add(labName);
        errors.push(
          `Lab "${labName}" requires: ${lab.signal_in_columns.join(", ")}; missing: ${lab.missing.join(", ")}.`,
        );
      }
    } else if (!columns.includes(col)) {
      errors.push(`${label} "${col}" not found in telemetry.`);
    }
  };

  if (cfg.xAxis?.col) checkCol(cfg.xAxis.col, "X-Axis");
  if (typeof cfg.yAxes !== "object" || cfg.yAxes === null || Array.isArray(cfg.yAxes)) {
    errors.push("yAxes must be a hashmap.");
  } else {
    Object.keys(cfg.yAxes).forEach((y) => checkCol(y, "Y-Axis"));
  }
  return errors;
}
