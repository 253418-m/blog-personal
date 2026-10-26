import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'

function template(overrides = {}) {
  return {
    template_id: 'post-template', name: 'Plantilla Post', target_type: 'POST', is_default: true,
    allow_published_edit: false,
    metadata_contract: [{ field_key: 'category', expected_type: 'STRING', is_required: true }],
    layout_structure: { sections: ['header', 'content'] }, created_at: '2026-10-26T12:00:00Z',
    ...overrides,
  }
}

function response(data, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => data }
}

function mockBackend({ templates = [template(), template({ template_id: 'landing-template', name: 'Plantilla Landing',
  target_type: 'LANDING', is_default: false, allow_published_edit: true })],
  createStatus = 201, updateStatus = 200, deleteStatus = 200, templatesStatus = 200 } = {}) {
  const rows = templates.map((item) => ({ ...item }))
  const fetchMock = vi.fn(async (rawUrl, init = {}) => {
    const url = new URL(rawUrl)
    const method = init.method || 'GET'
    if (url.pathname === '/api/v1/auth/me') return response({ username: 'editor', is_active: true })
    if (url.pathname === '/api/v1/templates') {
      if (method === 'GET') {
        if (templatesStatus !== 200) return response({}, templatesStatus)
        const target = url.searchParams.get('target_type')
        return response({ items: rows.filter((item) => !target || item.target_type === target) })
      }
      if (method === 'POST') {
        if (createStatus !== 201) return response({}, createStatus)
        const created = template({ ...JSON.parse(init.body), template_id: 'new-template' })
        rows.push(created)
        return response(created, 201)
      }
    }
    const match = url.pathname.match(/^\/api\/v1\/templates\/([^/]+)$/)
    if (match) {
      const row = rows.find((item) => item.template_id === match[1])
      if (!row) return response({}, 404)
      if (method === 'PUT') {
        if (updateStatus !== 200) return response({}, updateStatus)
        const payload = JSON.parse(init.body)
        if (payload.is_default) rows.forEach((item) => { item.is_default = false })
        Object.assign(row, payload)
        return response(row)
      }
      if (method === 'DELETE') {
        if (deleteStatus !== 200) return response({}, deleteStatus)
        rows.splice(rows.indexOf(row), 1)
        return response({ deleted_template_id: match[1] })
      }
    }
    if (url.pathname === '/api/v1/documents' && method === 'GET') return response({ items: [] })
    throw new Error(`Ruta inesperada: ${url.pathname}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function open(path) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

beforeEach(() => {
  sessionStorage.clear()
  sessionStorage.setItem('cms_access_token', 'fixture-token')
  vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')
  window.history.pushState({}, '', '/')
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe('Gestión de Templates', () => {
  it('lista tipos con nombres comprensibles, propiedades y filtros del backend', async () => {
    const fetchMock = mockBackend()
    open('/plantillas')
    expect(await screen.findByText('Plantilla Post')).toBeInTheDocument()
    expect(screen.getByText('Plantilla Landing')).toBeInTheDocument()
    expect(screen.getByText('Artículos / Posts')).toBeInTheDocument()
    expect(screen.getByText('Páginas del sitio')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '+ Nueva plantilla' })).toHaveAttribute('href', '/plantillas/nueva')
    await userEvent.click(screen.getByRole('button', { name: 'Para artículos' }))
    await waitFor(() => expect(screen.queryByText('Plantilla Landing')).not.toBeInTheDocument())
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/templates?target_type=POST'))).toBe(true)
    await userEvent.click(screen.getByRole('button', { name: 'Para páginas' }))
    await waitFor(() => expect(screen.queryByText('Plantilla Post')).not.toBeInTheDocument())
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/templates?target_type=LANDING'))).toBe(true)
  })

  it('la primera plantilla queda predeterminada y el formulario ofrece tipos de datos amigables', async () => {
    mockBackend({ templates: [] })
    open('/plantillas/nueva')
    expect(await screen.findByRole('heading', { name: 'Nueva plantilla' })).toBeInTheDocument()
    expect(await screen.findByLabelText('Nombre de la plantilla')).toBeInTheDocument()
    expect(screen.getByLabelText('Plantilla predeterminada')).toBeChecked()
    expect(screen.getByLabelText('Plantilla predeterminada')).toBeDisabled()
    expect(screen.getByLabelText('Tipo de contenido')).toHaveValue('POST')
    expect(screen.getByLabelText('Tipo de dato')).toHaveValue('STRING')
    expect(within(screen.getByLabelText('Tipo de dato')).getByRole('option', { name: 'Número entero' })).toHaveValue('INTEGER')
    expect(screen.getByText(/Los artículos publicados son inmutables/)).toBeInTheDocument()
  })

  it('crea POST con campos dinámicos y payload exacto, luego abre detalle', async () => {
    const fetchMock = mockBackend()
    open('/plantillas/nueva')
    await userEvent.type(await screen.findByLabelText('Nombre de la plantilla'), 'Plantilla de prueba')
    await userEvent.type(screen.getByLabelText('Identificador del campo'), 'category')
    expect(screen.getByText('Se mostrará como: Categoría')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('Obligatorio al publicar'))
    await userEvent.click(screen.getByRole('button', { name: '+ Agregar campo' }))
    await userEvent.type(screen.getAllByLabelText('Identificador del campo')[1], 'reading_time')
    await userEvent.selectOptions(screen.getAllByLabelText('Tipo de dato')[1], 'INTEGER')
    expect(screen.getByText('Se mostrará como: Tiempo de lectura')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Estructura de contenido'), { target: { value: '{"sections":["header","content"]}' } })
    await userEvent.click(screen.getByRole('button', { name: 'Crear plantilla' }))
    expect(await screen.findByText('Plantilla creada.')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/plantillas/new-template')
    const call = fetchMock.mock.calls.find(([url, init]) => url.endsWith('/templates') && init.method === 'POST')
    expect(JSON.parse(call[1].body)).toEqual({ name: 'Plantilla de prueba', target_type: 'POST',
      is_default: false, allow_published_edit: false,
      metadata_contract: [
        { field_key: 'category', expected_type: 'STRING', is_required: true },
        { field_key: 'reading_time', expected_type: 'INTEGER', is_required: false },
      ], layout_structure: { sections: ['header', 'content'] } })
  })

  it('crea LANDING con BOOLEAN y DATE y conserva sus valores API', async () => {
    const fetchMock = mockBackend()
    open('/plantillas/nueva')
    await userEvent.type(await screen.findByLabelText('Nombre de la plantilla'), 'Página de prueba')
    await userEvent.selectOptions(screen.getByLabelText('Tipo de contenido'), 'LANDING')
    await userEvent.click(screen.getByLabelText('Permitir edición después de publicar'))
    await userEvent.type(screen.getByLabelText('Identificador del campo'), 'visible')
    await userEvent.selectOptions(screen.getByLabelText('Tipo de dato'), 'BOOLEAN')
    await userEvent.click(screen.getByRole('button', { name: '+ Agregar campo' }))
    await userEvent.type(screen.getAllByLabelText('Identificador del campo')[1], 'published_date')
    await userEvent.selectOptions(screen.getAllByLabelText('Tipo de dato')[1], 'DATE')
    await userEvent.click(screen.getByRole('button', { name: 'Crear plantilla' }))
    await screen.findByText('Plantilla creada.')
    const call = fetchMock.mock.calls.find(([url, init]) => url.endsWith('/templates') && init.method === 'POST')
    expect(JSON.parse(call[1].body)).toMatchObject({ target_type: 'LANDING', allow_published_edit: true,
      metadata_contract: [{ field_key: 'visible', expected_type: 'BOOLEAN', is_required: false },
        { field_key: 'published_date', expected_type: 'DATE', is_required: false }] })
  })

  it.each([[409, 'Ya existe una plantilla con ese nombre.'],
    [422, 'Revisa los campos, la estructura y la plantilla predeterminada.']])(
    'crear con respuesta %s muestra un error seguro', async (status, message) => {
      mockBackend({ createStatus: status })
      open('/plantillas/nueva')
      await userEvent.type(await screen.findByLabelText('Nombre de la plantilla'), 'Plantilla repetida')
      await userEvent.type(screen.getByLabelText('Identificador del campo'), 'topic')
      await userEvent.click(screen.getByRole('button', { name: 'Crear plantilla' }))
      expect(await screen.findByRole('alert')).toHaveTextContent(message)
      expect(window.location.pathname).toBe('/plantillas/nueva')
    },
  )

  it('permite eliminar una fila pero bloquea identificadores duplicados y ausencia de campos', async () => {
    const fetchMock = mockBackend()
    open('/plantillas/nueva')
    await userEvent.type(await screen.findByLabelText('Nombre de la plantilla'), 'Duplicada')
    await userEvent.type(screen.getByLabelText('Identificador del campo'), 'category')
    await userEvent.click(screen.getByRole('button', { name: '+ Agregar campo' }))
    await userEvent.type(screen.getAllByLabelText('Identificador del campo')[1], 'category')
    await userEvent.click(screen.getByRole('button', { name: 'Crear plantilla' }))
    expect(screen.getByText('El identificador del campo está duplicado.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url, init]) => url.endsWith('/templates') && init.method === 'POST')).toBe(false)
    await userEvent.click(screen.getAllByRole('button', { name: 'Eliminar campo' })[1])
    expect(screen.getAllByLabelText('Identificador del campo')).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar campo' }))
    await userEvent.click(screen.getByRole('button', { name: 'Crear plantilla' }))
    expect(screen.getByText('Agrega al menos un campo adicional.')).toBeInTheDocument()
  })

  it.each(['{roto', '["header"]'])('rechaza layout inválido o array raíz: %s', async (layout) => {
    const fetchMock = mockBackend()
    open('/plantillas/nueva')
    await userEvent.type(await screen.findByLabelText('Nombre de la plantilla'), 'Layout de prueba')
    await userEvent.type(screen.getByLabelText('Identificador del campo'), 'topic')
    fireEvent.change(screen.getByLabelText('Estructura de contenido'), { target: { value: layout } })
    await userEvent.click(screen.getByRole('button', { name: 'Crear plantilla' }))
    expect(screen.getByText('La estructura debe ser un objeto JSON válido.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url, init]) => url.endsWith('/templates') && init.method === 'POST')).toBe(false)
  })

  it('detalle muestra datos y JSON como texto, sin ejecutarlo', async () => {
    mockBackend({ templates: [template({ name: '<script>alert(1)</script>',
      layout_structure: { sample: '<img src=x onerror=alert(1)>' } })] })
    open('/plantillas/post-template')
    expect(await screen.findByRole('heading', { name: '<script>alert(1)</script>' })).toBeInTheDocument()
    expect(screen.getByText(/<img src=x onerror=alert\(1\)>/)).toBeInTheDocument()
    expect(document.querySelector('img')).toBeNull()
    expect(screen.getByText('Categoría')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Editar' })).toHaveAttribute('href', '/plantillas/post-template/editar')
  })

  it('edición carga datos, protege inmutables y PUT envía solo cuatro campos', async () => {
    const fetchMock = mockBackend()
    open('/plantillas/landing-template/editar')
    expect(await screen.findByDisplayValue('Plantilla Landing')).toBeInTheDocument()
    expect(screen.getByText('Páginas del sitio')).toBeInTheDocument()
    expect(screen.getAllByText('No modificable')).toHaveLength(2)
    expect(screen.queryByLabelText('Tipo de contenido')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Permitir edición después de publicar')).not.toBeInTheDocument()
    await userEvent.clear(screen.getByLabelText('Nombre de la plantilla'))
    await userEvent.type(screen.getByLabelText('Nombre de la plantilla'), 'Landing editada')
    await userEvent.click(screen.getByLabelText('Plantilla predeterminada'))
    expect(screen.getByText('La plantilla predeterminada actual dejará de serlo.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))
    expect(await screen.findByText('Plantilla actualizada.')).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([url, init]) => url.endsWith('/templates/landing-template') && init.method === 'PUT')
    expect(Object.keys(JSON.parse(call[1].body)).sort()).toEqual(['name', 'is_default', 'metadata_contract', 'layout_structure'].sort())
    expect(JSON.parse(call[1].body).is_default).toBe(true)
    expect(JSON.parse(call[1].body).name).toBe('Landing editada')
  })

  it('impide desmarcar la predeterminada vigente y muestra 409/422 seguros', async () => {
    mockBackend({ updateStatus: 422 })
    open('/plantillas/post-template/editar')
    expect(await screen.findByDisplayValue('Plantilla Post')).toBeInTheDocument()
    expect(screen.getByLabelText('Plantilla predeterminada')).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('debe permanecer una plantilla predeterminada')
  })

  it('eliminar pide confirmación y al responder 200 vuelve al listado', async () => {
    const fetchMock = mockBackend()
    open('/plantillas/landing-template')
    await screen.findByRole('heading', { name: 'Plantilla Landing' })
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar plantilla' }))
    const dialog = screen.getByRole('dialog', { name: 'Eliminar plantilla' })
    expect(within(dialog).getByText(/si no está siendo utilizada/)).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url, init]) => url.endsWith('/templates/landing-template') && init.method === 'DELETE')).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Eliminar plantilla' }))
    expect(await screen.findByText('Plantilla eliminada.')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/plantillas')
  })

  it.each([
    [[template()], 'última plantilla'],
    [[template(), template({ template_id: 'other', is_default: false })], 'está siendo utilizada'],
  ])('DELETE 409 distingue última o utilizada', async (templates, message) => {
    mockBackend({ templates, deleteStatus: 409 })
    open('/plantillas/post-template')
    await screen.findByRole('heading', { name: 'Plantilla Post' })
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar plantilla' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Eliminar plantilla' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })

  it('Nuevo Post recibe una Template POST nueva y excluye LANDING', async () => {
    const fetchMock = mockBackend({ templates: [template({ template_id: 'fresh', name: 'Plantilla nueva',
      metadata_contract: [{ field_key: 'difficulty', expected_type: 'STRING', is_required: false }] }),
    template({ template_id: 'landing', name: 'Solo LANDING', target_type: 'LANDING', is_default: false })] })
    open('/contenido/nuevo')
    expect(await screen.findByRole('option', { name: 'Plantilla nueva' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Difficulty/)).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Solo LANDING' })).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/templates?target_type=POST'))).toBe(true)
  })

  it('una Template POST creada desde la UI alimenta Nuevo Post sin registrar campos a mano', async () => {
    const fetchMock = mockBackend()
    open('/plantillas/nueva')
    await userEvent.type(await screen.findByLabelText('Nombre de la plantilla'), 'Plantilla nueva UI')
    await userEvent.type(screen.getByLabelText('Identificador del campo'), 'topic')
    await userEvent.click(screen.getByRole('button', { name: 'Crear plantilla' }))
    await screen.findByText('Plantilla creada.')
    await userEvent.click(screen.getByRole('link', { name: 'Contenido' }))
    await userEvent.click(screen.getByRole('link', { name: '+ Nuevo post' }))
    expect(await screen.findByRole('option', { name: 'Plantilla nueva UI' })).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Plantilla'), 'new-template')
    expect(screen.getByLabelText(/Topic/)).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Plantilla Landing' })).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/templates?target_type=POST'))).toBe(true)
  })

  it('401 de Templates borra la sesión y vuelve a Login', async () => {
    mockBackend({ templatesStatus: 401 })
    open('/plantillas')
    expect(await screen.findByRole('heading', { name: 'Acceso administrativo' })).toBeInTheDocument()
    expect(sessionStorage.getItem('cms_access_token')).toBeNull()
  })
})
