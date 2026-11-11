<template>
  <article class="card" :class="{ 'is-selected': selected }" @click="$emit('select', feature.id)">
    <div class="card-title">
      <h2 style="font-size: var(--step-1)">{{ feature.code }}</h2>
      <span class="op-index">v{{ feature.version }}</span>
    </div>
    <p class="small muted" style="margin-bottom: 8px">{{ feature.name }}</p>
    <div class="pill-row">
      <span class="tag tag-ink">{{ feature.window_label }}</span>
      <span class="tag" :class="feature.boundary_policy === 'inclusive' ? 'tag-annot' : 'tag-ok'">
        {{ feature.boundary_policy }}
      </span>
      <span class="tag">{{ feature.aggregate_kind }}</span>
      <span v-if="feature.event_type" class="tag">{{ feature.event_type }}</span>
      <StatusTag :status="feature.status" :labels="FEATURE_STATUS" />
    </div>
    <pre v-if="showDsl" class="dsl" style="margin-top: 10px">{{ feature.dsl }}</pre>
  </article>
</template>

<script setup lang="ts">
import { FEATURE_STATUS } from '../../constants/enums'
import type { Feature } from '../../types/feature'
import StatusTag from '../common/StatusTag.vue'

withDefaults(defineProps<{ feature: Feature; selected?: boolean; showDsl?: boolean }>(), {
  selected: false,
  showDsl: true,
})
defineEmits<{ select: [id: number] }>()
</script>

<style scoped>
.card {
  cursor: pointer;
  transition: transform 180ms var(--ease-out);
}

.card:hover {
  transform: translateY(-1px);
}

.is-selected {
  border-color: var(--annot);
}
</style>
