<template>
  <div class="card" style="margin-top: 0">
    <div class="card-title"><h2>配额</h2><span class="op-index">quota</span></div>
    <div class="mono small">
      <div>{{ quota?.quota_used ?? 0 }} / {{ quota?.daily_quota ?? 0 }} 今日构建次数</div>
      <div class="muted" style="margin-top: 6px">
        限流 {{ quota?.rate_window_max ?? 0 }} 次 / {{ quota?.rate_window_seconds ?? 60 }} 秒
      </div>
    </div>
    <div
      style="height: 6px; border: 1px solid var(--ink-line-strong); margin-top: 8px; background: var(--paper)"
    >
      <div
        :style="{
          width: ratio + '%',
          height: '100%',
          background: ratio > 80 ? 'var(--annot)' : 'var(--ink)',
        }"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Quota } from '../../types/api'

const props = defineProps<{ quota: Quota | null }>()
const ratio = computed(() => {
  const q = props.quota
  if (!q || !q.daily_quota) return 0
  return Math.min(100, Math.round((q.quota_used / q.daily_quota) * 100))
})
</script>
