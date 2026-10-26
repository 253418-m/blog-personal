import { apiRequest } from './http'

export function loginRequest(username, password) {
  return apiRequest('/api/v1/auth/login', {
    method: 'POST',
    body: { username, password },
    authenticated: false,
  })
}

export function getCurrentAdmin() {
  return apiRequest('/api/v1/auth/me')
}
