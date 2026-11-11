import { http } from './http'
import type { Quota, User } from '../types/api'

export interface LoginResponse {
  token: string
  user: User
  quota: Quota
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const { data } = await http.post<LoginResponse>('/auth/login', { email, password })
  return data
}

export async function fetchMe(): Promise<{ user: User; quota: Quota }> {
  const { data } = await http.get('/auth/me')
  return data
}
