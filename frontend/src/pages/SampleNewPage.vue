<template>
  <AppShell active-key="samples">
    <PageHeader
      op="02"
      title="样本炼制"
      sub="选标签集与特征口径，冻结参数快照后交给 worker 用 pit_engine 真算；样本落库后到工序 03 看泄漏。"
    >
      <template #seal>
        <div>标签集 {{ labelSets.length }} 个</div>
        <div>特征 {{ features.length }} 张配方单</div>
      </template>
    </PageHeader>

    <ErrorNotice :error="error" />
    <PermitNotice
      :allowed="auth.canRunSample"
      :role-label="auth.user?.role_label ?? ''"
      target="样本任务"
      reason="viewer 是风控审计角色，只读校验报告与版本轨迹。"
    />

    <form class="grid-2" @submit.prevent="submit">
      <section class="card">
        <div class="card-title"><h2>标签集</h2><span class="op-index">label_set</span></div>
        <label v-for="item in labelSets" :key="item.id" class="select-row" :class="{ 'is-on': selectedSets.includes(item.id) }">
          <input v-model="selectedSets" type="checkbox" :value="item.id" :disabled="!auth.canRunSample" />
          <span>
            <strong class="mono" style="font-size: 0.78rem">{{ item.code }}</strong>
            <span class="muted small"> · {{ item.name }}</span>
            <span class="small muted" style="display: block">
              {{ item.sample_count }} 行 · {{ item.entity_count }} 个账户 · 正样本 {{ item.label_positive }}
            </span>
            <span class="small muted">{{ fmtTime(item.first_label_time) }} → {{ fmtTime(item.last_label_time) }}</span>
          </span>
        </label>
        <EmptyState v-if="labelSets.length === 0" title="没有标签集" hint="seed 未执行或标签集被清空。" />
      </section>

      <section class="card">
        <div class="card-title"><h2>特征口径</h2><span class="op-index">feature_def</span></div>
        <label
          v-for="feature in features"
          :key="feature.id"
          class="select-row"
          :class="{ 'is-on': selectedFeatures.includes(feature.id) }"
        >
          <input v-model="selectedFeatures" type="checkbox" :value="feature.id" :disabled="!auth.canRunSample" />
          <span>
            <strong class="mono" style="font-size: 0.78rem">{{ feature.code }}</strong>
            <span class="small muted" style="display: block">
              {{ feature.window_label }} · {{ feature.aggregate_kind }} · 边界
              <span :style="{ color: feature.boundary_policy === 'inclusive' ? 'var(--annot)' : 'inherit' }">
                {{ feature.boundary_policy }}
              </span>
            </span>
            <span class="small muted">v{{ feature.version }} · {{ feature.status }}</span>
          </span>
        </label>
      </section>

      <section class="card" style="grid-column: 1 / -1">
        <div class="card-title"><h2>参数快照</h2><span class="op-index">snapshot</span></div>
        <div class="grid-3">
          <div class="field">
            <label>时间范围起点（可空 = 全量）</label>
            <input v-model="rangeStart" placeholder="2026-02-01T00:00:00Z" :disabled="!auth.canRunSample" />
          </div>
          <div class="field">
            <label>时间范围终点（可空 = 全量）</label>
            <input v-model="rangeEnd" placeholder="2026-03-15T00:00:00Z" :disabled="!auth.canRunSample" />
          </div>
          <div class="field">
            <label>任务名称</label>
            <input v-model="jobName" :disabled="!auth.canRunSample" />
          </div>
        </div>
        <p class="small muted">
          预期样本数：
          <strong class="mono">{{ expectedSamples }}</strong>
          （所选标签集行数合计）；边界策略由所选特征决定，混合时取最宽松口径并在快照里留痕。
        </p>
        <div class="actions">
          <button class="btn btn-annot" type="submit" :disabled="!auth.canRunSample || submitting">
            {{ submitting ? '提交中…' : '运行样本炼制' }}
          </button>
          <router-link class="link" to="/features">回到工序 01 修改边界</router-link>
        </div>
      </section>
    </form>

    <template #margin>
      <div class="margin-note">
        <span class="stamp">批注 · 003</span>
        <p>
          样本任务由 worker（Celery）真跑 pit_engine；创建后参数快照冻结，重跑用当前已发布定义——
          修正边界后重跑立即生效。
        </p>
      </div>
      <QuotaMeter :quota="auth.quota" />
    </template>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../components/common/AppShell.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import PageHeader from '../components/common/PageHeader.vue'
import PermitNotice from '../components/common/PermitNotice.vue'
import QuotaMeter from '../components/common/QuotaMeter.vue'
import { useApi } from '../hooks/useApi'
import { useAuthStore } from '../stores/auth'
import { useFeatureStore } from '../stores/feature'
import { useSampleStore } from '../stores/sample'
import { fmtTime } from '../utils/format'

const auth = useAuthStore()
const featureStore = useFeatureStore()
const sampleStore = useSampleStore()
const router = useRouter()
const { error, run } = useApi()

const selectedSets = ref<number[]>([])
const selectedFeatures = ref<number[]>([])
const rangeStart = ref('')
const rangeEnd = ref('')
const jobName = ref(`样本炼制 · ${new Date().toISOString().slice(0, 10)}`)
const submitting = ref(false)

const labelSets = computed(() => sampleStore.labelSets)
const features = computed(() => featureStore.items)
const expectedSamples = computed(() =>
  labelSets.value
    .filter((item) => selectedSets.value.includes(item.id))
    .reduce((sum, item) => sum + item.sample_count, 0),
)

onMounted(async () => {
  await run(() => sampleStore.loadLabelSets())
  await run(() => featureStore.load())
  if (selectedSets.value.length === 0) selectedSets.value = labelSets.value.map((item) => item.id)
  if (selectedFeatures.value.length === 0) selectedFeatures.value = features.value.map((item) => item.id)
  await auth.refresh()
})

async function submit() {
  submitting.value = true
  const payload: Record<string, unknown> = {
    name: jobName.value,
    label_set_ids: selectedSets.value,
    feature_ids: selectedFeatures.value,
  }
  if (rangeStart.value.trim()) payload.range_start = rangeStart.value.trim()
  if (rangeEnd.value.trim()) payload.range_end = rangeEnd.value.trim()
  const job = await run(() => sampleStore.create(payload))
  if (job) {
    await run(() => sampleStore.run(job.id))
    router.push(`/samples/${job.id}`)
  }
  submitting.value = false
}
</script>
