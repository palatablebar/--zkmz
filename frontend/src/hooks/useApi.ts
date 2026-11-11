import { ref } from 'vue'
import { describeHttpError } from '../api/http'

/** 统一 loading / error 状态，错误文案直接可展示（含后端错误码）。 */
export function useApi() {
  const loading = ref(false)
  const error = ref<{ code: string; message: string } | null>(null)

  async function run<T>(task: () => Promise<T>): Promise<T | null> {
    loading.value = true
    error.value = null
    try {
      return await task()
    } catch (exc) {
      error.value = describeHttpError(exc)
      return null
    } finally {
      loading.value = false
    }
  }

  function reset() {
    error.value = null
  }

  return { loading, error, run, reset }
}
