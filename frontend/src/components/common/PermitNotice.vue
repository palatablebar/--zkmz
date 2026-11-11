<template>
  <div class="notice" v-if="!allowed">
    <strong>只读视图</strong> · 当前角色「{{ roleLabel }}」不能修改{{ target }}；
    {{ reason }}
  </div>
</template>

<script setup lang="ts">
defineProps<{ allowed: boolean; roleLabel: string; target: string; reason: string }>()
</script>
