import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'

const postTemplate = {
  template_id: 'post-default', name: 'Plantilla Post', target_type: 'POST', is_default: true,
  allow_published_edit: false,
  metadata_contract: [
    { field_key: 'category', expected_type: 'STRING', is_required: true },
    { field_key: 'reading_time', expected_type: 'INTEGER', is_required: false },
    { field_key: 'featured', expected_type: 'BOOLEAN', is_required: false },
    { field_key: 'event_date', expected_type: 'DATE', is_required: false },
  ],
}
const alternateTemplate = { ...postTemplate, template_id: 'post-other', name: 'Otra plantilla', is_default: false }
const landingTemplate = { ...postTemplate, template_id: 'landing', name: 'Landing', target_type: 'LANDING' }

function fixtureDocument(status = 'BORRADOR', overrides = {}) {
  return {
    document_id: 'doc-1', title: 'Borrador original', slug: 'borrador-original', content_type: 'POST',
    status, template_id: 'post-default', metadata_values: { category: 'Redes', reading_time: 2 },
    content: '# Texto seguro\n\nContenido de prueba.', created_at: '2026-10-20T12:00:00Z',
    updated_at: '2026-10-26T12:00:00Z', published_at: status === 'BORRADOR' ? null : '2026-10-26T12:00:00Z',
    ...overrides,
  }
}

function reply(data, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => data }
}

