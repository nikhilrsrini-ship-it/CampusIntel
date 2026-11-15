import { FormEvent, useCallback, useEffect, useState } from 'react'
import { api, AdminUser, AnalyticsSummary, ApiError, AttachmentRecord, AuditRecord, Category, CommentRecord, Department, DepartmentPerformance, DuplicateRecord, EventRecord, FeedbackRecord, PredictionRecord, readToken, RequestRecord, ResolutionEstimate, saveToken, User, WorkflowMetrics } from './services/api'

type AuthResult = { access_token: string; user: User }
type Notification = { id: string; title: string; message: string; is_read: boolean }
type AuthMode = 'login' | 'register' | 'forgot' | 'reset'
const institutionName = import.meta.env.VITE_INSTITUTION_NAME || 'CAMPUSINTEL demonstration workspace'
const supportEmail = import.meta.env.VITE_SUPPORT_EMAIL || ''
const privacyUrl = import.meta.env.VITE_PRIVACY_URL || ''
const demoMode = import.meta.env.VITE_DEMO_MODE !== 'false'
const passwordResetEnabled = import.meta.env.VITE_PASSWORD_RESET_ENABLED !== 'false'
const passwordResetExpiryMinutes = Number(import.meta.env.VITE_PASSWORD_RESET_EXPIRE_MINUTES || 30)
const emailPreviewUrl = import.meta.env.VITE_EMAIL_PREVIEW_URL || ''

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [resetToken, setResetToken] = useState(() => new URLSearchParams(window.location.search).get('reset_token') || '')
  const [authMode, setAuthMode] = useState<AuthMode>(() => new URLSearchParams(window.location.search).has('reset_token') ? 'reset' : 'login')
  const [requests, setRequests] = useState<RequestRecord[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [departmentMetrics, setDepartmentMetrics] = useState<DepartmentPerformance[]>([])
  const [workflowMetrics, setWorkflowMetrics] = useState<WorkflowMetrics | null>(null)
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditRecord[]>([])
  const [feedback, setFeedback] = useState<FeedbackRecord | null>(null)
  const [events, setEvents] = useState<EventRecord[]>([])
  const [comments, setComments] = useState<CommentRecord[]>([])
  const [attachments, setAttachments] = useState<AttachmentRecord[]>([])
  const [prediction, setPrediction] = useState<PredictionRecord | null>(null)
  const [duplicates, setDuplicates] = useState<DuplicateRecord[]>([])
  const [estimate, setEstimate] = useState<ResolutionEstimate | null>(null)
  const [selected, setSelected] = useState<RequestRecord | null>(null)
  const [tab, setTab] = useState<'requests' | 'new' | 'team'>('requests')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [apiState, setApiState] = useState<'checking' | 'online' | 'offline'>('checking')

  const refresh = useCallback(async () => {
    if (!readToken()) return
    try {
      const [me, rows, cats, depts, notes] = await Promise.all([
        api<User>('/auth/me'), api<RequestRecord[]>('/requests?limit=250'), api<Category[]>('/categories'),
        api<Department[]>('/departments'), api<Notification[]>('/notifications'),
      ])
      setUser(me); setRequests(rows); setCategories(cats); setDepartments(depts); setNotifications(notes)
      if (me.role === 'ADMIN' || me.role === 'SUPER_ADMIN') {
        const [institution, performance, accounts, audit] = await Promise.all([api<AnalyticsSummary>('/analytics/summary'), api<DepartmentPerformance[]>('/analytics/departments'), api<AdminUser[]>('/admin/users?limit=100'), api<AuditRecord[]>('/admin/audit-logs?limit=50')])
        setSummary(institution); setDepartmentMetrics(performance); setAdminUsers(accounts); setAuditLogs(audit)
        setWorkflowMetrics(null)
      } else if (me.role === 'STAFF') {
        setSummary(null); setDepartmentMetrics([]); setWorkflowMetrics(await api<WorkflowMetrics>('/analytics/workflow')); setAdminUsers([]); setAuditLogs([])
      } else { setSummary(null); setDepartmentMetrics([]); setWorkflowMetrics(null); setAdminUsers([]); setAuditLogs([]) }
      setApiState('online')
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        saveToken(null); setUser(null)
      }
      setApiState('offline')
      setError(caught instanceof Error ? caught.message : 'Could not connect to CAMPUSINTEL')
    }
  }, [])

  useEffect(() => {
    const queryResetToken = new URLSearchParams(window.location.search).get('reset_token')
    if (queryResetToken) {
      saveToken(null)
      setUser(null)
      setResetToken(queryResetToken)
      setAuthMode('reset')
    }
    if (!readToken()) {
      fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/readyz`).then((response) => setApiState(response.ok ? 'online' : 'offline')).catch(() => setApiState('offline'))
      return
    }
    void refresh()
  }, [refresh])

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setNotice(''); setBusy(true)
    const data = new FormData(event.currentTarget)
    try {
      if (authMode === 'forgot') {
        await api('/auth/password-reset/request', { method: 'POST', body: JSON.stringify({ email: data.get('email') }) })
        setNotice('If an active account matches that email, reset instructions will arrive shortly. Check your inbox, or the local mail inbox listed in the service setup.')
        return
      }
      if (authMode === 'reset') {
        const newPassword = String(data.get('new_password') || '')
        if (newPassword !== String(data.get('confirm_password') || '')) throw new Error('The passwords do not match.')
        await api('/auth/password-reset/confirm', { method: 'POST', body: JSON.stringify({ token: resetToken, new_password: newPassword }) })
        saveToken(null); setResetToken(''); setUser(null); setAuthMode('login')
        window.history.replaceState({}, document.title, window.location.pathname)
        setNotice('Password reset successfully. Sign in with your new password.')
        return
      }
      const body: Record<string, string | null> = { email: String(data.get('email')), password: String(data.get('password')) }
      if (authMode === 'register') {
        body.full_name = String(data.get('full_name'))
        body.student_identifier = String(data.get('student_identifier') ?? '').trim() || null
      }
      const result = await api<AuthResult>(authMode === 'register' ? '/auth/register' : '/auth/login', { method: 'POST', body: JSON.stringify(body) })
      saveToken(result.access_token); setUser(result.user); setNotice('Welcome to CAMPUSINTEL.'); await refresh()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Sign in failed') }
    finally { setBusy(false) }
  }

  function logout() { saveToken(null); setUser(null); setSelected(null); setRequests([]); setTab('requests'); setError('') }

  async function submitRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setNotice(''); setBusy(true)
    const form = event.currentTarget
    const data = new FormData(form)
    try {
      const request = await api<RequestRecord>('/requests', { method: 'POST', body: JSON.stringify({ subject: data.get('subject'), description: data.get('description'), category_id: data.get('category_id') || null }) })
      const file = data.get('attachment')
      if (file instanceof File && file.size > 0) {
        const upload = new FormData(); upload.append('file', file)
        await api(`/requests/${request.id}/attachments`, { method: 'POST', body: upload })
      }
      form.reset(); setNotice(`Request ${request.ticket_number} submitted.`); setTab('requests'); await refresh()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Request could not be submitted') }
    finally { setBusy(false) }
  }

  async function openRequest(row: RequestRecord) {
    setSelected(row); setError('')
    try {
      const [history, messages, predictions, candidates, files] = await Promise.all([
        api<EventRecord[]>(`/requests/${row.id}/events`), api<CommentRecord[]>(`/requests/${row.id}/comments`),
        api<PredictionRecord[]>(`/requests/${row.id}/predictions`), api<{ candidates: DuplicateRecord[] }>(`/ml/requests/${row.id}/duplicates`),
        api<AttachmentRecord[]>(`/requests/${row.id}/attachments`),
      ])
      setEvents(history); setComments(messages); setPrediction(predictions[0] ?? null); setDuplicates(candidates.candidates); setAttachments(files); setEstimate(null)
      setFeedback(user?.role === 'STUDENT' && ['RESOLVED', 'CLOSED'].includes(row.current_status) ? await api<FeedbackRecord>(`/requests/${row.id}/feedback`) : null)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Could not load request details') }
  }

  async function changeStatus(row: RequestRecord, target: string) {
    try {
      const updated = await api<RequestRecord>(`/requests/${row.id}/status`, { method: 'POST', body: JSON.stringify({ status: target }) })
      setNotice(`Request ${row.ticket_number} updated.`); await refresh(); await openRequest(updated)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Status update failed') }
  }

  async function assignRequest(event: FormEvent<HTMLFormElement>, row: RequestRecord) {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    try {
      const updated = await api<RequestRecord>(`/requests/${row.id}/assign`, { method: 'POST', body: JSON.stringify({ department_id: data.get('department_id'), staff_id: data.get('staff_id') || null, reason: data.get('reason') || null }) })
      setNotice(`Request ${row.ticket_number} assigned.`); await refresh(); await openRequest(updated)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Assignment failed') }
  }

  async function postComment(event: FormEvent<HTMLFormElement>, row: RequestRecord) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form)
    try {
      await api(`/requests/${row.id}/comments`, { method: 'POST', body: JSON.stringify({ message: data.get('message'), visibility: data.get('visibility') || 'STUDENT_VISIBLE' }) })
      form.reset(); await openRequest(row)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Comment failed') }
  }

  async function readNotification(id: string) {
    await api(`/notifications/${id}/read`, { method: 'POST' }); await refresh()
  }

  async function getResolutionEstimate(row: RequestRecord) {
    try { setEstimate(await api<ResolutionEstimate>(`/ml/requests/${row.id}/resolution-estimate`)) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Estimate unavailable') }
  }

  async function createStaff(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form)
    try {
      const role = String(data.get('role'))
      await api('/auth/staff', { method: 'POST', body: JSON.stringify({ full_name: data.get('full_name'), email: data.get('email'), password: data.get('password'), role, department_id: role === 'STAFF' ? data.get('department_id') || null : null, student_identifier: role === 'STUDENT' ? String(data.get('student_identifier') ?? '').trim() || null : null }) })
      form.reset(); setNotice('Account created. Share the temporary password securely with the student.'); await refresh()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Account creation failed') }
  }

  async function submitFeedback(event: FormEvent<HTMLFormElement>, row: RequestRecord) {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    try {
      await api(`/requests/${row.id}/feedback`, { method: 'POST', body: JSON.stringify({ rating: Number(data.get('rating')), feedback_text: data.get('feedback_text') || null }) })
      setFeedback({ saved: true, rating: Number(data.get('rating')) }); setNotice('Thank you. Your feedback was recorded.')
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Feedback could not be saved') }
  }

  async function toggleUserActive(target: AdminUser) {
    try {
      await api(`/admin/users/${target.id}/active?active=${!target.is_active}`, { method: 'PATCH' }); await refresh()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Account update failed') }
  }

  async function downloadReport() {
    try {
      const token = readToken()
      const response = await fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/analytics/export/requests.csv`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!response.ok) throw new Error('Report could not be exported')
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = 'campusintel-requests.csv'; link.click(); URL.revokeObjectURL(url)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Report export failed') }
  }

  async function downloadAttachment(row: RequestRecord, attachment: AttachmentRecord) {
    try {
      const token = readToken()
      const response = await fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/requests/${row.id}/attachments/${attachment.id}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!response.ok) throw new Error('Attachment could not be downloaded')
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = attachment.original_filename; link.click(); URL.revokeObjectURL(url)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Attachment download failed') }
  }

  if (!user) return <AuthScreen mode={authMode} setMode={setAuthMode} submit={submitAuth} busy={busy} error={error} notice={notice} apiState={apiState} resetToken={resetToken} />

  const isStudent = user.role === 'STUDENT'
  const canManage = user.role === 'ADMIN' || user.role === 'SUPER_ADMIN'
  return (
    <main className="app-shell">
      <header className="topbar app-topbar">
        <a className="brand" href="#home"><span className="brand-mark">C</span><span>CAMPUS<span className="brand-strong">INTEL</span></span></a>
        <div className="app-top-actions"><span className={`connection connection-${apiState}`}><i className="connection-dot" />{apiState === 'online' ? 'Connected' : 'Reconnecting'}</span><span className="user-chip">{user.full_name.split(' ')[0]} <b>{user.role.replace('_', ' ')}</b></span><button className="button button-quiet" onClick={() => void refresh()}>Refresh</button><button className="button button-quiet" onClick={logout}>Sign out</button></div>
      </header>

      <section className="workspace-head">
        <div><div className="eyebrow"><span /> {institutionName.toUpperCase()} · SERVICE DESK</div><h1>{isStudent ? 'Your requests, in view.' : canManage ? 'Institution overview.' : 'Department workspace.'}</h1><p>{isStudent ? 'Submit a request and follow each step to resolution.' : 'Review assigned work, update progress, and keep a clear history.'}</p></div>
        <div className="workspace-count"><strong>{(canManage && summary ? summary.total_requests : requests.length).toString().padStart(2, '0')}</strong><span>{canManage ? 'INSTITUTION REQUESTS' : isStudent ? 'RECENT REQUESTS' : 'VISIBLE REQUESTS'}</span></div>
      </section>
      {user.role === 'STAFF' && workflowMetrics && <section className="staff-stats"><div><b>{workflowMetrics.open_requests}</b><span>OPEN IN YOUR SCOPE</span></div><div><b>{workflowMetrics.resolved_requests}</b><span>RESOLVED</span></div><div><b>{workflowMetrics.average_resolution_hours === null ? '—' : `${workflowMetrics.average_resolution_hours.toFixed(1)}h`}</b><span>AVERAGE RESOLUTION</span></div><div><b>{workflowMetrics.mean_inter_event_hours === null ? '—' : `${workflowMetrics.mean_inter_event_hours.toFixed(1)}h`}</b><span>MEAN EVENT GAP</span></div></section>}

      <nav className="workspace-nav" aria-label="Workspace">
        <button className={tab === 'requests' ? 'active' : ''} onClick={() => { setTab('requests'); setSelected(null) }}>{isStudent ? 'My requests' : 'Request queue'}</button>
        {isStudent && <button className={tab === 'new' ? 'active' : ''} onClick={() => setTab('new')}>New request</button>}
        {canManage && <button className={tab === 'team' ? 'active' : ''} onClick={() => setTab('team')}>Team & notifications</button>}
      </nav>

      {canManage && <section className="admin-transparency" aria-label="Operational and policy status"><div><span>SERVICE READINESS</span><b>{apiState === 'online' ? 'API and database available' : 'Connection needs attention'}</b><small>Status reflects a successful authenticated data refresh.</small></div><div><span>DEMO MODE</span><b>{demoMode ? 'Enabled' : 'Disabled'}</b><small>{demoMode ? 'Model examples are synthetic. Review every suggestion.' : 'Model suggestions remain advisory and require staff review.'}</small></div><div><span>INSTITUTION POLICY</span><b>{privacyUrl ? 'Privacy information linked' : 'Privacy link not configured'}</b><small>{supportEmail ? `Support contact: ${supportEmail}` : 'Institution support contact is not configured.'}</small></div></section>}

      {error && <div className="alert alert-error" role="alert">{error}</div>}{notice && <div className="alert alert-success" role="status">{notice}</div>}
      {notifications.some((item) => !item.is_read) && <section className="unread-strip"><b>New updates</b>{notifications.filter((item) => !item.is_read).slice(0, 3).map((item) => <span key={item.id}>{item.message} <button onClick={() => void readNotification(item.id)}>Mark read</button></span>)}</section>}

      {tab === 'new' && isStudent && <section className="panel form-panel"><div className="panel-title"><div><span className="eyebrow muted">REQUEST DETAILS</span><h2>What can we help with?</h2></div><span className="phase-tag"><i /> VISIBLE TO YOU AND AUTHORIZED SERVICE STAFF</span></div>
        <form className="form-grid" onSubmit={submitRequest}><label>Subject<input name="subject" required minLength={5} maxLength={240} placeholder="A short summary of the issue" /></label><label>Approximate category<select name="category_id"><option value="">Not sure yet</option>{categories.map((item) => <option value={item.id} key={item.id}>{item.category_name}</option>)}</select></label><label className="full">Description<textarea name="description" required minLength={15} maxLength={10000} rows={5} placeholder="Share the details that will help the team investigate." /></label><label className="full">Supporting document <span className="field-hint">PDF, PNG or JPEG up to 5 MB</span><input type="file" name="attachment" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" /></label><div className="full form-actions"><button className="button button-primary" disabled={busy}>{busy ? 'Submitting…' : 'Submit request'}</button></div></form>
      </section>}

      {tab === 'requests' && <div className={`content-grid ${selected ? 'has-detail' : ''}`}>
        <section className="panel request-list"><div className="panel-title"><div><span className="eyebrow muted">LIVE RECORDS</span><h2>{isStudent ? 'Your request history' : 'Request queue'}</h2></div><span className="list-count">{requests.length} total</span></div>
          {requests.length === 0 ? <div className="empty-state"><div className="empty-mark">○</div><h3>No requests to show</h3><p>{isStudent ? 'When you submit a request, its progress will appear here.' : 'Requests routed to your account or department will appear here.'}</p>{isStudent && <button className="button button-primary" onClick={() => setTab('new')}>Submit a request</button>}</div> : <div className="request-rows">{requests.map((row) => <button className={`request-row ${selected?.id === row.id ? 'selected' : ''}`} key={row.id} onClick={() => void openRequest(row)}><span className="row-top"><span className="ticket">{row.ticket_number}</span><Status status={row.current_status} /></span><strong>{row.subject}</strong><span className="row-bottom">{new Date(row.created_at).toLocaleDateString()} <span>{row.ml_predicted_category ? `Suggested: ${row.ml_predicted_category} · model suggestion` : 'Category pending review'}</span></span></button>)}</div>}
        </section>
        {selected && <section className="panel detail-panel"><div className="panel-title detail-title"><div><span className="eyebrow muted">{selected.ticket_number}</span><h2>{selected.subject}</h2></div><button className="icon-button" aria-label="Close request detail" onClick={() => setSelected(null)}>×</button></div><Status status={selected.current_status} /><p className="detail-description">{selected.description}</p>{selected.ml_predicted_category && <div className="suggestion"><span>MODEL SUGGESTION · NOT A VERIFIED CATEGORY</span><b>{selected.ml_predicted_category}</b>{selected.ml_confidence !== null && <small>{Math.round(selected.ml_confidence * 100)}% confidence</small>}{prediction && <small>Training data: {prediction.explanation.dataset_type ?? 'provenance unavailable'}</small>}{prediction?.explanation.learned_terms && <small>Learned terms: {prediction.explanation.learned_terms.join(', ')}</small>}</div>}
          <h3 className="subhead">Request history</h3><div className="timeline">{events.map((event, i) => <div className="timeline-item" key={`${event.event_type}-${i}`}><i /><div><b>{event.new_status?.replaceAll('_', ' ') || event.event_type.replaceAll('_', ' ')}</b><small>{event.description} · {new Date(event.event_timestamp).toLocaleString()}</small></div></div>)}</div>
          {attachments.length > 0 && <><h3 className="subhead">Supporting documents</h3><div className="attachment-list">{attachments.map((attachment) => <button className="attachment-link" key={attachment.id} onClick={() => void downloadAttachment(selected, attachment)}><span>▤ {attachment.original_filename}</span><small>{(attachment.file_size / 1024).toFixed(0)} KB · private download</small></button>)}</div></>}
          <h3 className="subhead">Conversation</h3><div className="comment-list">{comments.map((comment) => <article className="comment" key={comment.id}><div>{comment.message}</div><small>{comment.visibility === 'INTERNAL' ? 'Internal note' : 'Visible to student'} · {new Date(comment.created_at).toLocaleString()}</small></article>)}{comments.length === 0 && <p className="muted-copy">No comments yet.</p>}</div>
          <div className="intel-block"><div className="intel-heading"><h3 className="subhead">Related requests</h3><small>Similarity suggestions · review manually</small></div>{duplicates.length ? duplicates.map((candidate) => <div className="duplicate-row" key={candidate.request_id}><span><b>{candidate.ticket_number}</b> {candidate.subject}</span><small>{Math.round(candidate.similarity * 100)}% similar</small></div>) : <p className="muted-copy">No close matches found.</p>}</div>
          <div className="intel-block"><div className="intel-heading"><h3 className="subhead">Resolution estimate</h3><button className="button button-outline button-small" onClick={() => void getResolutionEstimate(selected)}>Estimate</button></div>{estimate && <p className="estimate-copy">{estimate.available ? `${estimate.estimate_hours} historical median hours, based on ${estimate.sample_size} resolved requests.` : estimate.note}</p>}</div>
          {(!isStudent || selected.current_status !== 'CLOSED') && <form className="comment-form" onSubmit={(event) => void postComment(event, selected)}><textarea name="message" required rows={2} placeholder="Add a request update…" /><div className="comment-tools">{!isStudent && <select name="visibility"><option value="STUDENT_VISIBLE">Student-visible reply</option><option value="INTERNAL">Internal staff note</option></select>}<button className="button button-primary button-small">Post update</button></div></form>}
          {!isStudent && <div className="status-actions">{nextStatuses(selected.current_status, canManage).map((next) => <button className="button button-outline" key={next} onClick={() => void changeStatus(selected, next)}>{next.replaceAll('_', ' ')}</button>)}</div>}
          {canManage && <form className="assignment-form" onSubmit={(event) => void assignRequest(event, selected)}><b>Assign or route</b><select name="department_id" required defaultValue={selected.assigned_department_id ?? ''}><option value="" disabled>Choose department</option>{departments.map((department) => <option key={department.id} value={department.id}>{department.department_name}</option>)}</select><input name="reason" placeholder="Assignment note (optional)" /><button className="button button-outline button-small">Assign to department</button></form>}
          {isStudent && ['RESOLVED', 'CLOSED'].includes(selected.current_status) && (feedback?.saved ? <p className="feedback-saved">Feedback recorded. Thank you.</p> : <form className="feedback-form" onSubmit={(event) => void submitFeedback(event, selected)}><h3 className="subhead">How was the support?</h3><select name="rating" required defaultValue="5"><option value="5">5 — Excellent</option><option value="4">4 — Good</option><option value="3">3 — Okay</option><option value="2">2 — Poor</option><option value="1">1 — Very poor</option></select><textarea name="feedback_text" rows={2} placeholder="Optional feedback"/><button className="button button-outline button-small">Send feedback</button></form>)}
          {isStudent && ['RESOLVED', 'CLOSED'].includes(selected.current_status) && <button className="button button-outline" onClick={() => void changeStatus(selected, 'REOPENED')}>Reopen request</button>}
        </section>}
      </div>}

      {tab === 'team' && canManage && <div className="content-grid team-grid"><section className="panel"><div className="panel-title"><div><span className="eyebrow muted">SYSTEM MESSAGES</span><h2>Recent notifications</h2></div><button className="button button-outline button-small" onClick={() => void downloadReport()}>Export authorized CSV</button></div>{notifications.length === 0 ? <p className="muted-copy">No notifications yet. Request activity will appear here.</p> : notifications.map((item) => <article className={`notification ${item.is_read ? '' : 'unread'}`} key={item.id}><div><b>{item.title}</b><p>{item.message}</p></div>{!item.is_read && <button className="button button-quiet" onClick={() => void readNotification(item.id)}>Mark read</button>}</article>)}<div className="panel-title subpanel-title"><div><span className="eyebrow muted">ACCOUNT ADMINISTRATION</span><h2>Create a student or staff account</h2></div></div><form className="form-grid compact-form" onSubmit={(event) => void createStaff(event)}><label>Full name<input name="full_name" minLength={2} required /></label><label>Email<input name="email" type="email" required /></label><PasswordField label="Temporary password" name="password" minLength={10} autoComplete="new-password" /><label>Role<select name="role"><option value="STUDENT">Student</option><option value="STAFF">Department staff</option>{user.role === 'SUPER_ADMIN' && <><option value="ADMIN">Administrator</option><option value="SUPER_ADMIN">Super administrator</option></>}</select></label><label>Student identifier <span className="field-hint">Optional for student accounts</span><input name="student_identifier" maxLength={80} /></label><label className="full">Department<select name="department_id"><option value="">No department</option>{departments.map((department) => <option value={department.id} key={department.id}>{department.department_name}</option>)}</select></label><div className="full form-actions"><button className="button button-primary">Create account</button></div></form><h3 className="subhead">Accounts</h3><div className="account-list">{adminUsers.map((account) => <div className="account-row" key={account.id}><span><b>{account.full_name}</b><small>{account.email} · {account.role}</small></span><span>{account.is_active ? 'Active' : 'Inactive'}{user.role === 'SUPER_ADMIN' && account.id !== user.id && <button className="button button-quiet" onClick={() => void toggleUserActive(account)}>{account.is_active ? 'Deactivate' : 'Activate'}</button>}</span></div>)}</div></section><section className="panel"><div className="panel-title"><div><span className="eyebrow muted">LIVE DATABASE TOTALS</span><h2>Current workflow</h2></div></div><div className="status-summary">{['SUBMITTED', 'CLASSIFIED', 'ASSIGNED', 'IN_PROGRESS', 'WAITING_FOR_STUDENT', 'ESCALATED', 'RESOLVED', 'CLOSED', 'REOPENED'].map((status) => <div key={status}><span>{status.replaceAll('_', ' ')}</span><b>{summary?.by_status[status] ?? 0}</b></div>)}</div><p className="muted-copy">{summary?.resolved_count ?? 0} resolved · Average {summary?.average_resolution_hours === null || summary?.average_resolution_hours === undefined ? 'not available' : `${summary.average_resolution_hours.toFixed(1)} hours`} from resolved records.</p><h3 className="subhead">Department performance</h3>{departmentMetrics.map((department) => <div className="department-metric" key={department.department_id}><b>{department.department_name}</b><span>{department.open_requests} open · {department.resolved_requests} resolved</span><small>{department.average_resolution_hours === null ? 'No resolved cases yet' : `${department.average_resolution_hours.toFixed(1)} average hours to resolution`}</small></div>)}<h3 className="subhead">Recent audit activity</h3><div className="audit-list">{auditLogs.map((entry) => <div key={entry.id}><b>{entry.action}</b><small>{entry.resource_type} · {new Date(entry.created_at).toLocaleString()}</small></div>)}</div></section></div>}

      <footer className="footer"><span>© 2026 CAMPUSINTEL</span><span>Student services, understood.</span><span className="footer-status"><i /> ROLE-BASED ACCESS</span></footer>
    </main>
  )
}

