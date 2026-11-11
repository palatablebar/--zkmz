import axios, { AxiosError } from 'axios'
import type { ApiError } from '../types/api'

export const http = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

let unauthorizedHandler: (() => void) | null = null

export function onUnauthorized(handler: () => void) {
  unauthorizedHandler = handler
}

export function setToken(token: string | null) {
  if (token) {
    http.defaults.headers.common['Authorization'] = `Bearer ${token}`
  } else {
    delete http.defaults.headers.common['Authorization']
  }
}

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401 && unauthorizedHandler) {
      unauthorizedHandler()
    }
    return Promise.reject(error)
  },
)

export function describeHttpError(error: unknown): { code: string; message: string } {
  const axiosError = error as AxiosError<ApiError>
  const payload = axiosError.response?.data
  if (payload && typeof payload === 'object' && 'message' in payload) {
    return { code: String(payload.code ?? ''), message: String(payload.message ?? '请求失败') }
  }
  return { code: '', message: axiosError.message || '网络异常' }
}