function mockBackend({ documents = [fixtureDocument()], templates = [postTemplate, alternateTemplate, landingTemplate],
  publishStatus = 200, publishGate, archiveStatus = 200, archiveGate, documentsStatus = 200 } = {}) {
  const rows = documents.map((item) => ({ ...item }))
  const fetchMock = vi.fn(async (rawUrl, init = {}) => {
    const url = new URL(rawUrl)
    const method = init.method || 'GET'
    const path = url.pathname
    if (path === '/api/v1/auth/me') return reply({ user_id: 'admin', username: 'editor', is_active: true })
    if (path === '/api/v1/templates' && method === 'GET') {
      const target = url.searchParams.get('target_type')
      return reply({ items: templates.filter((item) => !target || item.target_type === target) })
    }
    if (path === '/api/v1/documents' && method === 'GET') {
      if (documentsStatus !== 200) return reply({}, documentsStatus)
      const status = url.searchParams.get('status')
      const type = url.searchParams.get('content_type')
      return reply({ items: rows.filter((item) => (!status || item.status === status) &&
        (!type || item.content_type === type)) })
    }
    if (path === '/api/v1/documents' && method === 'POST') {
      const payload = JSON.parse(init.body)
      const created = fixtureDocument('BORRADOR', { ...payload, document_id: 'created-id' })
      rows.push(created)
      return reply(created, 201)
    }
    const match = path.match(/^\/api\/v1\/documents\/([^/]+)(?:\/(publish|archive))?$/)
    if (!match) throw new Error('Ruta inesperada de test')
    const row = rows.find((item) => item.document_id === match[1])
    if (!row) return reply({}, 404)
    if (method === 'GET') return reply(row)
    if (method === 'PUT') {
      Object.assign(row, JSON.parse(init.body), { updated_at: '2026-10-26T13:00:00Z' })
      return reply(row)
    }
    if (method === 'DELETE') {
      rows.splice(rows.indexOf(row), 1)
      return reply(null, 204)
    }
    if (method === 'POST' && match[2] === 'publish') {
      if (publishGate) await publishGate
      if (publishStatus !== 200) return reply({}, publishStatus)
      Object.assign(row, { status: 'PUBLICADO', published_at: '2026-10-26T13:00:00Z' })
      return reply(row)
    }
    if (method === 'POST' && match[2] === 'archive') {
      if (archiveGate) await archiveGate
      if (archiveStatus !== 200) return reply({}, archiveStatus)
      row.status = 'ARCHIVADO'
      return reply(row)
    }
    throw new Error('Método inesperado de test')
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

describe('Listado de Documents', () => {
  it('lista documentos, fechas, tipos y acciones permitidas por estado', async () => {
    mockBackend({ documents: [fixtureDocument(), fixtureDocument('PUBLICADO', { document_id: 'doc-2', title: 'Publicado' }),
      fixtureDocument('ARCHIVADO', { document_id: 'doc-3', title: 'Archivado' })] })
    open('/contenido')
    expect(await screen.findByText('Borrador original')).toBeInTheDocument()
    const rows = screen.getAllByRole('row')
    expect(within(rows[1]).getByText('Editar')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Publicar')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Eliminar')).toBeInTheDocument()
    expect(within(rows[2]).getByText('Archivar')).toBeInTheDocument()
    expect(within(rows[2]).queryByText('Editar')).not.toBeInTheDocument()
    expect(within(rows[2]).queryByText('Eliminar')).not.toBeInTheDocument()
    expect(within(rows[3]).getByText('Ver')).toBeInTheDocument()
    expect(within(rows[3]).queryByText('Publicar')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '+ Nuevo post' })).toHaveAttribute('href', '/contenido/nuevo')
  })

  it('usa filtros status y content_type del backend', async () => {
    const fetchMock = mockBackend({ documents: [fixtureDocument(),
      fixtureDocument('PUBLICADO', { document_id: 'doc-2', title: 'Post publicado' }),
      fixtureDocument('BORRADOR', { document_id: 'doc-3', title: 'Landing', content_type: 'LANDING' })] })
    open('/contenido')
    await screen.findByText('Post publicado')
    await userEvent.click(screen.getByRole('button', { name: 'Borradores' }))
    await waitFor(() => expect(screen.queryByText('Post publicado')).not.toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText('Tipo'), 'POST')
    await waitFor(() => expect(screen.queryByText('Landing')).not.toBeInTheDocument())
    expect(fetchMock.mock.calls.some(([url]) => url.includes('status=BORRADOR') && url.includes('content_type=POST'))).toBe(true)
  })

  it('Publicar desde la lista abre el detalle y pide confirmación', async () => {
    const fetchMock = mockBackend()
    open('/contenido')
    const row = (await screen.findByText('Borrador original')).closest('tr')
    await userEvent.click(within(row).getByRole('link', { name: 'Publicar' }))
    expect(await screen.findByRole('dialog', { name: 'Publicar documento' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/publish'))).toBe(false)
  })
})

describe('Creación y edición', () => {
  it('carga solo Templates POST, selecciona default y muestra cuatro tipos de metadatos', async () => {
    const fetchMock = mockBackend()
    open('/contenido/nuevo')
    expect(await screen.findByRole('heading', { name: 'Nuevo post' })).toBeInTheDocument()
    expect(await screen.findByLabelText('Plantilla')).toHaveValue('post-default')
    expect(screen.getByText('Artículo / Post')).toBeInTheDocument()
    expect(screen.getByText('Datos del artículo')).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Landing' })).not.toBeInTheDocument()
    expect(screen.getByLabelText(/Categoría/)).toHaveAttribute('type', 'text')
    expect(screen.getByLabelText(/Tiempo de lectura/)).toHaveAttribute('type', 'number')
    expect(screen.getByLabelText(/Featured/)).toHaveAttribute('type', 'checkbox')
    expect(screen.getByLabelText(/Event date/)).toHaveAttribute('type', 'date')
    expect(screen.getByText('minutos')).toBeInTheDocument()
    for (const field of ['Título', 'Identificador URL', 'Plantilla', 'Contenido']) {
      expect(within(screen.getByLabelText(field).closest('.form-field'))
        .getByRole('button', { name: 'Mostrar ayuda' })).toHaveAttribute('type', 'button')
    }
    for (const field of [/Categoría/, /Tiempo de lectura/]) {
      expect(within(screen.getByLabelText(field).closest('.form-field'))
        .getByRole('button', { name: 'Mostrar ayuda' })).toBeInTheDocument()
    }
    expect(within(screen.getByText('Datos del artículo').closest('.field-label-row'))
      .getByRole('button', { name: 'Mostrar ayuda' })).toBeInTheDocument()
    expect(screen.queryByText('Tema principal al que pertenece el artículo.')).not.toBeInTheDocument()
    expect(screen.getByText('Obligatorio al publicar')).toBeInTheDocument()
    expect(screen.getAllByText('Opcional').length).toBeGreaterThan(0)
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/templates?target_type=POST'))).toBe(true)
  })

  it('muestra una etiqueta legible para metadata futura sin renombrar su clave', async () => {
    const customTemplate = { ...postTemplate, metadata_contract: [
      ...postTemplate.metadata_contract,
      { field_key: 'published_date', expected_type: 'DATE', is_required: false },
    ] }
    const fetchMock = mockBackend({ templates: [customTemplate] })
    open('/contenido/nuevo')
    await userEvent.type(await screen.findByLabelText('Título'), 'Post futuro')
    const help = within(screen.getByLabelText(/Published date/).closest('.form-field'))
      .getByRole('button', { name: 'Mostrar ayuda' })
    await userEvent.hover(help)
    expect(screen.getByRole('tooltip')).toHaveTextContent('Campo adicional definido por la plantilla seleccionada.')
    await userEvent.unhover(help)
    await userEvent.type(screen.getByLabelText(/Published date/), '2026-10-26')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }))
    await screen.findByText('Borrador guardado.')
    const createCall = fetchMock.mock.calls.find(([url, init]) => url.endsWith('/documents') && init.method === 'POST')
    expect(JSON.parse(createCall[1].body).metadata_values.published_date).toBe('2026-10-26')
  })

  it('bloquea la creación cuando no hay Template POST', async () => {
    mockBackend({ templates: [landingTemplate] })
    open('/contenido/nuevo')
    expect(await screen.findByText('No existe una plantilla para crear posts.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Guardar borrador' })).not.toBeInTheDocument()
  })

  it('sugiere slug y conserva la edición manual', async () => {
    mockBackend()
    open('/contenido/nuevo')
    const title = await screen.findByLabelText('Título')
    await userEvent.type(title, 'Introducción a VLANs: Básico')
    const slug = screen.getByLabelText('Identificador URL')
    expect(slug).toHaveValue('introduccion-a-vlans-basico')
    expect(screen.getByText(/Dirección:/)).toHaveTextContent('/posts/introduccion-a-vlans-basico/')
    await userEvent.clear(slug)
    expect(screen.getByText(/Dirección:/)).toHaveTextContent('/posts/.../')
    await userEvent.type(slug, 'mi-slug')
    await userEvent.type(title, ' ampliado')
    expect(slug).toHaveValue('mi-slug')
    expect(screen.getByText(/Dirección:/)).toHaveTextContent('/posts/mi-slug/')
    expect(slug).toHaveAccessibleDescription(/Dirección: \/posts\/mi-slug\//)
    const help = within(slug.closest('.form-field')).getByRole('button', { name: 'Mostrar ayuda' })
    await userEvent.hover(help)
    expect(screen.getByRole('tooltip')).toHaveTextContent(/Se genera automáticamente a partir del título/)
    await userEvent.unhover(help)
  })

  it('guarda BORRADOR con payload tipado y redirige al detalle', async () => {
    const fetchMock = mockBackend()
    open('/contenido/nuevo')
    await userEvent.type(await screen.findByLabelText('Título'), 'Nuevo post')
    await userEvent.type(screen.getByLabelText(/Categoría/), 'Redes')
    await userEvent.type(screen.getByLabelText(/Tiempo de lectura/), '2')
    await userEvent.click(screen.getByLabelText(/Featured/))
    await userEvent.type(screen.getByLabelText(/Event date/), '2026-10-26')
    await userEvent.type(screen.getByLabelText('Contenido'), '# Prueba')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }))
    expect(await screen.findByText('Borrador guardado.')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/contenido/created-id')
    const createCall = fetchMock.mock.calls.find(([url, init]) => url.endsWith('/documents') && init.method === 'POST')
    expect(JSON.parse(createCall[1].body)).toEqual({
      title: 'Nuevo post', slug: 'nuevo-post', content_type: 'POST', template_id: 'post-default',
      metadata_values: { category: 'Redes', reading_time: 2, featured: true, event_date: '2026-10-26' },
      content: '# Prueba',
    })
  })

  it('permite guardar borrador sin metadata obligatoria y valida slug inválido', async () => {
    const fetchMock = mockBackend()
    open('/contenido/nuevo')
    await userEvent.type(await screen.findByLabelText('Título'), 'Título')
    await userEvent.clear(screen.getByLabelText('Identificador URL'))
    await userEvent.type(screen.getByLabelText('Identificador URL'), 'Slug Incorrecto')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }))
    expect(screen.getByText('Usa minúsculas, números y guiones simples.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url, init]) => url.endsWith('/documents') && init.method === 'POST')).toBe(false)
    await userEvent.clear(screen.getByLabelText('Identificador URL'))
    await userEvent.type(screen.getByLabelText('Identificador URL'), 'slug-valido')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }))
    await screen.findByText('Borrador guardado.')
    const createCall = fetchMock.mock.calls.find(([url, init]) => url.endsWith('/documents') && init.method === 'POST')
    expect(JSON.parse(createCall[1].body).metadata_values).toEqual({ featured: false })
  })

  it('carga BORRADOR y PUT solo envía campos editables', async () => {
    const fetchMock = mockBackend()
    open('/contenido/doc-1/editar')
    expect(await screen.findByDisplayValue('Borrador original')).toBeInTheDocument()
    expect(screen.getByLabelText('Identificador URL')).toHaveValue('borrador-original')
    expect(screen.getByText('Artículo / Post')).toBeInTheDocument()
    expect(within(screen.getByLabelText('Título').closest('.form-field'))
      .getByRole('button', { name: 'Mostrar ayuda' })).toBeInTheDocument()
    await userEvent.clear(screen.getByLabelText('Título'))
    await userEvent.type(screen.getByLabelText('Título'), 'Título editado')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }))
    expect(await screen.findByText('Borrador actualizado.')).toBeInTheDocument()
    const put = fetchMock.mock.calls.find(([url, init]) => url.endsWith('/documents/doc-1') && init.method === 'PUT')
    expect(Object.keys(JSON.parse(put[1].body)).sort()).toEqual(
      ['title', 'slug', 'template_id', 'metadata_values', 'content'].sort(),
    )
    expect(JSON.parse(put[1].body).title).toBe('Título editado')
  })
})

