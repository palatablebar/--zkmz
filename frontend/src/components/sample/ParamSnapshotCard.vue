<template>
  <section class="card">
    <div class="card-title">
      <h2>参数快照</h2>
      <span class="op-index">{{ snapshot?.engine ?? 'pit_engine' }}</span>
    </div>
    <table>
      <tbody>
        <tr>
          <td style="width: 128px" class="muted">标签集</td>
          <td>{{ (snapshot?.label_set_codes ?? []).join(' / ') || '—' }}</td>
        </tr>
        <tr>
          <td class="muted">时间范围</td>
          <td>{{ fmtTime(String(snapshot?.range_start ?? '')) }} → {{ fmtTime(String(snapshot?.range_end ?? '')) }}</td>
        </tr>
        <tr>
          <td class="muted">边界策略</td>
          <td>{{ job?.boundary_policy ?? '—' }}</td>
        </tr>
        <tr>
          <td class="muted">特征口径</td>
          <td>
            <div v-for="item in snapshot?.features ?? []" :key="item.code">
              <span class="inline-code">{{ item.code }}</span>
              {{ item.window_label }} · {{ item.boundary_policy }} · {{ item.aggregate_kind }}
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FeatureSnapshot, SampleJob } from '../../types/sample'
import { fmtTime } from '../../utils/format'

const props = defineProps<{ job: SampleJob | null }>()
const snapshot = computed(
  () =>
    (props.job?.params_snapshot ?? {}) as {
      engine?: string
      label_set_codes?: string[]
      range_start?: string
      range_end?: string
      features?: FeatureSnapshot[]
    },
)
</script>
