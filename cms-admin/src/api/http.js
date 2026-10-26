import { clearToken, getToken } from './session'

let unauthorizedHandler = null

export class ApiError extends Error {
  constructor(status) {
    super('La solicitud al CMS no se completó.')
    this.name = 'ApiError'
    this.status = status
  }
}

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler
  return () => {
    if (unauthorizedHandler === handler) unauthorizedHandler = null
  }
}

export async function apiRequest(path, { method = 'GET', body, authenticated = true } = {}) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, '')
  if (!baseUrl) throw new ApiError(0)

  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let token
  if (authenticated) {
    token = getToken()
    if (!token) throw new ApiError(401)
    headers.Authorization = `Bearer ${token}`
  }

  let response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      method,
      headers,
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    })
  } catch {
    throw new ApiError(0)
  }

  if (response.status === 401 && authenticated && getToken() === token) {
    clearToken()
    unauthorizedHandler?.()
  }
  if (!response.ok) throw new ApiError(response.status)
  if (response.status === 204) return null
  try {
    return await response.json()
  } catch {
    throw new ApiError(0)
  }
}
