import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiRequest, setUnauthorizedHandler } from '../api/http'

beforeEach(() => {
  sessionStorage.clear()
  vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000/')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe('Cliente HTTP', () => {
  it('adjunta Bearer, no envía Content-Type en GET y parsea JSON', async () => {
    sessionStorage.setItem('cms_access_token', 'fixture-token')
    const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ items: [] }) }))
    vi.stubGlobal('fetch', fetchMock)
    expect(await apiRequest('/api/v1/documents')).toEqual({ items: [] })
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/documents', {
      method: 'GET', headers: { Authorization: 'Bearer fixture-token' },
    })
  })

  it('soporta respuestas sin body y 401 limpia sesión', async () => {
    sessionStorage.setItem('cms_access_token', 'fixture-token')
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 204 })))
    expect(await apiRequest('/api/v1/documents/x', { method: 'DELETE' })).toBeNull()
    const handler = vi.fn()
    const unsubscribe = setUnauthorizedHandler(handler)
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 401 })))
    await expect(apiRequest('/api/v1/documents')).rejects.toMatchObject({ status: 401 })
    expect(sessionStorage.getItem('cms_access_token')).toBeNull()
    expect(handler).toHaveBeenCalledOnce()
    unsubscribe()
  })

  it('traduce un fallo de red sin exponer detalles internos', async () => {
    sessionStorage.setItem('cms_access_token', 'fixture-token')
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('ruta local sensible') }))
    await expect(apiRequest('/api/v1/documents')).rejects.toEqual(new ApiError(0))
  })

  it('un 401 tardío no borra una sesión nueva', async () => {
    sessionStorage.setItem('cms_access_token', 'token-anterior')
    let completeRequest
    vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve) => { completeRequest = resolve })))
    const handler = vi.fn()
    const unsubscribe = setUnauthorizedHandler(handler)
    const pending = apiRequest('/api/v1/documents')
    sessionStorage.setItem('cms_access_token', 'token-nuevo')
    completeRequest({ ok: false, status: 401 })
    await expect(pending).rejects.toMatchObject({ status: 401 })
    expect(sessionStorage.getItem('cms_access_token')).toBe('token-nuevo')
    expect(handler).not.toHaveBeenCalled()
    unsubscribe()
  })
})
