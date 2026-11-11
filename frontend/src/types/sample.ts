import type { AuditEntry } from './feature'

export interface LeakCell {
  value: number
  leak: boolean
  overflow_ms: number | null
  matched_events: number
}

export interface MatrixSample {
  label_row_id: number
  entity_key: string
  label_time: string
  label: number
  cells: Record<string, LeakCell>
}

export interface LeakMatrixData {
  features: { code: string; name: string; window_label: string; boundary: string }[]
  samples: MatrixSample[]
  total_samples: number
  shown_samples: number
  truncated?: boolean
}

export interface LeakItem {
  feature_code: string
  feature_name: string
  declared_boundary: string
  kind: string
  overflow_ms: number
  event_id: number
  event_type: string
  event_ts: string
  label_time: string
  label_row_id: number
  label_set_id: number
  entity_key: string
  label: number
}

export interface LeakSummary {
  leak_count: number
  leak_samples: number
  leak_features: number
  by_feature: { feature_code: string; count: number; max_overflow_ms: number; policy: string }[]
  max_overflow_ms: number
  boundary_policies: string[]
}

export interface BoundaryProbe {
  case: string
  offset_ms: number
  event_ts: string
  included_strict: boolean
  included_inclusive: boolean
  verdict: string
  leak_under_inclusive: boolean
}

export interface SampleJob {
  id: number
  code: string
  name: string
  status: string
  label_set_ids: number[]
  feature_ids: number[]
  range_start: string | null
  range_end: string | null
  boundary_policy: string
  sample_count: number
  leak_count: number
  failure_reason: string | null
  created_by: string
  started_at: string | null
  finished_at: string | null
  created_at: string | null
  params_snapshot: Record<string, unknown> & { features?: FeatureSnapshot[] }
  leak_summary: LeakSummary | null
  leak_free: boolean | null
}

export interface FeatureSnapshot {
  code: string
  name: string
  window_label: string
  window_seconds: number
  boundary_policy: string
  aggregate_kind: string
  event_type: string | null
  amount_min: number | null
}

export interface SampleRow {
  id: number
  label_row_id: number
  label_set_id: number
  entity_key: string
  label_time: string
  label: number
  features: Record<string, number>
  leak_flags: LeakItem[]
  has_leak: boolean
  no_event: boolean
}

export interface SampleReport {
  job: SampleJob
  leak_summary: LeakSummary
  leaks: LeakItem[]
  matrix: LeakMatrixData
  boundary_probes: BoundaryProbe[]
  run_snapshot: Record<string, unknown>
  failure: { reason: string; message: string; detail?: Record<string, unknown> } | null
  sample_preview: SampleRow[]
  sample_total: number
}

export interface LabelSet {
  id: number
  code: string
  name: string
  description: string
  sample_count: number
  entity_count: number
  label_positive: number
  first_label_time: string | null
  last_label_time: string | null
}

export type { AuditEntry }
