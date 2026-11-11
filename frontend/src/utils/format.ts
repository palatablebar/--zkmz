export function fmtTime(value: string | null | undefined): string {
  if (!value) return '—'
  return value.replace('T', ' ').replace('Z', ' UTC').replace('.000', '')
}

export function fmtShortTime(value: string | null | undefined): string {
  if (!value) return '—'
  return value.slice(5, 16).replace('T', ' ')
}

export function fmtNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function fmtInt(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('zh-CN')
}

export function fmtMs(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value} ms`
}

export function shortChecksum(value: string | null | undefined): string {
  if (!value) return '—'
  return `${value.slice(0, 10)}…${value.slice(-6)}`
}
