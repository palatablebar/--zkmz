<template>
  <section class="card">
    <div class="card-title">
      <h2>full vs incremental</h2>
      <span class="op-index">md5 · 逐样本 JSON</span>
    </div>

    <div class="kpi-row" style="grid-template-columns: repeat(3, minmax(0, 1fr))">
      <div class="kpi">
        <div class="k">差异样本</div>
        <div class="v" :class="report?.diff_sample_count ? 'is-annot' : 'is-ok'">
          {{ report?.diff_sample_count ?? '—' }}
        </div>
      </div>
      <div class="kpi">
        <div class="k">比对样本</div>
        <div class="v">{{ report?.sample_count ?? '—' }}</div>
      </div>
      <div class="kpi">
        <div class="k">不变量</div>
        <div class="v" :class="report?.invariant_hold ? 'is-ok' : 'is-annot'">
          {{ report?.invariant_hold ? '成立' : '不成立' }}
        </div>
      </div>
    </div>

    <table>
      <tbody>
        <tr>
          <td style="width: 150px" class="muted">全量重算 checksum</td>
          <td class="mono">{{ report?.full.checksum ?? '—' }}</td>
        </tr>
        <tr>
          <td class="muted">增量重算 checksum</td>
          <td class="mono">{{ report?.incremental.checksum ?? '—' }}</td>
        </tr>
        <tr>
          <td class="muted">相等</td>
          <td>
            <span class="tag" :class="report?.equal ? 'tag-ok' : 'tag-annot'">
              {{ report?.equal ? 'EQUAL' : 'DIFF' }}
            </span>
          </td>
        </tr>
        <tr>
          <td class="muted">基准水位</td>
          <td class="mono">{{ fmtTime(report?.base_watermark) }}</td>
        </tr>
        <tr>
          <td class="muted">事件（基准 / 新增）</td>
          <td class="mono">{{ report?.base_event_count ?? '—' }} / {{ report?.new_event_count ?? '—' }}</td>
        </tr>
        <tr>
          <td class="muted">迟到 / 重复事件</td>
          <td class="mono">{{ report?.late_event_count ?? 0 }} / {{ report?.duplicate_event_count ?? 0 }}</td>
        </tr>
        <tr>
          <td class="muted">首个差异位置</td>
          <td class="mono">
            {{ report?.first_diff ? JSON.stringify(report?.first_diff).slice(0, 160) : '无（逐样本一致）' }}
          </td>
        </tr>
        <tr>
          <td class="muted">负例对照（人为放宽右端 60s）</td>
          <td class="mono">
            差异 {{ report?.self_check.diff_sample_count ?? '—' }} 个样本 ·
            原因 {{ Object.keys(report?.self_check.reason_classes ?? {}).join('/') || '—' }}
            <span class="tag" :class="report?.self_check.sensitivity_ok ? 'tag-ok' : 'tag-annot'">
              {{ report?.self_check.sensitivity_ok ? '比对器有效' : '比对器空转' }}
            </span>
          </td>
        </tr>
        <tr>
          <td class="muted">耗时</td>
          <td class="mono">{{ report?.duration_ms ?? '—' }} ms</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import type { ChecksumReport } from '../../types/backfill'
import { fmtTime } from '../../utils/format'

defineProps<{ report: ChecksumReport | null }>()
</script>
