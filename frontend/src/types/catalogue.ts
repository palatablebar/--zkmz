export interface EventRow {
  id: number
  entity_key: string
  event_type: string
  event_ts: string
  amount: number
  channel: string
  source_ref: string
}

export interface EventPage {
  items: EventRow[]
  total: number
  summary: {
    by_type: Record<string, number>
    amount_sum: number
    entity_count: number
  }
}

export interface MetaPayload {
  app: string
  client: string
  roles: { value: string; label: string }[]
  boundary_policies: { value: string; label: string }[]
  aggregates: { value: string; label: string }[]
  event_types: { value: string; label: string }[]
  operation_steps: { code: string; key: string; title: string; hint: string }[]
  margin_notes: Record<string, string>
  default_backfill_range: { start: string; end: string }
  limits: { rate_window_seconds: number; rate_window_max: number; daily_run_quota: number }
}
