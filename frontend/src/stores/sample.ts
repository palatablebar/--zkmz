import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  createSampleJob,
  getSampleJob,
  listLabelSets,
  listSampleJobs,
  runSampleJob,
} from '../api/sample'
import type { LabelSet, SampleJob, SampleReport } from '../types/sample'

export const useSampleStore = defineStore('sample', () => {
  const jobs = ref<SampleJob[]>([])
  const labelSets = ref<LabelSet[]>([])
  const report = ref<SampleReport | null>(null)
  const activeJobId = ref<number | null>(null)

  async function loadJobs() {
    const payload = await listSampleJobs()
    jobs.value = payload.items
  }

  async function loadLabelSets() {
    const payload = await listLabelSets()
    labelSets.value = payload.items
  }

  async function create(payload: Record<string, unknown>) {
    const job = await createSampleJob(payload)
    await loadJobs()
    return job
  }

  async function run(id: number) {
    await runSampleJob(id)
    await loadJobs()
  }

  async function loadReport(id: number) {
    const payload = await getSampleJob(id)
    report.value = payload.report
    activeJobId.value = id
    return payload
  }

  async function waitForCompletion(id: number, timeoutMs = 120000): Promise<SampleJob> {
    const started = Date.now()
    while (Date.now() - started < timeoutMs) {
      const payload = await getSampleJob(id)
      if (payload.job.status === 'completed' || payload.job.status === 'failed') {
        report.value = payload.report
        await loadJobs()
        return payload.job
      }
      await new Promise((resolve) => setTimeout(resolve, 1200))
    }
    throw new Error('样本任务等待超时')
  }

  return { jobs, labelSets, report, activeJobId, loadJobs, loadLabelSets, create, run, loadReport, waitForCompletion }
})
