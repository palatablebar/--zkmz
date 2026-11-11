import { http } from './http'
import type { PageResult } from '../types/api'
import type { EventPage, MetaPayload } from '../types/catalogue'
import type { AuditEntry } from '../types/feature'

export async function listEvents(params: { limit?: number; offset?: number; event_type?: string } = {}): Promise<EventPage> {
  const { data } = await http.get('/events', { params })
  return data
}

export async function listAudits(limit = 30, featureId?: number): Promise<PageResult<AuditEntry>> {
  const { data } = await http.get('/audit-logs', { params: { limit, feature_id: featureId } })
  return data
}

export async function fetchMeta(): Promise<MetaPayload> {
  const { data } = await http.get('/meta')
  return data
}
