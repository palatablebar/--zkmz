import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getFeatureVersions, listFeatures, publishFeature, updateFeature } from '../api/feature'
import type { Feature, FeatureVersion } from '../types/feature'
import type { AuditEntry } from '../types/feature'

export const useFeatureStore = defineStore('feature', () => {
  const items = ref<Feature[]>([])
  const selectedId = ref<number | null>(null)
  const versions = ref<FeatureVersion[]>([])
  const audits = ref<AuditEntry[]>([])

  const selected = computed(() => items.value.find((item) => item.id === selectedId.value) ?? null)
  const inclusiveCount = computed(
    () => items.value.filter((item) => item.boundary_policy === 'inclusive').length,
  )

  async function load() {
    const payload = await listFeatures()
    items.value = payload.items
    if (selectedId.value === null && items.value.length > 0) {
      selectedId.value = items.value[0].id
    }
  }

  async function loadDetail(id: number) {
    const payload = await getFeatureVersions(id)
    versions.value = payload.versions
    audits.value = payload.audits
  }

  async function save(id: number, payload: Record<string, unknown>) {
    const updated = await updateFeature(id, payload)
    items.value = items.value.map((item) => (item.id === updated.id ? updated : item))
    return updated
  }

  async function publish(id: number) {
    const updated = await publishFeature(id)
    items.value = items.value.map((item) => (item.id === updated.id ? updated : item))
    return updated
  }

  function select(id: number) {
    selectedId.value = id
  }

  return { items, selectedId, selected, versions, audits, inclusiveCount, load, loadDetail, save, publish, select }
})
