import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

// Inject JWT token on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('kavach_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const login = (username: string, password: string, role: string) =>
  api.post('/auth/login', { username, password, role }).then((r) => r.data)

// ─── Predict ──────────────────────────────────────────────────────────────────

export const predict = (borrower_id: string) =>
  api.post('/predict', { borrower_id }).then((r) => r.data)

// ─── Explain ──────────────────────────────────────────────────────────────────

export const explain = (borrower_id: string) =>
  api.get(`/explain/${borrower_id}`).then((r) => r.data)

// ─── Portfolio ────────────────────────────────────────────────────────────────

export interface PortfolioParams {
  loan_type?: string
  industry?: string
  region?: string
  min_stress?: number
  sort_by?: string
  page?: number
  page_size?: number
}

export const getPortfolio = (params: PortfolioParams = {}) =>
  api.get('/portfolio', { params }).then((r) => r.data)

// ─── Simulate ─────────────────────────────────────────────────────────────────

export interface HypotheticalChanges {
  dscr_delta?: number
  gst_delay_days?: number
  bureau_score_delta?: number
  overdraft_utilization_delta?: number
  dpd_change?: number
  epfo_change_pct?: number
}

export const simulate = (borrower_id: string, changes: HypotheticalChanges) =>
  api.post('/simulate', { borrower_id, hypothetical_changes: changes }).then((r) => r.data)

// ─── Analytics ────────────────────────────────────────────────────────────────

export const getAnalytics = () =>
  api.get('/analytics').then((r) => r.data)

// ─── Governance ───────────────────────────────────────────────────────────────

export const getGovernance = () =>
  api.get('/governance').then((r) => r.data)

// ─── Alerts ───────────────────────────────────────────────────────────────────

export const getAlerts = (days: number = 7) =>
  api.get('/alerts', { params: { days } }).then((r) => r.data)

// ─── Health ───────────────────────────────────────────────────────────────────

export const health = () =>
  api.get('/health').then((r) => r.data).catch(() => ({ status: 'error' }))

// ─── User Management ──────────────────────────────────────────────────────────

export const getUsers = () =>
  api.get('/users').then((r) => r.data)

export const createUser = (payload: { username: string; name: string; role: string; password: string }) =>
  api.post('/users', payload).then((r) => r.data)

export const updateUser = (id: number, payload: Partial<{ name: string; role: string; password: string; is_active: boolean }>) =>
  api.patch(`/users/${id}`, payload).then((r) => r.data)

export const deactivateUser = (id: number) =>
  api.delete(`/users/${id}`).then((r) => r.data)

export default api
