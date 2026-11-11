import { http } from './http'
import type { PageResult } from '../types/api'
import type { LabelSet, SampleJob, SampleReport, SampleRow } from '../types/sample'

export async function listLabelSets(): Promise<PageResult<LabelSet>> {
  const { data } = await http.get('/label-sets')
  return data
}

export async function listSampleJobs(): Promise<PageResult<SampleJob>> {
  const { data } = await http.get('/sample-jobs')
  return data
}

export async function createSampleJob(payload: Record<string, unknown>): Promise<SampleJob> {
  const { data } = await http.post('/sample-jobs', payload)
  return data
}

export async function runSampleJob(id: number): Promise<Record<string, unknown>> {
  const { data } = await http.post(`/sample-jobs/${id}/run`)
  return data
}

export async function getSampleJob(id: number): Promise<{ job: SampleJob; report: SampleReport }> {
  const { data } = await http.get(`/sample-jobs/${id}`)
  return data
}

export async function getSampleReport(id: number): Promise<SampleReport> {
  const { data } = await http.get(`/sample-jobs/${id}/report`)
  return data
}

export async function getSampleRows(id: number, limit = 20): Promise<PageResult<SampleRow>> {
  const { data } = await http.get(`/sample-jobs/${id}/samples`, { params: { limit } })
  return data
}