function nextStatuses(current: string, canManage: boolean): string[] {
  const map: Record<string, string[]> = { SUBMITTED: ['IN_PROGRESS', 'ESCALATED'], CLASSIFIED: ['IN_PROGRESS', 'ESCALATED'], ASSIGNED: ['IN_PROGRESS', 'WAITING_FOR_STUDENT', 'ESCALATED', 'RESOLVED'], IN_PROGRESS: ['WAITING_FOR_STUDENT', 'ESCALATED', 'RESOLVED'], WAITING_FOR_STUDENT: ['IN_PROGRESS', 'ESCALATED', 'RESOLVED'], ESCALATED: ['ASSIGNED', 'IN_PROGRESS', 'RESOLVED'], REOPENED: ['IN_PROGRESS', 'ESCALATED'], RESOLVED: ['CLOSED', 'IN_PROGRESS'] }
  return (map[current] ?? []).filter((next) => canManage || next !== 'CLOSED')
}

function Status({ status }: { status: string }) { return <span className={`status-pill status-${status.toLowerCase()}`}><i />{status.replaceAll('_', ' ')}</span> }

function PasswordField({ label, name, minLength, autoComplete }: { label: string; name: string; minLength: number; autoComplete: string }) {
  const [visible, setVisible] = useState(false)
  return <label className="password-field">{label}<span className="password-control"><input name={name} type={visible ? 'text' : 'password'} required minLength={minLength} autoComplete={autoComplete} /><button type="button" className="password-toggle" aria-label={visible ? 'Hide password' : 'Show password'} aria-pressed={visible} onClick={() => setVisible((value) => !value)}>{visible ? 'Hide' : 'Show'}</button></span></label>
}

