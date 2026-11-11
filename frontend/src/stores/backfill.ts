import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createBackfill, getBackfill, listBackfills, runBackfill } from '../api/backfill'
import type { BackfillTask } from '../types/backfill'

export const useBackfillStore = defineStore('backfill', () => {
  const tasks = ref<BackfillTask[]>([])
  const active = ref<BackfillTask | null>(null)

  async function load() {
    const payload = await listBackfills()
    tasks.value = payload.items
    if (!active.value && tasks.value.length > 0) {
      await select(tasks.value[0].id)
    }
  }

  async function select(id: number) {
    active.value = await getBackfill(id)
  }

  async function create(payload: Record<string, unknown>) {
    const task = await createBackfill(payload)
    await load()
    await select(task.id)
    return task
  }

  async function run(id: number) {
    await runBackfill(id)
    await load()
    await waitFor(id)
  }

  async function waitFor(id: number, timeoutMs = 120000): Promise<BackfillTask> {
    const started = Date.now()
    while (Date.now() - started < timeoutMs) {
      const task = await getBackfill(id)
      active.value = task
      if (task.status === 'completed' || task.status === 'failed') {
        await load()
        return task
      }
      await new Promise((resolve) => setTimeout(resolve, 1200))
    }
    throw new Error('回填任务等待超时')
  }

  return { tasks, active, load, select, create, run, waitFor }
})