describe('Detalle y ciclo de vida', () => {
  it('PUBLICADO es lectura segura: Ver y Archivar, sin Editar ni Eliminar', async () => {
    mockBackend({ documents: [fixtureDocument('PUBLICADO', { content: '<script>alert(1)</script>' })] })
    open('/contenido/doc-1')
    expect(await screen.findByText('<script>alert(1)</script>')).toBeInTheDocument()
    expect(window.document.querySelector('script:not([src])')).toBeNull()
    expect(screen.queryByRole('link', { name: 'Editar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Eliminar borrador' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archivar' })).toBeInTheDocument()
  })

  it('ARCHIVADO no presenta acciones de mutación', async () => {
    mockBackend({ documents: [fixtureDocument('ARCHIVADO')] })
    open('/contenido/doc-1')
    expect(await screen.findByText(/Archivado: no admite/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Archivar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Publicar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Editar' })).not.toBeInTheDocument()
  })

  it('la ruta de edición bloquea un POST PUBLICADO', async () => {
    mockBackend({ documents: [fixtureDocument('PUBLICADO')] })
    open('/contenido/doc-1/editar')
    expect(await screen.findByText(/Este documento ya no es editable/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Guardar borrador' })).not.toBeInTheDocument()
  })

  it('informa metadata faltante antes de publicar sin llamar API', async () => {
    const fetchMock = mockBackend({ documents: [fixtureDocument('BORRADOR', { metadata_values: {} })] })
    open('/contenido/doc-1')
    await screen.findByRole('heading', { name: 'Borrador original' })
    await userEvent.click(screen.getByRole('button', { name: 'Publicar' }))
    expect(screen.getByRole('alert')).toHaveTextContent('category')
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/publish'))).toBe(false)
  })

  it('confirma publicación, muestra espera y pasa a lectura al responder 200', async () => {
    let release
    const gate = new Promise((resolve) => { release = resolve })
    const fetchMock = mockBackend({ publishGate: gate })
    open('/contenido/doc-1')
    await screen.findByRole('heading', { name: 'Borrador original' })
    await userEvent.click(screen.getByRole('button', { name: 'Publicar' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/ya no podrá editarse/)).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/publish'))).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Publicar ahora' }))
    expect(screen.getByRole('status')).toHaveTextContent('Publicando y generando el sitio...')
    expect(within(dialog).getByRole('button', { name: 'Procesando…' })).toBeDisabled()
    release()
    expect(await screen.findByText('Post publicado correctamente.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Editar' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archivar' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url, init]) => url.endsWith('/documents/doc-1/publish') && init.method === 'POST' && !init.body)).toBe(true)
  })

  it.each([[409, 'slug o el contenido Quarto'], [422, 'revisa título, contenido'],
    [500, 'El borrador se conservó']])('publicación %s muestra error seguro', async (status, message) => {
    mockBackend({ publishStatus: status })
    open('/contenido/doc-1')
    await screen.findByRole('heading', { name: 'Borrador original' })
    await userEvent.click(screen.getByRole('button', { name: 'Publicar' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Publicar ahora' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByRole('button', { name: 'Publicar' })).toBeInTheDocument()
  })

  it('archivar POST confirma, espera el render y pasa a ARCHIVADO', async () => {
    let release
    const gate = new Promise((resolve) => { release = resolve })
    const fetchMock = mockBackend({ documents: [fixtureDocument('PUBLICADO')], archiveGate: gate })
    open('/contenido/doc-1')
    await screen.findByRole('heading', { name: 'Borrador original' })
    await userEvent.click(screen.getByRole('button', { name: 'Archivar' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByRole('heading', { name: '¿Archivar este post?' })).toBeInTheDocument()
    expect(within(dialog).getByText(/se retirará del sitio generado/)).toBeInTheDocument()
    expect(within(dialog).queryByText(/seguirá público/)).not.toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Archivar' }))
    expect(screen.getByRole('status')).toHaveTextContent('Archivando y actualizando el sitio...')
    expect(within(dialog).getByRole('button', { name: 'Procesando…' })).toBeDisabled()
    release()
    expect(await screen.findByText('Post archivado correctamente y retirado del sitio generado.')).toBeInTheDocument()
    expect(screen.getByText(/Archivado: no admite/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Archivar' })).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url, init]) => url.endsWith('/archive') && init.method === 'POST')).toBe(true)
  })

  it.each([[500, 'El contenido permanece publicado'], [409, 'estado actual']])(
    'archivar POST con error %s mantiene la vista PUBLICADO', async (status, message) => {
      mockBackend({ documents: [fixtureDocument('PUBLICADO')], archiveStatus: status })
      open('/contenido/doc-1')
      await screen.findByRole('heading', { name: 'Borrador original' })
      await userEvent.click(screen.getByRole('button', { name: 'Archivar' }))
      await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Archivar' }))
      expect(await screen.findByRole('alert')).toHaveTextContent(message)
      expect(screen.getByRole('button', { name: 'Archivar' })).toBeInTheDocument()
    },
  )

  it('LANDING archivada conserva un mensaje administrativo y no promete retirada Quarto', async () => {
    mockBackend({ documents: [fixtureDocument('PUBLICADO', { content_type: 'LANDING' })] })
    open('/contenido/doc-1')
    await screen.findByRole('heading', { name: 'Borrador original' })
    await userEvent.click(screen.getByRole('button', { name: 'Archivar' }))
    expect(within(screen.getByRole('dialog')).queryByText(/sitio generado/)).not.toBeInTheDocument()
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Archivar' }))
    expect(await screen.findByText('Documento archivado.')).toBeInTheDocument()
  })

  it('eliminar BORRADOR confirma, acepta 204 y vuelve al listado', async () => {
    const fetchMock = mockBackend()
    open('/contenido/doc-1')
    await screen.findByRole('heading', { name: 'Borrador original' })
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar borrador' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Eliminar borrador' }))
    expect(await screen.findByText('Borrador eliminado.')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/contenido')
    expect(fetchMock.mock.calls.some(([url, init]) => url.endsWith('/documents/doc-1') && init.method === 'DELETE')).toBe(true)
  })

  it('404 ofrece volver a Contenido', async () => {
    mockBackend()
    open('/contenido/no-existe')
    expect(await screen.findByText('Documento no encontrado.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Volver a Contenido' })).toHaveAttribute('href', '/contenido')
  })

  it('401 de Documents conserva la redirección global al Login', async () => {
    mockBackend({ documentsStatus: 401 })
    open('/contenido')
    expect(await screen.findByRole('heading', { name: 'Acceso administrativo' })).toBeInTheDocument()
    expect(sessionStorage.getItem('cms_access_token')).toBeNull()
  })
})