function AuthScreen({ mode, setMode, submit, busy, error, notice, apiState, resetToken }: { mode: AuthMode; setMode: (mode: AuthMode) => void; submit: (event: FormEvent<HTMLFormElement>) => void; busy: boolean; error: string; notice: string; apiState: string; resetToken: string }) {
  const heading = mode === 'login' ? 'Welcome back' : mode === 'register' ? 'Create your account' : mode === 'forgot' ? 'Reset your password' : 'Choose a new password'
  const description = mode === 'login' ? 'Sign in to view and manage your requests.' : mode === 'register' ? 'Student registration is open for this installation.' : mode === 'forgot' ? 'Enter your account email and we will send a one-time reset link if the account is active.' : 'Choose a new password for your account.'
  const action = mode === 'login' ? 'Sign in' : mode === 'register' ? 'Create student account' : mode === 'forgot' ? 'Send reset link' : 'Save new password'
  return (
    <main className="auth-shell">
      <header className="topbar">
        <a className="brand" href="#home"><span className="brand-mark">C</span><span>CAMPUS<span className="brand-strong">INTEL</span></span></a>
        <span className="institution-name">{institutionName}</span>
        <span className={"connection connection-" + apiState}><i className="connection-dot" />{apiState === 'online' ? 'Database ready' : apiState === 'offline' ? 'Service unavailable' : 'Checking service'}</span>
      </header>
      <div className="auth-layout">
        <section className="auth-intro">
          <div className="eyebrow"><span /> STUDENT SERVICE INTELLIGENCE</div>
          <h1>Campus services,<br />with a clear next step.</h1>
          <p>Submit requests, follow progress, and stay connected with the team working on your issue.</p>
          <div className="auth-orbit" aria-hidden="true"><div className="orbit orbit-outer"/><div className="orbit orbit-inner"/><div className="art-core">C</div><i className="orbit-point point-one"/><i className="orbit-point point-two"/></div>
        </section>
        <section className="auth-card">
          <div className="eyebrow muted">STUDENT ACCOUNT ACCESS</div>
          <h2>{heading}</h2>
          <p>{description}</p>
          {error && <div className="alert alert-error" role="alert">{error}</div>}
          {notice && <div className="alert alert-success" role="status">{notice}</div>}
          <form className="auth-form" onSubmit={submit}>
            {mode === 'register' && <>
              <label>Full name<input name="full_name" required minLength={2} maxLength={160} autoComplete="name" /></label>
              <label>Student identifier <span className="field-hint">Optional</span><input name="student_identifier" maxLength={80} /></label>
            </>}
            {mode !== 'reset' && <label>Email address<input name="email" type="email" required autoComplete="email" /></label>}
            {mode === 'login' && <PasswordField label="Password" name="password" minLength={1} autoComplete="current-password" />}
            {mode === 'register' && <PasswordField label="Password" name="password" minLength={10} autoComplete="new-password" />}
            {mode === 'forgot' && <small className="auth-footnote">For privacy, this page gives the same confirmation whether or not an account exists.</small>}
            {mode === 'reset' && <>
              <input type="hidden" name="reset_token" value={resetToken} />
              <PasswordField label="New password" name="new_password" minLength={10} autoComplete="new-password" />
              <PasswordField label="Confirm new password" name="confirm_password" minLength={10} autoComplete="new-password" />
              <small className="auth-footnote">This reset link is single-use and expires in {passwordResetExpiryMinutes} minutes.</small>
            </>}
            <button className="button button-primary auth-submit" disabled={busy}>{busy ? 'Please wait…' : action}</button>
          </form>
          {mode === 'login' && <div className="auth-secondary-actions">
            <p className="auth-switch">New to CAMPUSINTEL? <button onClick={() => setMode('register')}>Create an account</button></p>
            {passwordResetEnabled ? <button className="text-link" onClick={() => setMode('forgot')}>Forgot password?</button> : <small className="auth-footnote">Password reset email is not configured. Contact your institution administrator.</small>}
          </div>}
          {mode === 'register' && <p className="auth-switch">Already have an account? <button onClick={() => setMode('login')}>Sign in</button></p>}
          {(mode === 'forgot' || mode === 'reset') && <p className="auth-switch"><button onClick={() => setMode('login')}>Back to sign in</button></p>}
          <small className="auth-footnote">Students can self-register or be added by an institution administrator.</small>
        </section>
      </div>
      <TrustCenter apiState={apiState} />
      <footer className="footer"><span>© 2026 CAMPUSINTEL</span><span>Student services, understood.</span><span className="footer-status"><i/>CAMPUS SERVICE PORTAL</span></footer>
    </main>
  )
}


