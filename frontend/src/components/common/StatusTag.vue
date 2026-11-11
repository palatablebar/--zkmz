<template>
  <span class="tag" :class="toneClass">{{ label }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string; labels: Record<string, string> }>()
const label = computed(() => props.labels[props.status] ?? props.status)
const toneClass = computed(() => {
  if (['completed', 'published'].includes(props.status)) return 'tag-ok'
  if (['failed', 'deprecated'].includes(props.status)) return 'tag-annot'
  if (['running'].includes(props.status)) return 'tag-warn'
  return 'tag-ink'
})
</script>
