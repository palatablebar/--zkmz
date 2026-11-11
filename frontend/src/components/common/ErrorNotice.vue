<template>
  <div v-if="error" class="notice" role="alert">
    <strong class="mono" style="font-size: 0.78rem">{{ error.code || 'ERROR' }}</strong>
    <span> · {{ error.message }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{ error: { code: string; message: string } | null }>()
</script>
