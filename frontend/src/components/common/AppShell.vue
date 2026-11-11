<template>
  <div class="shell">
    <aside class="rail">
      <div class="rail-brand">FeatPoint · 工艺卡</div>
      <router-link
        v-for="step in steps"
        :key="step.code"
        :to="step.to"
        class="rail-step"
        :class="{ 'is-active': step.key === activeKey }"
      >
        <strong>{{ step.code }}</strong>
        <span>{{ step.title }}</span>
      </router-link>
      <div style="margin-top: auto">
        <button class="btn btn-ghost small" style="width: 100%" @click="logout">退出</button>
      </div>
    </aside>

    <main class="main">
      <slot />
    </main>

    <aside class="margin-col">
      <div class="margin-note">
        <span class="stamp">批注 · margin</span>
        <p>{{ MARGIN_NOTES[activeKey] || '按工序逐步校验，任一格越界都要回到 01 工序改口径。' }}</p>
      </div>
      <slot name="margin" />
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { MARGIN_NOTES, OPERATION_STEPS } from '../../constants/recipe'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{ activeKey: string }>()
const steps = OPERATION_STEPS
const auth = useAuthStore()
const router = useRouter()
const activeKey = computed(() => props.activeKey)

function logout() {
  auth.logout()
  router.replace('/login')
}
</script>
