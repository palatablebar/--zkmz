export interface ApiError {
  code: string
  message: string
  detail?: Record<string, unknown> | null
  request_id?: string
}

export interface PageResult<T> {
  items: T[]
  total: number
}

export interface Quota {
  daily_quota: number
  quota_used: number
  quota_remaining: number
  rate_window_seconds: number
  rate_window_max: number
}

export interface User {
  id: number
  email: string
  display_name: string
  role: string
  role_label: string
}
