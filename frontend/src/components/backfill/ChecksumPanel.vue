<template>
  <section class="card">
    <div class="card-title">
      <h2>full vs incremental</h2>
      <span class="op-index">md5 · 逐样本 JSON · 台账水位</span>
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
        <div class="k">批次对平 / 不变量</div>
        <div class="v" :class="report?.invariant_hold ? 'is-ok' : 'is-annot'">
          {{ report ? (report.aligned ? '对平' : '未对平') : '—' }}
          / {{ report?.invariant_hold ? '成立' : '不成立' }}
        </div>
      </div>
    </div>

    <div v-if="report && !report.aligned" class="notice" style="margin: var(--space-3) 0">
      <strong>新批次未对平，已保留上一次回填结果</strong>
      <span class="small" style="display: block; margin-top: 4px">
        共 {{ report.reconciliation.issue_count }} 条问题投递；checksum 与基准水位未更新，
        请按下方「投递对账」处理后重跑。
      </span>
    </div>

    <table>
      <tbody>
        <tr>
          <td style="width: 170px" class="muted">全量重算 checksum</td>
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
          <td class="muted">基准水位（台账 seq）</td>
          <td class="mono">
            {{ report?.baseline_cutoff_seq === null || report?.baseline_cutoff_seq === undefined
              ? '首次运行 · 无基准'
              : `seq ≤ ${report.baseline_cutoff_seq}（${report.base_event_count} 个基准事件）` }}
            → 当前 seq {{ report?.current_cutoff_seq ?? '—' }}
          </td>
        </tr>
        <tr>
          <td class="muted">事件（基准 / 本批新增）</td>
          <td class="mono">{{ report?.base_event_count ?? '—' }} / {{ report?.new_event_count ?? '—' }}</td>
        </tr>
        <tr>
          <td class="muted">迟到 / 重复投递</td>
          <td class="mono">{{ report?.late_event_count ?? 0 }} / {{ report?.duplicate_event_count ?? 0 }}</td>
        </tr>
        <tr>
          <td class="muted">投递处置</td>
          <td class="mono small">
            <span v-for="(count, outcome) in report?.impact_summary ?? {}" :key="outcome" style="margin-right: 10px">
              {{ OUTCOME_LABEL[outcome] ?? outcome }} {{ count }}
            </span>
            <span v-if="!report?.impact_summary">—</span>
          </td>
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

defineProps<{ report: ChecksumReport | null }>()

const OUTCOME_LABEL: Record<string, string> = {
  accepted: '新增',
  replaced: '替换',
  retracted: '撤销',
  duplicate_delivery: '重复忽略',
  retract_missing: '撤销缺失',
}
</script>
