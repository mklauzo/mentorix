const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1'

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return undefined as T
  }

  return res.json()
}

// ── Token helpers ──────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('mentorix_token')
}

export function setToken(token: string): void {
  localStorage.setItem('mentorix_token', token)
}

export function clearToken(): void {
  localStorage.removeItem('mentorix_token')
  localStorage.removeItem('mentorix_user')
}

export function getCachedUser(): AuthUser | null {
  if (typeof window === 'undefined') return null
  const raw = localStorage.getItem('mentorix_user')
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}

export function setCachedUser(user: AuthUser): void {
  localStorage.setItem('mentorix_user', JSON.stringify(user))
}

// ── Types ─────────────────────────────────────────────────────

export interface AuthUser {
  id: string
  email: string
  role: 'superadmin' | 'admin' | 'user'
  full_name: string
  first_name: string | null
  last_name: string | null
  tenant_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user_id: string
  role: string
  is_superadmin: boolean
  tenant_id: string | null
}

export interface ChatConfig {
  chat_title: string
  chat_color: string
  welcome_message: string
  is_active: boolean
  chat_logo_url: string | null
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatResponse {
  answer: string
  conversation_id: string
  sources: Array<{
    chunk_id: string
    document_name: string
    content_preview: string
  }>
  tokens_used: number
  estimated_cost_usd: number
}

export interface Tenant {
  id: string
  name: string
  slug: string
  is_active: boolean
  is_blocked: boolean
  blocked_reason: string | null
  llm_model: string
  llm_api_key: string | null
  embedding_api_key: string | null
  embedding_model: string
  system_prompt: string | null
  welcome_message: string
  chat_title: string
  chat_color: string
  chat_logo_url: string | null
  monthly_token_limit: number
  daily_token_limit: number
  tokens_used_month: number
  tokens_used_day: number
  created_at: string
}

export interface Document {
  id: string
  tenant_id: string
  name: string
  mime_type: string | null
  size_bytes: number | null
  status: 'pending' | 'processing' | 'done' | 'error'
  error_message: string | null
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface Conversation {
  id: string
  session_id: string
  started_at: string
  last_message_at: string
  message_count: number
  user_ip_hash: string | null
}

export interface MessageDetail {
  id: string
  role: string
  content: string
  created_at: string
  total_tokens: number | null
  retrieved_chunk_ids: string[] | null
}

export interface AppUser {
  id: string
  email: string
  role: 'superadmin' | 'admin' | 'user'
  full_name: string
  first_name: string | null
  last_name: string | null
  tenant_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

// ── API helpers ────────────────────────────────────────────────

export const authApi = {
  login: async (email: string, password: string): Promise<LoginResponse> =>
    apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  me: async (token: string): Promise<AuthUser> =>
    apiFetch('/auth/me', {}, token),
}

export const ollamaApi = {
  listModels: (token: string): Promise<{ models: string[] }> =>
    apiFetch('/admin/ollama/models', {}, token),

  pullModel: (token: string, model: string): Promise<{ status: string; model: string }> =>
    apiFetch('/admin/ollama/pull', { method: 'POST', body: JSON.stringify({ model }) }, token),

  fetchProviderModels: (
    token: string,
    provider: string,
    apiKey?: string,
  ): Promise<{ models: Array<{ id: string; size_gb?: number }>; error?: string }> =>
    apiFetch('/admin/models/fetch', {
      method: 'POST',
      body: JSON.stringify({ provider, api_key: apiKey || '' }),
    }, token),
}

export const usersApi = {
  list: (token: string, role?: string) =>
    apiFetch<AppUser[]>(`/users${role ? `?role=${role}` : ''}`, {}, token),

  create: (token: string, data: {
    email: string; password: string; role: string;
    first_name?: string; last_name?: string; tenant_id?: string
  }) => apiFetch<AppUser>('/users', { method: 'POST', body: JSON.stringify(data) }, token),

  delete: (token: string, userId: string) =>
    apiFetch<void>(`/users/${userId}`, { method: 'DELETE' }, token),

  setPassword: (token: string, userId: string, newPassword: string) =>
    apiFetch<void>(`/users/${userId}/set-password`, {
      method: 'POST',
      body: JSON.stringify({ new_password: newPassword }),
    }, token),
}
