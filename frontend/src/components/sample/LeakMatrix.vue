<template>
  <section class="card">
    <div class="card-title">
      <h2>泄漏矩阵</h2>
      <span class="op-index">
        {{ matrix?.shown_samples ?? 0 }} / {{ matrix?.total_samples ?? 0 }} 样本 ×
        {{ features.length }} 特征
      </span>
    </div>

    <p v-if="!matrix || samples.length === 0" class="muted small">
      尚无矩阵数据：先运行样本任务，矩阵会按「泄漏优先」排序展示前 24 个样本。
    </p>

    <template v-else>
      <div class="matrix" :style="{ gridTemplateColumns: `170px repeat(${features.length}, minmax(0, 1fr))` }">
        <div class="matrix-head" style="display: contents">
          <div>样本键 / 标签时间</div>
          <div v-for="feature in features" :key="feature.code">
            {{ feature.code }}<br />
            <span class="muted">{{ feature.window_label }} · {{ feature.boundary }}</span>
          </div>
        </div>
        <div
          v-for="(row, rowIndex) in samples"
          :key="row.label_row_id"
          class="matrix-row"
          style="display: contents"
        >
          <div class="row-label">
            <span>{{ row.entity_key }}</span>
            <span class="muted">{{ fmtShortTime(row.label_time) }} · y={{ row.label }}</span>
          </div>
          <div
            v-for="(feature, colIndex) in features"
            :key="feature.code"
            class="cell"
            :class="cellTone(row.cells[feature.code])"
            :style="{ '--i': rowIndex * features.length + colIndex }"
            :title="`${feature.code} = ${row.cells[feature.code]?.value}`"
          >
            <span>{{ row.cells[feature.code]?.value }}</span>
            <span v-if="row.cells[feature.code]?.leak" style="font-size: 0.6rem">越界 {{ row.cells[feature.code]?.overflow_ms }}ms</span>
            <span v-else class="muted" style="font-size: 0.6rem">n={{ row.cells[feature.code]?.matched_events ?? 0 }}</span>
          </div>
        </div>
      </div>

      <div class="legend">
        <span v-for="item in legend" :key="item.tone">
          <i :class="item.tone"></i>{{ item.label }}
        </span>
      </div>
      <p class="small muted" style="margin-top: 10px">
        点亮格数（泄漏格）：<strong class="mono">{{ litCount }}</strong>；
        矩阵按泄漏优先排序并截断，完整泄漏明细见下方清单。
      </p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { useLeakMatrix } from '../../hooks/useLeakMatrix'
import type { LeakMatrixData } from '../../types/sample'
import { fmtShortTime } from '../../utils/format'

const props = defineProps<{ matrix: LeakMatrixData | null }>()
const { features, samples, legend, litCount, cellTone } = useLeakMatrix(() => props.matrix)
</script>