function TrustCenter({ apiState }: { apiState: string }) {
  const readiness = apiState === 'online' ? 'Ready · API and database connected' : apiState === 'offline' ? 'Unavailable · check service status' : 'Checking live readiness…'
  return (
    <section className="trust-center" aria-labelledby="trust-heading">
      <div className="trust-intro">
        <span className="eyebrow">SERVICE, ACCESS & ACCOUNTABILITY</span>
        <h2 id="trust-heading">{institutionName}</h2>
        <p>Review how this service handles requests before creating an account.</p>
      </div>
      <div className="trust-grid">
        <article className="trust-card">
          <span className={"trust-state " + apiState}><i />{readiness}</span>
          <h3>Live service status</h3>
          <p>The status above comes from a readiness check that verifies the API can reach its database. It is not an uptime guarantee.</p>
          <a href={(import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/readyz'} target="_blank" rel="noreferrer">View readiness details</a>
        </article>
        <article className="trust-card">
          <span className="trust-index">01 · ACCESS</span>
          <h3>Who can see a request?</h3>
          <p>Students see their own requests. Staff see work in their authorized scope. Administrators can review institution-wide records and audit activity.</p>
        </article>
        <article className="trust-card">
          <span className="trust-index">02 · DATA</span>
          <h3>What information is stored?</h3>
          <p>Account details, request text, comments, event history, and any files you attach. Passwords are stored as hashes and cannot be retrieved as plain text.</p><p className={passwordResetEnabled ? "trust-configured" : "trust-unconfigured"}>{passwordResetEnabled ? "Password recovery uses expiring, single-use email links. Email verification and multi-factor authentication are not implemented." : "Password recovery email is not configured. Email verification and multi-factor authentication are not implemented."}</p>
          {privacyUrl ? <a href={privacyUrl} target="_blank" rel="noreferrer">Read institution privacy information</a> : <p className="trust-unconfigured">Institution privacy policy link has not been configured.</p>}
        </article>
        <article className="trust-card">
          <span className="trust-index">03 · MODEL LIMITS</span>
          <h3>{demoMode ? 'Demonstration suggestions' : 'Advisory suggestions'}</h3>
          <p>{demoMode ? 'This installation uses synthetic examples. Category and duplicate suggestions are for demonstration and must be reviewed by staff.' : 'Automated category, duplicate, and time suggestions are advisory. Staff remain responsible for review and decisions.'}</p>
        </article>
        <article className="trust-card trust-contact">
          <span className="trust-index">04 · HELP</span>
          <h3>Need assistance?</h3>
          {supportEmail ? <p>Contact your institution service desk at <a href={'mailto:' + supportEmail}>{supportEmail}</a>.</p> : <p className="trust-unconfigured">The institution support contact has not been configured. Contact your campus service administrator.</p>}
          <p>Request response times and data retention depend on your institution’s published policies.</p>{emailPreviewUrl && <p>Local development email inbox: <a href={emailPreviewUrl} target="_blank" rel="noreferrer">open inbox</a>.</p>}
        </article>
      </div>
    </section>
  )
}

export default App
