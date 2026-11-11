export interface ChecksumReport {
  windows: string[]
  sample_count: number
  cell_count: number
  base_watermark: string | null
  range_start: string | null
  range_end: string | null
  scoped_event_count: number
  base_event_count: number
  new_event_count: number
  late_event_count: number
  duplicate_event_count: number
  full: { checksum: string; digest_count: number }
  incremental: { checksum: string; digest_count: number }
  equal: boolean
  invariant: string
  invariant_hold: boolean
  diff_sample_count: number
  first_diff: Record<string, unknown> | null
  reason_classes: Record<string, number>
  differences: Record<string, unknown>[]
  self_check: {
    induced_boundary: string
    diff_sample_count: number
    first_diff: Record<string, unknown> | null
    reason_classes: Record<string, number>
    sensitivity_ok: boolean
  }
  duration_ms: number
  mode?: string
  engine?: string
}

export interface BackfillTask {
  id: number
  code: string
  name: string
  mode: string
  status: string
  range_start: string | null
  range_end: string | null
  base_watermark: string | null
  feature_ids: number[]
  full_checksum: string | null
  incremental_checksum: string | null
  invariant_hold: boolean | null
  created_by: string
  started_at: string | null
  finished_at: string | null
  created_at: string | null
  report: ChecksumReport | null
}
