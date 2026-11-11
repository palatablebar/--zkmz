import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { fetchMe, login as loginApi } from '../api/auth'
import { setToken } from '../api/http'
import type { Quota, User } from '../types/api'

const TOKEN_KEY = 'featpoint.token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<User | null>(null)
  const quota = ref<Quota | null>(null)

  const role = computed(() => user.value?.role ?? '')
  const isOwner = computed(() => role.value === 'owner')
  const isAnalyst = computed(() => role.value === 'analyst')
  const isViewer = computed(() => role.value === 'viewer')
  const canEditFeature = computed(() => isOwner.value)
  const canRunSample = computed(() => isOwner.value || isAnalyst.value)
  const canBackfill = computed(() => isOwner.value)

  if (token.value) setToken(token.value)

  async function login(email: string, password: string) {
    const payload = await loginApi(email, password)
    token.value = payload.token
    user.value = payload.user
    quota.value = payload.quota
    localStorage.setItem(TOKEN_KEY, payload.token)
    setToken(payload.token)
    return payload
  }

  async function refresh() {
    if (!token.value) return
    try {
      const payload = await fetchMe()
      user.value = payload.user
      quota.value = payload.quota
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null
    quota.value = null
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
  }

  return {
    token,
    user,
    quota,
    role,
    isOwner,
    isAnalyst,
    isViewer,
    canEditFeature,
    canRunSample,
    canBackfill,
    login,
    refresh,
    logout,
  }
})
