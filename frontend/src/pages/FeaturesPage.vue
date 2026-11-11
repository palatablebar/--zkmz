<template>
  <AppShell active-key="features">
    <PageHeader
      op="01"
      title="特征配方"
      sub="每个特征是一张配方单：事件源过滤 → 窗口 → 聚合口径。窗口右端 strict 才排除标签时刻。"
    >
      <template #seal>
        <div>{{ auth.user?.display_name ?? '未登录' }}</div>
        <div>{{ auth.user?.role_label }} · {{ features.length }} 张配方单</div>
      </template>
    </PageHeader>

    <ErrorNotice :error="error" />

    <div class="kpi-row">
      <div class="kpi">
        <div class="k">特征定义</div>
        <div class="v">{{ features.length }}</div>
      </div>
      <div class="kpi">
        <div class="k">inclusive 误用</div>
        <div class="v" :class="store.inclusiveCount ? 'is-annot' : 'is-ok'">{{ store.inclusiveCount }}</div>
      </div>
      <div class="kpi">
        <div class="k">已发布</div>
        <div class="v">{{ publishedCount }}</div>
      </div>
      <div class="kpi">
        <div class="k">当前角色</div>
        <div class="v" style="font-size: var(--step-1)">{{ auth.user?.role_label }}</div>
      </div>
    </div>

    <div class="grid-2">
      <div>
        <FeatureDefinitionCard
          v-for="feature in features"
          :key="feature.id"
          :feature="feature"
          :selected="feature.id === store.selectedId"
          :show-dsl="false"
          @select="select(feature.id)"
        />
      </div>
      <div>
        <section class="card" v-if="store.selected">
          <div class="card-title">
            <h2>{{ store.selected.code }}</h2>
            <span class="op-index">v{{ store.selected.version }} · {{ store.selected.status }}</span>
          </div>
          <pre class="dsl">{{ store.selected.dsl }}</pre>
          <div class="tear" />
          <WindowEditor
            :feature="store.selected"
            :can-edit="auth.canEditFeature"
            :saving="saving"
            @save="save"
            @publish="publish"
          />
          <div class="actions">
            <router-link class="link" :to="`/features/${store.selected.id}/versions`">
              版本与发布轨迹（工序 05）
            </router-link>
          </div>
        </section>
        <EmptyState
          v-else
          title="没有可编辑的配方单"
          hint="seed 尚未执行，或特征定义被清空。执行 python -m scripts.seed_demo 后刷新。"
        />
      </div>
    </div>

    <template #margin>
      <div class="margin-note">
        <span class="stamp">批注 · 002</span>
        <p>
          校验结果：{{ store.inclusiveCount }} 张配方单仍是 inclusive。它们的样本会在「恰好等于标签时刻」
          的事件上出现越界 0ms 的泄漏。
        </p>
      </div>
      <QuotaMeter :quota="auth.quota" />
      <div class="margin-note" style="margin-top: var(--space-4)">
        <span class="stamp" style="color: var(--ink-soft); border-color: var(--ink-line-strong)">操作</span>
        <p>
          owner 改完边界策略 → 保存生成新版本 → 到工序 03 重跑，泄漏应归零。analyst 只能看，保存会 403。
        </p>
      </div>
    </template>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '../components/common/AppShell.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import PageHeader from '../components/common/PageHeader.vue'
import QuotaMeter from '../components/common/QuotaMeter.vue'
import FeatureDefinitionCard from '../components/feature/FeatureDefinitionCard.vue'
import WindowEditor from '../components/feature/WindowEditor.vue'
import { useApi } from '../hooks/useApi'
import { useAuthStore } from '../stores/auth'
import { useFeatureStore } from '../stores/feature'

const auth = useAuthStore()
const store = useFeatureStore()
const { error, run } = useApi()
const saving = ref(false)

const features = computed(() => store.items)
const publishedCount = computed(() => store.items.filter((item) => item.status === 'published').length)

onMounted(async () => {
  await run(() => store.load())
  await auth.refresh()
})

function select(id: number) {
  store.select(id)
}

async function save(payload: Record<string, unknown>) {
  if (!store.selectedId) return
  saving.value = true
  const updated = await run(() => store.save(store.selectedId as number, payload))
  saving.value = false
  if (updated) await run(() => store.load())
}

async function publish() {
  if (!store.selectedId) return
  await run(() => store.publish(store.selectedId as number))
  await run(() => store.load())
}
</script>
