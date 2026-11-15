const baseUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const tokenKey = 'campusintel_access_token'

export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); this.name = 'ApiError' }
}

export const readToken = () => localStorage.getItem(tokenKey)
export const saveToken = (token: string | null) => token ? localStorage.setItem(tokenKey, token) : localStorage.removeItem(tokenKey)

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = readToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${baseUrl}${path}`, { ...options, headers })
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null
    throw new ApiError(payload?.detail ?? `Request failed (${response.status})`, response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export type User = { id: string; full_name: string; email: string; role: string; department_id: string | null }
export type Category = { id: string; category_name: string; default_department_id: string | null }
export type Department = { id: string; department_code: string; department_name: string }
export type RequestRecord = {
  id: string; ticket_number: string; subject: string; description: string; current_status: string
  category_id: string | null; assigned_department_id: string | null; assigned_staff_id: string | null
  ml_predicted_category: string | null; ml_confidence: number | null; ml_predicted_department: string | null
  created_at: string; resolved_at: string | null
}
export type EventRecord = { event_type: string; new_status: string | null; description: string | null; event_timestamp: string }
export type CommentRecord = { id: string; author_id: string; message: string; visibility: string; created_at: string }
export type PredictionRecord = { model_name: string; model_version: string; predicted_category: string; confidence_score: number; predicted_department: string | null; explanation: { dataset_type?: string; learned_terms?: string[]; disclaimer?: string } }
export type DuplicateRecord = { request_id: string; ticket_number: string; subject: string; status: string; similarity: number }
export type ResolutionEstimate = { available: boolean; estimate_hours: number | null; sample_size: number; model_version: string; note: string }
export type AnalyticsSummary = { total_requests: number; by_status: Record<string, number>; resolved_count: number; average_resolution_hours: number | null; source: string }
export type DepartmentPerformance = { department_id: string; department_name: string; open_requests: number; resolved_requests: number; average_resolution_hours: number | null }
export type WorkflowMetrics = { open_requests: number; resolved_requests: number; average_resolution_hours: number | null; event_count: number; mean_inter_event_hours: number | null; handoff_count: number; reassignment_count: number }
export type AttachmentRecord = { id: string; original_filename: string; mime_type: string; file_size: number; created_at: string }
export type AdminUser = { id: string; full_name: string; email: string; role: string; department_id: string | null; is_active: boolean; created_at: string }
export type AuditRecord = { id: string; actor_id: string | null; action: string; resource_type: string; resource_id: string | null; created_at: string }
export type FeedbackRecord = { saved: boolean; rating?: number; feedback_text?: string | null; created_at?: string }
