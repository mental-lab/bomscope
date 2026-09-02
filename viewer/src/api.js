// API wrapper: attaches the bearer token and routes to /login on 401.
import { reactive } from 'vue'

export const auth = reactive({
  token: localStorage.getItem('bomscope_token') || '',
  role: localStorage.getItem('bomscope_role') || '',
})

export function setToken(token, role) {
  auth.token = token
  auth.role = role
  localStorage.setItem('bomscope_token', token)
  localStorage.setItem('bomscope_role', role)
}

export function clearToken() {
  auth.token = ''
  auth.role = ''
  localStorage.removeItem('bomscope_token')
  localStorage.removeItem('bomscope_role')
}

export async function apiFetch(path, opts = {}) {
  const headers = { ...(opts.headers || {}) }
  if (auth.token) headers['Authorization'] = 'Bearer ' + auth.token
  const res = await fetch(path, { ...opts, headers })
  if (res.status === 401 && !path.endsWith('/api/auth/check')) {
    clearToken()
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
  }
  return res
}
