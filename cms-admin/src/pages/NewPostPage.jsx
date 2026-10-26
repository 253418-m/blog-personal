import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createDocument } from '../api/documents'
import { ApiError } from '../api/http'
import { getTemplates } from '../api/templates'
import { DocumentForm } from '../components/DocumentForm'
import { ErrorNotice } from '../components/ErrorNotice'
import { useApiData } from '../hooks/useApiData'

const loadPostTemplates = () => getTemplates({ target_type: 'POST' })

export function NewPostPage() {
  const navigate = useNavigate()
  const { loading, data: templates, error } = useApiData(loadPostTemplates)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  async function save(payload) {
    setSaving(true)
    setSaveError('')
    try {
      const result = await createDocument(payload)
      navigate(`/contenido/${result.document_id}`, { replace: true, state: { flash: 'Borrador guardado.' } })
    } catch (failure) {
      setSaveError(failure instanceof ApiError && failure.status === 409
        ? 'Ya existe un documento con ese slug. Elige otro.'
        : failure instanceof ApiError && failure.status === 422
          ? 'Revisa los datos y metadatos del borrador.'
          : 'No fue posible guardar el borrador. Inténtalo de nuevo.')
    } finally {
      setSaving(false)
    }
  }

  return <>
    <div className="page-heading">
      <Link className="back-link" to="/contenido">← Volver a Contenido</Link>
      <span className="eyebrow">Nuevo artículo</span>
      <h1>Nuevo post</h1>
      <p>Guarda un borrador antes de publicarlo en Quarto.</p>
    </div>
    {loading ? <p className="page-status" role="status">Cargando plantillas de artículos…</p>
      : error ? <ErrorNotice message="No fue posible cargar las plantillas de artículos." />
        : templates.length === 0 ? <div className="panel empty-state" role="status">No existe una plantilla para crear posts.</div>
          : <DocumentForm templates={templates} onSubmit={save} saving={saving} error={saveError} />}
  </>
}
