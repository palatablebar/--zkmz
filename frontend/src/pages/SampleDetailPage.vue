<template>
  <AppShell active-key="pit">
    <PageHeader
      op="03"
      title="点时间校验报告"
      :sub="job ? `${job.code} · ${job.name}` : '选择一个样本任务查看泄漏矩阵与边界探针'"
    >
      <template #seal>
        <div>{{ job?.created_by ?? '—' }}</div>
        <div>样本 {{ job?.sample_count ?? 0 }} · 泄漏 {{ job?.leak_count ?? 0 }}</div>
      </template>
    </PageHeader>

    <ErrorNotice :error="error" />
    <div v-if="loadingJob" class="loading-note">正在读取校验报告…</div>

    <template v-if="job">
      <div class="notice" v-if="job.status === 'failed'">
        <strong>任务失败</strong> · reason={{ job.failure_reason }} ·
        {{ report?.failure?.message }}
        <button class="btn btn-ghost" style="margin-left: 12px" :disabled="rerunning || !auth.canRunSample" @click="rerun">
          修复后重跑
        </button>
      </div>

      <div class="kpi-row">
        <div class="kpi">
          <div class="k">泄漏处数</div>
          <div class="v" :class="job.leak_count ? 'is-annot' : 'is-ok'">{{ job.leak_count }}</div>
        </div>
        <div class="kpi">
          <div class="k">样本数</div>
          <div class="v">{{ job.sample_count }}</div>
        </div>
        <div class="kpi">
          <div class="k">命中样本</div>
          <div class="v">{{ report?.leak_summary?.leak_samples ?? 0 }}</div>
        </div>
        <div class="kpi">
          <div class="k">最大越界</div>
          <div class="v">{{ report?.leak_summary?.max_overflow_ms ?? 0 }}<span style="font-size: 0.8rem"> ms</span></div>
        </div>
      </div>

      <div class="actions" style="margin-top: 0; margin-bottom: var(--space-4)">
        <button class="btn btn-annot" :disabled="rerunning || !auth.canRunSample" @click="rerun">
          {{ rerunning ? '重跑中…' : '重跑样本任务' }}
        </button>
        <router-link class="link" to="/samples/new">再建一个样本任务</router-link>
        <router-link class="link" to="/features">去工序 01 修正边界</router-link>
      </div>

      <section class="card" v-if="(report?.leak_summary?.by_feature ?? []).length">
        <div class="card-title"><h2>泄漏归因</h2><span class="op-index">by feature</span></div>
        <table>
          <thead>
            <tr><th>特征</th><th>越界处数</th><th>最大越界</th><th>声明边界</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in report?.leak_summary?.by_feature ?? []" :key="item.feature_code">
              <td>{{ item.feature_code }}</td>
              <td>{{ item.count }}</td>
              <td>{{ item.max_overflow_ms }} ms</td>
              <td :style="{ color: item.policy === 'inclusive' ? 'var(--annot)' : 'inherit' }">{{ item.policy }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <LeakMatrix :matrix="report?.matrix ?? null" />
      <BoundaryProbeTable :probes="report?.boundary_probes ?? []" />

      <section class="card">
        <div class="card-title"><h2>泄漏明细</h2><span class="op-index">leaks</span></div>
        <p v-if="(report?.leaks ?? []).length === 0" class="muted small">当前口径下没有泄漏，样本可进训练集。</p>
        <table v-else>
          <thead>
            <tr><th>特征</th><th>实体</th><th>标签时间</th><th>事件时间</th><th>越界</th><th>kind</th></tr>
          </thead>
          <tbody>
            <tr v-for="leak in report?.leaks ?? []" :key="`${leak.feature_code}-${leak.label_row_id}`">
              <td>{{ leak.feature_code }}</td>
              <td>{{ leak.entity_key }}</td>
              <td>{{ fmtTime(leak.label_time) }}</td>
              <td>{{ fmtTime(leak.event_ts) }}</td>
              <td style="color: var(--annot)">{{ leak.overflow_ms }} ms</td>
              <td>{{ LEAK_KIND[leak.kind] ?? leak.kind }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="card">
        <div class="card-title"><h2>样本预览</h2><span class="op-index">sample_row</span></div>
        <table>
          <thead>
            <tr><th>实体</th><th>标签时间</th><th>y</th><th>特征 JSON</th><th>泄漏</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in report?.sample_preview ?? []" :key="row.id">
              <td>{{ row.entity_key }}</td>
              <td>{{ fmtShortTime(row.label_time) }}</td>
              <td>{{ row.label }}</td>
              <td>{{ JSON.stringify(row.features) }}</td>
              <td :style="{ color: row.has_leak ? 'var(--annot)' : 'inherit' }">
                {{ row.has_leak ? '越界' : row.no_event ? '无事件' : '通过' }}
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <ParamSnapshotCard :job="job" />
    </template>

    <template #margin>
      <div class="margin-note">
        <span class="stamp">批注 · 004</span>
        <p>
          两处泄漏都落在「事件时间戳恰好等于标签时间」的样本上：inclusive 边界把它算进窗口，越界 0ms。
          修正 strict 后这两格应当熄灭。
        </p>
      </div>
      <div class="margin-note" style="color: var(--ink-soft); border-left-color: var(--ink-line-strong)">
        <span class="stamp" style="color: var(--ink-soft); border-color: var(--ink-line-strong)">口径</span>
        <p>窗口 [label_time − W, label_time) ；聚合 sum/count/max/last；无事件记 0（recency 记 −1）。</p>
      </div>
    </template>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/common/AppShell.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import PageHeader from '../components/common/PageHeader.vue'
import BoundaryProbeTable from '../components/sample/BoundaryProbeTable.vue'
import LeakMatrix from '../components/sample/LeakMatrix.vue'
import ParamSnapshotCard from '../components/sample/ParamSnapshotCard.vue'
import { LEAK_KIND } from '../constants/enums'
import { useApi } from '../hooks/useApi'
import { useAuthStore } from '../stores/auth'
import { useSampleStore } from '../stores/sample'
import { fmtShortTime, fmtTime } from '../utils/format'

const route = useRoute()
const auth = useAuthStore()
const store = useSampleStore()
const { error, run } = useApi()
const loadingJob = ref(true)
const rerunning = ref(false)

const job = computed(() => store.report?.job ?? null)
const report = computed(() => store.report)

const jobId = computed(() => Number(route.params.id))

onMounted(async () => {
  await load()
  await auth.refresh()
})

watch(jobId, load)

async function load() {
  loadingJob.value = true
  await run(() => store.loadReport(jobId.value))
  loadingJob.value = false
}

async function rerun() {
  rerunning.value = true
  const ok = await run(async () => {
    await store.run(jobId.value)
    await store.waitForCompletion(jobId.value)
    await store.loadReport(jobId.value)
  })
  rerunning.value = false
  if (!ok) loadingJob.value = false
}
</script>
