<template>
  <form @submit.prevent="$emit('save', draft)">
    <div class="grid-2">
      <div class="field">
        <label>特征名称</label>
        <input v-model="draft.name" :disabled="!canEdit" />
      </div>
      <div class="field">
        <label>聚合口径</label>
        <select v-model="draft.aggregate_kind" :disabled="!canEdit">
          <option v-for="agg in AGGREGATE" :key="agg" :value="agg">{{ agg }}</option>
        </select>
      </div>
      <div class="field">
        <label>窗口</label>
        <select v-model="draft.window_label" :disabled="!canEdit">
          <option v-for="w in WINDOWS" :key="w" :value="w">{{ w }}</option>
        </select>
      </div>
      <div class="field">
        <label>边界策略（右端）</label>
        <select v-model="draft.boundary_policy" :disabled="!canEdit">
          <option value="strict">strict · [t-W, t)</option>
          <option value="inclusive">inclusive · (t-W, t]</option>
        </select>
        <span class="hint">inclusive 会把「恰好等于标签时刻」的事件算进特征</span>
      </div>
    </div>
    <div class="field">
      <label>变更备注（写入版本轨迹与审计）</label>
      <input v-model="draft.change_note" :disabled="!canEdit" placeholder="例如：修正边界策略为 strict" />
    </div>
    <div class="actions">
      <button class="btn btn-annot" type="submit" :disabled="!canEdit || saving">
        {{ saving ? '保存中…' : '保存并生成新版本' }}
      </button>
      <button class="btn btn-ghost" type="button" :disabled="!canEdit" @click="$emit('publish')">
        发布
      </button>
      <span v-if="!canEdit" class="small muted">只读：仅 owner 可修改特征定义</span>
    </div>
  </form>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import { AGGREGATE, WINDOWS } from '../../constants/enums'
import type { Feature } from '../../types/feature'

const props = defineProps<{ feature: Feature; canEdit: boolean; saving: boolean }>()
defineEmits<{ save: [payload: Record<string, unknown>]; publish: [] }>()

const draft = reactive({
  name: '',
  window_label: '7d',
  boundary_policy: 'strict',
  aggregate_kind: 'last',
  change_note: '',
})

watch(
  () => props.feature,
  (feature) => {
    draft.name = feature.name
    draft.window_label = feature.window_label
    draft.boundary_policy = feature.boundary_policy
    draft.aggregate_kind = feature.aggregate_kind
    draft.change_note = ''
  },
  { immediate: true },
)
</script>
