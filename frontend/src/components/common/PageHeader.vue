<template>
  <header class="sheet-head">
    <div>
      <div class="op">工序 {{ op }} / {{ stepTitle }}</div>
      <h1>{{ title }}</h1>
      <p v-if="sub" class="sub">{{ sub }}</p>
    </div>
    <div class="seal">
      <slot name="seal">
        <div>岚舟科技 · 风控算法组</div>
        <div>工艺卡 No. F-2026-01</div>
      </slot>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { OPERATION_STEPS } from '../../constants/recipe'

const props = defineProps<{ op: string; title: string; sub?: string; stepKey?: string }>()
const stepTitle = computed(
  () => OPERATION_STEPS.find((step) => step.code === props.op)?.title ?? '工艺卡',
)
</script>
