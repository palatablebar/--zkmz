<template>
  <div class="card" style="text-align: left">
    <div class="card-title"><h2>{{ title }}</h2><span class="op-index">空</span></div>
    <p class="muted small">{{ hint }}</p>
    <div class="actions" v-if="$slots.default"><slot /></div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; hint: string }>()
</script>
