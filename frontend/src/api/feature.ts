import { http } from './http'
import type { PageResult } from '../types/api'
import type { Feature, FeatureDetail } from '../types/feature'

export async function listFeatures(): Promise<PageResult<Feature>> {
  const { data } = await http.get('/features')
  return data
}

export async function getFeature(id: number): Promise<FeatureDetail> {
  const { data } = await http.get(`/features/${id}`)
  return data
}

export async function updateFeature(id: number, payload: Record<string, unknown>): Promise<Feature> {
  const { data } = await http.patch(`/features/${id}`, payload)
  return data
}

export async function publishFeature(id: number): Promise<Feature> {
  const { data } = await http.post(`/features/${id}/publish`)
  return data
}

export async function getFeatureVersions(id: number): Promise<FeatureDetail> {
  const { data } = await http.get(`/features/${id}/versions`)
  return data
}
