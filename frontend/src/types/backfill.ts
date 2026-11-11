export interface LedgerImpactItem {
  seq: number
  batch_id: string
  delivery_id: string
  action: string
  outcome: 'accepted' | 'replaced' | 'retracted' | 'duplicate_delivery' | 'retract_missing'
  entity_key: string
  event_type: string
  event_ts: string
  amount_before: number | null
  amount_after: number | null
  in_baseline: boolean
  affected_sample_count: number
  affected_samples: { label_row_id: number; window: string; label_time: string }[]
}

export interface ReconciliationIssue {
  seq: number
  reason: 'duplicate_delivery' | 'retract_missing' | 'baseline_rewritten'
  detail: Record<string, unknown>
}

export interface DifferenceEntry {
  index: number
  label_row_id: number
  entity_key?: string
  label_time?: string
  reason: string
  differing_windows: string[]
  full?: Record<string, unknown>
  incremental?: Record<string, unknown>
  detail?: string
}

export interface ChecksumReport {
  windows: string[]
  sample_count: number
  cell_count: number
  baseline_cutoff_seq: number | null
  current_cutoff_seq: number | null
  range_start: string | null
  range_end: string | null
  scoped_event_count: number
  base_event_count: number
  new_event_count: number
  late_event_count: number
  duplicate_event_count: number
  reconciliation: {
    aligned: boolean
    issue_count: number
    issues: ReconciliationIssue[]
  }
  aligned: boolean
  full: { checksum: string; digest_count: number }
  incremental: { checksum: string; digest_count: number }
  equal: boolean
  invariant: string
  invariant_hold: boolean
  diff_sample_count: number
  first_diff: Record<string, unknown> | null
  reason_classes: Record<string, number>
  differences: DifferenceEntry[]
  impact_summary: Record<string, number>
  ledger_impact: LedgerImpactItem[]
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
  baseline?: {
    cutoff_seq: number | null
    event_count: number
    first_run: boolean
  }
  last_reconciliation?: {
    at: string
    reason: string
    message: string
    issue_count: number
    issues: ReconciliationIssue[]
    impact_summary: Record<string, number>
    ledger_impact: LedgerImpactItem[]
    baseline_cutoff_seq: number | null
    current_cutoff_seq: number | null
  }
  last_failure?: {
    reason: string
    message: string
    detail?: Record<string, unknown>
    at: string
  }
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
  baseline_cutoff_seq: number | null
  baseline_event_count: number | null
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
