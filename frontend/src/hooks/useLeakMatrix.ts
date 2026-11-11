import { computed } from 'vue'
import type { LeakMatrixData } from '../types/sample'
import { cellTone } from '../utils/leakTone'

/** 泄漏矩阵的展示派生：图例、逐格点亮序号、泄漏优先排序。 */
export function useLeakMatrix(matrix: () => LeakMatrixData | null) {
  const features = computed(() => matrix()?.features ?? [])
  const samples = computed(() => {
    const rows = matrix()?.samples ?? []
    return [...rows].sort((a, b) => {
      const aLeak = Object.values(a.cells).some((cell) => cell.leak) ? 0 : 1
      const bLeak = Object.values(b.cells).some((cell) => cell.leak) ? 0 : 1
      return aLeak - bLeak
    })
  })
  const legend = [
    { tone: 'cell-leak', label: '泄漏（越界）' },
    { tone: 'cell-dense', label: '窗口内事件 ≥ 5' },
    { tone: 'cell-normal', label: '窗口内有事件' },
    { tone: 'cell-noevent', label: '窗口内无事件' },
  ]
  const litCount = computed(
    () =>
      samples.value.reduce(
        (sum, row) => sum + Object.values(row.cells).filter((cell) => cell.leak).length,
        0,
      ),
  )
  return { features, samples, legend, litCount, cellTone }
}
