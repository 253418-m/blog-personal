import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'

const admin = { user_id: 'fixture-user', username: 'editor', is_active: true }
const document = (title, status, updated_at = '2026-10-26T12:00:00Z') => ({
  document_id: title, title, content_type: 'POST', status, updated_at,
})
const template = (name) => ({
  template_id: name, name, target_type: 'POST', is_default: true,
  allow_published_edit: false, metadata_contract: [{ field_key: 'category' }],
})

function response(data, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => data }
}

function mockApi({ loginStatus = 200, meStatus = 200, documents = [], templates = [], documentsStatus = 200 } = {}) {
  return vi.fn(async (url) => {
    if (url.endsWith('/auth/login')) return response(loginStatus === 200 ? { access_token: 'fixture-token' } : {}, loginStatus)
    if (url.endsWith('/auth/me')) return response(admin, meStatus)
    if (url.endsWith('/documents')) return response({ items: documents }, documentsStatus)
    if (url.endsWith('/templates')) return response({ items: templates })
    throw new Error('Ruta inesperada en test')
  })
}

function open(path) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

beforeEach(() => {
  sessionStorage.clear()
  vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')
  window.history.pushState({}, '', '/')
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe('Acceso y sesión', () => {
  it('muestra el formulario y no envía campos vacíos', async () => {
    const fetchMock = mockApi()
    vi.stubGlobal('fetch', fetchMock)
    open('/login')
    expect(screen.getByLabelText('Usuario')).toBeInTheDocument()
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: 'Iniciar sesión' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Escribe usuario y contraseña.')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('guarda el JWT de prueba, valida /auth/me y abre Dashboard', async () => {
    const fetchMock = mockApi()
    vi.stubGlobal('fetch', fetchMock)
    open('/login')
    await userEvent.type(screen.getByLabelText('Usuario'), 'editor')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'contraseña-ficticia')
    await userEvent.click(screen.getByRole('button', { name: 'Iniciar sesión' }))
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(sessionStorage.getItem('cms_access_token')).toBe('fixture-token')
    expect(window.location.pathname).toBe('/dashboard')
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/auth/me'))).toBe(true)
    expect(screen.queryByLabelText('Contraseña')).not.toBeInTheDocument()
  })

  it('presenta el mensaje correcto para 401 sin guardar token', async () => {
    vi.stubGlobal('fetch', mockApi({ loginStatus: 401 }))
    open('/login')
    await userEvent.type(screen.getByLabelText('Usuario'), 'editor')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'incorrecta')
    await userEvent.click(screen.getByRole('button', { name: 'Iniciar sesión' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Usuario o contraseña incorrectos.')
    expect(sessionStorage.getItem('cms_access_token')).toBeNull()
  })

  it('distingue una API inaccesible de credenciales incorrectas', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('fallo de red ficticio') }))
    open('/login')
    await userEvent.type(screen.getByLabelText('Usuario'), 'editor')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'clave-ficticia')
    await userEvent.click(screen.getByRole('button', { name: 'Iniciar sesión' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No fue posible conectar con el CMS.')
    expect(sessionStorage.getItem('cms_access_token')).toBeNull()
  })

  it('redirige una ruta protegida sin token a Login', async () => {
    const fetchMock = mockApi()
    vi.stubGlobal('fetch', fetchMock)
    open('/dashboard')
    expect(await screen.findByRole('heading', { name: 'Acceso administrativo' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('valida el token existente antes de mostrar datos protegidos', async () => {
    sessionStorage.setItem('cms_access_token', 'fixture-token')
    let completeMe
    const fetchMock = mockApi()
    vi.stubGlobal('fetch', vi.fn((url, options) => {
      if (url.endsWith('/auth/me')) return new Promise((resolve) => { completeMe = resolve })
      return fetchMock(url, options)
    }))
    open('/dashboard')
    expect(screen.getByRole('status')).toHaveTextContent('Validando sesión')
    expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument()
    completeMe(response(admin))
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    const meCall = fetch.mock.calls.find(([url]) => url.endsWith('/auth/me'))
    expect(meCall[1].headers.Authorization).toBe('Bearer fixture-token')
  })

  it('elimina un token rechazado por /auth/me', async () => {
    sessionStorage.setItem('cms_access_token', 'fixture-token')
    vi.stubGlobal('fetch', mockApi({ meStatus: 401 }))
    open('/dashboard')
    expect(await screen.findByRole('heading', { name: 'Acceso administrativo' })).toBeInTheDocument()
    expect(sessionStorage.getItem('cms_access_token')).toBeNull()
    expect(window.location.pathname).toBe('/login')
  })

  it('no muestra datos si /auth/me está inaccesible y permite reintentar', async () => {
    sessionStorage.setItem('cms_access_token', 'fixture-token')
    const normal = mockApi()
    let attempts = 0
    vi.stubGlobal('fetch', vi.fn((url, options) => {
      if (url.endsWith('/auth/me') && attempts++ === 0) return Promise.reject(new Error('red ficticia'))
      return normal(url, options)
    }))
    open('/dashboard')
    expect(await screen.findByRole('alert')).toHaveTextContent('No fue posible validar la sesión')
    expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument()
    expect(sessionStorage.getItem('cms_access_token')).toBe('fixture-token')
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  it('expulsa al usuario cuando una petición protegida recibe 401', async () => {
    sessionStorage.setItem('cms_access_token', 'fixture-token')
    vi.stubGlobal('fetch', mockApi({ documentsStatus: 401 }))
    open('/dashboard')
    expect(await screen.findByRole('heading', { name: 'Acceso administrativo' })).toBeInTheDocument()
    expect(sessionStorage.getItem('cms_access_token')).toBeNull()
    expect(window.location.pathname).toBe('/login')
  })

  it('cerrar sesión borra token y vuelve a Login', async () => {
    sessionStorage.setItem('cms_access_token', 'fixture-token')
    vi.stubGlobal('fetch', mockApi())
    open('/dashboard')
    await screen.findByRole('heading', { name: 'Dashboard' })
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
    expect(sessionStorage.getItem('cms_access_token')).toBeNull()
    expect(window.location.pathname).toBe('/login')
    expect(screen.getByRole('heading', { name: 'Acceso administrativo' })).toBeInTheDocument()
    window.history.pushState({}, '', '/dashboard')
    cleanup()
    open('/dashboard')
    expect(await screen.findByRole('heading', { name: 'Acceso administrativo' })).toBeInTheDocument()
  })
})

describe('Vistas de solo lectura', () => {
  beforeEach(() => sessionStorage.setItem('cms_access_token', 'fixture-token'))

  it('calcula estados, Templates y limita los documentos recientes a cinco', async () => {
    const documents = [
      document('Borrador uno', 'BORRADOR'), document('Publicado uno', 'PUBLICADO'),
      document('Archivado uno', 'ARCHIVADO'), document('Borrador dos', 'BORRADOR'),
      document('Extra uno', 'PUBLICADO'), document('Extra dos', 'PUBLICADO'),
    ]
    vi.stubGlobal('fetch', mockApi({ documents, templates: [template('Post'), template('Landing')] }))
    open('/dashboard')
    await screen.findByRole('heading', { name: 'Dashboard' })
    const summary = screen.getByRole('region', { name: 'Resumen editorial' })
    expect(within(summary).getByText('Borradores').parentElement).toHaveTextContent('2')
    expect(within(summary).getByText('Publicados').parentElement).toHaveTextContent('3')
    expect(within(summary).getByText('Archivados').parentElement).toHaveTextContent('1')
    expect(within(summary).getByText('Plantillas').parentElement).toHaveTextContent('2')
    expect(screen.getAllByRole('listitem')).toHaveLength(5)
  })

  it('muestra Documents como texto, filtra estados y no inyecta HTML', async () => {
    vi.stubGlobal('fetch', mockApi({ documents: [
      document('<img src=x onerror=alert(1)>', 'BORRADOR'),
      document('Post publicado', 'PUBLICADO'),
    ] }))
    open('/contenido')
    expect(await screen.findByText('<img src=x onerror=alert(1)>')).toBeInTheDocument()
    expect(window.document.querySelector('img')).toBeNull()
    expect(screen.getByText('Post publicado')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Borradores' }))
    expect(screen.queryByText('Post publicado')).not.toBeInTheDocument()
  })

  it('muestra Templates y sus propiedades reales', async () => {
    vi.stubGlobal('fetch', mockApi({ templates: [template('Plantilla POST')] }))
    open('/plantillas')
    expect(await screen.findByText('Plantilla POST')).toBeInTheDocument()
    expect(screen.getByText('Artículos / Posts')).toBeInTheDocument()
    expect(screen.getByText('No permitida')).toBeInTheDocument()
  })
})
