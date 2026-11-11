import type { LeakCell } from '../types/sample'

/** 泄漏矩阵单元格的色阶（车间工艺卡的批注红 / 油墨蓝黑）。 */
export function cellTone(cell: LeakCell | undefined): string {
  if (!cell) return 'cell-empty'
  if (cell.leak) return 'cell-leak'
  if (cell.matched_events === 0) return 'cell-noevent'
  if (cell.matched_events >= 5) return 'cell-dense'
  return 'cell-normal'
}

export function leakRow(entityKey: string, labelTime: string): string {
  return `${entityKey} @ ${labelTime.replace('T', ' ').slice(0, 19)}`
}
