<template>
  <section class="card">
    <div class="card-title">
      <h2>投递对账 · 记录影响</h2>
      <span class="op-index">event_ledger · 每条投递影响了哪些样本</span>
    </div>

    <p v-if="items.length === 0" class="muted small">
      基准水位之后没有新的投递（或本任务尚未运行）。
    </p>

    <table v-else>
      <thead>
        <tr>
          <th>seq</th>
          <th>投递</th>
          <th>处置</th>
          <th>事件（实体 / 类型 / 时间）</th>
          <th>金额 前 → 后</th>
          <th>影响样本</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.seq">
          <td class="mono">{{ item.seq }}</td>
          <td class="mono small">{{ item.delivery_id }}<br /><span class="muted">{{ item.batch_id }}</span></td>
          <td>
            <span class="tag" :class="tone(item.outcome)">{{ OUTCOME_LABEL[item.outcome] ?? item.outcome }}</span>
          </td>
          <td class="small">
            {{ item.entity_key }} · {{ item.event_type }}<br />
            <span class="mono muted">{{ item.event_ts }}</span>
          </td>
          <td class="mono small">
            {{ item.amount_before ?? '—' }} → {{ item.amount_after ?? '—' }}
          </td>
          <td class="small">
            <span v-if="item.affected_sample_count === 0" class="muted">无样本窗口命中</span>
            <span v-else>
              {{ item.affected_sample_count }} 个样本：
              <span v-for="(hit, idx) in item.affected_samples.slice(0, 4)" :key="idx" class="inline-code">
                #{{ hit.label_row_id }}({{ hit.window }})<span v-if="idx < Math.min(item.affected_samples.length, 4) - 1">, </span>
              </span>
              <span v-if="item.affected_samples.length > 4"> …</span>
            </span>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="tear" />
    <p class="small muted">
      处置口径：新增 = 新自然键入库；替换 = 更正同自然键事件（金额前后值留痕）；
      撤销 = retract 生效并从物化视图移除；重复忽略 = 同一 delivery_id 重复投递只生效一次；
      撤销缺失 = retract 找不到对应自然键。命中「重复忽略 / 撤销缺失 / 替换基准内事件」时
      批次判定未对平，回填保留上一次结果。
    </p>
  </section>
</template>

<script setup lang="ts">
import type { LedgerImpactItem } from '../../types/backfill'

defineProps<{ items: LedgerImpactItem[] }>()

const OUTCOME_LABEL: Record<string, string> = {
  accepted: '新增',
  replaced: '替换',
  retracted: '撤销',
  duplicate_delivery: '重复忽略',
  retract_missing: '撤销缺失',
}

function tone(outcome: string): string {
  if (outcome === 'accepted') return 'tag-ok'
  if (outcome === 'duplicate_delivery' || outcome === 'retract_missing') return 'tag-annot'
  return ''
}
</script>
