export interface Feature {
  id: number
  code: string
  name: string
  description: string
  event_type: string | null
  amount_min: number | null
  window_seconds: number
  window_label: string
  boundary_policy: string
  aggregate_kind: string
  status: string
  version: number
  owner_id: number | null
  published_at: string | null
  updated_at: string | null
  dsl: string
}

export interface FeatureVersion {
  id: number
  version_no: number
  change_note: string
  changed_by: string
  snapshot: Record<string, unknown>
  created_at: string | null
}

export interface FeatureDetail {
  feature: Feature
  versions: FeatureVersion[]
  audits: AuditEntry[]
}

export interface AuditEntry {
  id: number
  actor_email: string
  action: string
  entity_type: string
  entity_id: number | null
  created_at: string | null
  after_json: Record<string, unknown> | null
}
