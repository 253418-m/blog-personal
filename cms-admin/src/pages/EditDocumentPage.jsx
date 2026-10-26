import { useCallback, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getDocument, updateDocument } from '../api/documents'
import { ApiError } from '../api/http'
import { getTemplates } from '../api/templates'
import { DocumentForm } from '../components/DocumentForm'
import { ErrorNotice } from '../components/ErrorNotice'
import { useApiData } from '../hooks/useApiData'

export function EditDocumentPage() {
  const { documentId } = useParams()
  const navigate = useNavigate()
  const load = useCallback(async () => {
    const document = await getDocument(documentId)
    const templates = await getTemplates({ target_type: document.content_type })
    return { document, templates }
  }, [documentId])
  const { loading, data, error } = useApiData(load)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  async function save(payload) {
    setSaving(true)
    setSaveError('')
    try {
      await updateDocument(documentId, payload)
      navigate(`/contenido/${documentId}`, { replace: true, state: { flash: 'Borrador actualizado.' } })
    } catch (failure) {
      setSaveError(failure instanceof ApiError && failure.status === 409
        ? 'No fue posible guardar: el slug ya existe o el estado cambió.'
        : failure instanceof ApiError && failure.status === 422
          ? 'Revisa los datos y metadatos del borrador.'
          : 'No fue posible guardar los cambios.')
    } finally {
      setSaving(false)
    }
  }

  return <>
    <div className="page-heading">
      <Link className="back-link" to={`/contenido/${documentId}`}>← Volver al documento</Link>
      <span className="eyebrow">Edición de borrador</span>
      <h1>Editar documento</h1>
    </div>
    {loading ? <p className="page-status" role="status">Cargando documento…</p>
      : error instanceof ApiError && error.status === 404 ? <div className="panel empty-state">Documento no encontrado. <Link to="/contenido">Volver a Contenido</Link></div>
        : error ? <ErrorNotice message="No fue posible cargar el documento." />
          : data.document.status !== 'BORRADOR' ? <div className="panel empty-state">Este documento ya no es editable. <Link to={`/contenido/${documentId}`}>Ver documento</Link></div>
            : data.templates.length === 0 ? <div className="panel empty-state">No existe una plantilla compatible para este documento.</div>
              : <DocumentForm key={documentId} templates={data.templates} initialDocument={data.document}
                onSubmit={save} saving={saving} error={saveError} />}
  </>
}
