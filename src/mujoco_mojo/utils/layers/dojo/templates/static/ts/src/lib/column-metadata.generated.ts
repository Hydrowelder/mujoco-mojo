// ============================================================
// AUTO-GENERATED - do not edit manually.
// Source: src/mujoco_mojo/utils/signal_metadata.py (ColumnMetadata)
// Regenerate: python scripts/gen_ts_models.py
// ============================================================

export type TransformType = "point" | "vector" | "quaternion" | "scalar";
export const TRANSFORM_TYPE_VALUES: TransformType[] = ["point", "vector", "quaternion", "scalar"];

export interface ColumnMetadata {
  unit?: string | null;
  dimension?: string | null;
  quantity?: string | null;
  transform_type?: TransformType | null;
  [key: string]: unknown;
}
