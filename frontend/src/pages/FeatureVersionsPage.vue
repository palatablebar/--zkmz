<template>
  <AppShell active-key="versions">
    <PageHeader
      op="05"
      title="版本与发布"
      :sub="feature ? `${feature.code} · ${feature.name}` : '读取特征版本轨迹'"
    >
      <template #seal>
        <div>v{{ feature?.version ?? '—' }} · {{ feature?.status ?? '—' }}</div>
        <div>{{ audits.length }} 条审计</div>
      </template>
    </PageHeader>

    <ErrorNotice :error="error" />

    <div class="kpi-row" v-if="feature">
      <div class="kpi">
        <div class="k">当前版本</div>
        <div class="v">v{{ feature.version }}</div>
      </div>
      <div class="kpi">
        <div class="k">边界策略</div>
        <div class="v" :class="feature.boundary_policy === 'inclusive' ? 'is-annot' : 'is-ok'" style="font-size: var(--step-1)">
          {{ feature.boundary_policy }}
        </div>
      </div>
      <div class="kpi">
        <div class="k">版本轨迹</div>
        <div class="v">{{ versions.length }}</div>
      </div>
      <div class="kpi">
        <div class="k">发布状态</div>
        <div class="v" style="font-size: var(--step-1)">{{ FEATURE_STATUS[feature.status] }}</div>
      </div>
    </div>

    <section class="card" v-if="feature">
      <div class="card-title"><h2>版本轨迹</h2><span class="op-index">feature_version</span></div>
      <table>
        <thead>
          <tr><th>版本</th><th>口径快照</th><th>备注</th><th>操作人</th><th>时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in versions" :key="item.id">
            <td>v{{ item.version_no }}</td>
            <td class="mono">
              {{ item.snapshot.window_label }} · {{ item.snapshot.aggregate_kind }} ·
              <span :style="{ color: item.snapshot.boundary_policy === 'inclusive' ? 'var(--annot)' : 'inherit' }">
                {{ item.snapshot.boundary_policy }}
              </span>
            </td>
            <td>{{ item.change_note }}</td>
            <td>{{ item.changed_by }}</td>
            <td>{{ fmtShortTime(item.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div class="actions">
        <button class="btn btn-ghost" :disabled="!auth.isOwner" @click="publish">发布当前定义</button>
        <router-link class="link" to="/features">回到工序 01</router-link>
      </div>
    </section>

    <section class="card">
      <div class="card-title"><h2>审计轨迹</h2><span class="op-index">audit_log</span></div>
      <p v-if="audits.length === 0" class="muted small">该特征暂无审计记录（只读角色也能看到全部轨迹）。</p>
      <table v-else>
        <thead><tr><th>动作</th><th>操作人</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="item in audits" :key="item.id">
            <td>{{ item.action }}</td>
            <td>{{ item.actor_email }}</td>
            <td>{{ fmtShortTime(item.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <LeakMatrix v-if="latestMatrix" :matrix="latestMatrix" />

    <template #margin>
      <div class="margin-note">
        <span class="stamp">批注 · 006</span>
        <p>
          发布后的定义冻结，修改需新建版本；每次修改都会写入 feature_version 快照与 audit_log，
          风控审计可回放到任意一版口径。
        </p>
      </div>
      <div class="margin-note" v-if="latestJob" style="color: var(--ink-soft); border-left-color: var(--ink-line-strong)">
        <span class="stamp" style="color: var(--ink-soft); border-color: var(--ink-line-strong)">最近校验</span>
        <p>
          {{ latestJob.code }}：泄漏 {{ latestJob.leak_count }} 处 / 样本 {{ latestJob.sample_count }} 行。
          <router-link class="link" :to="`/samples/${latestJob.id}`">查看矩阵</router-link>
        </p>
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
import LeakMatrix from '../components/sample/LeakMatrix.vue'
import { getFeatureVersions, publishFeature } from '../api/feature'
import { getSampleJob, listSampleJobs } from '../api/sample'
import { FEATURE_STATUS } from '../constants/enums'
import { useApi } from '../hooks/useApi'
import { useAuthStore } from '../stores/auth'
import { useFeatureStore } from '../stores/feature'
import type { AuditEntry, Feature, FeatureVersion } from '../types/feature'
import type { LeakMatrixData, SampleJob } from '../types/sample'
import { fmtShortTime } from '../utils/format'

const route = useRoute()
const auth = useAuthStore()
const featureStore = useFeatureStore()
const { error, run } = useApi()

const feature = ref<Feature | null>(null)
const versions = ref<FeatureVersion[]>([])
const audits = ref<AuditEntry[]>([])
const latestJob = ref<SampleJob | null>(null)
const latestMatrix = ref<LeakMatrixData | null>(null)

const featureId = computed(() => Number(route.params.id))

onMounted(async () => {
  await load()
  await auth.refresh()
})

watch(featureId, load)

async function load() {
  const payload = await run(() => getFeatureVersions(featureId.value))
  if (payload) {
    feature.value = payload.feature
    versions.value = payload.versions
    audits.value = payload.audits
  }
  const jobs = await run(() => listSampleJobs())
  const completed = (jobs?.items ?? []).filter((item) => item.status === 'completed')
  if (completed.length > 0) {
    latestJob.value = completed[0]
    const detail = await run(() => getSampleJob(completed[0].id))
    latestMatrix.value = detail?.report.matrix ?? null
  }
}

async function publish() {
  if (!feature.value) return
  const updated = await run(() => publishFeature(feature.value!.id))
  if (updated) {
    feature.value = updated
    await load()
  }
  await featureStore.load().catch(() => undefined)
}
</script>
