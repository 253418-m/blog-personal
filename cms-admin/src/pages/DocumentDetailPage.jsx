import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { archiveDocument, deleteDocument, getDocument, publishDocument } from '../api/documents'
import { ApiError } from '../api/http'
import { getTemplates } from '../api/templates'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorNotice } from '../components/ErrorNotice'
import { Feedback } from '../components/Feedback'
import { StatusBadge } from '../components/StatusBadge'
import { useApiData } from '../hooks/useApiData'
import { missingPublishFields } from '../utils/documentForm'
import { formatDate } from '../utils/format'

function actionError(action, error) {
  if (action === 'publish') {
    if (error instanceof ApiError && error.status === 409) return 'No fue posible publicar: el slug o el contenido Quarto ya existe, o cambió el estado.'
    if (error instanceof ApiError && error.status === 422) return 'No fue posible publicar: revisa título, contenido y metadatos obligatorios.'
    if (error instanceof ApiError && error.status === 500) return 'No fue posible publicar el post. El borrador se conservó.'
    return 'No fue posible publicar el documento. Comprueba el estado del borrador.'
  }
  if (error instanceof ApiError && error.status === 409) return 'La operación no está permitida para el estado actual.'
  return action === 'delete' ? 'No fue posible eliminar el borrador.' : 'No fue posible archivar el documento.'
}

export function DocumentDetailPage() {
  const { documentId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const load = useCallback(async () => {
    const [document, templates] = await Promise.all([getDocument(documentId), getTemplates()])
    return { document, templates }
  }, [documentId])
  const { loading, data, error } = useApiData(load)
  const [updated, setUpdated] = useState(null)
  const [intent, setIntent] = useState(location.state?.intent || null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState(null)
  const document = updated?.document_id === documentId ? updated : data?.document
  const template = data?.templates.find((item) => item.template_id === document?.template_id)

  useEffect(() => {
    if (location.state?.intent) navigate(location.pathname, { replace: true, state: null })
  }, [location.pathname, location.state, navigate])

  useEffect(() => {
    if (!intent || !document) return
    const permitted = (document.status === 'BORRADOR' && (intent === 'publish' || intent === 'delete')) ||
      (document.status === 'PUBLICADO' && intent === 'archive')
    if (!permitted) {
      setIntent(null)
      setFeedback({ tone: 'error', message: 'La acción ya no está disponible para este documento.' })
      return
    }
    if (intent !== 'publish') return
    const missing = missingPublishFields(document, template)
    if (!template || missing.length) {
      setIntent(null)
      setFeedback({ tone: 'error', message: !template
        ? 'No fue posible comprobar la plantilla del documento.'
        : `Antes de publicar completa: ${missing.join(', ')}.` })
    }
  }, [intent, document, template])

  function askPublish() {
    const missing = missingPublishFields(document, template)
    if (!template) {
      setFeedback({ tone: 'error', message: 'No fue posible comprobar la plantilla del documento.' })
    } else if (missing.length) {
      setFeedback({ tone: 'error', message: `Antes de publicar completa: ${missing.join(', ')}.` })
    } else {
      setFeedback(null)
      setIntent('publish')
    }
  }

  async function confirmAction() {
    const action = intent
    setBusy(true)
    setFeedback(null)
    try {
      if (action === 'delete') {
        await deleteDocument(documentId)
        navigate('/contenido', { replace: true, state: { flash: 'Borrador eliminado.' } })
        return
      }
      const result = action === 'publish' ? await publishDocument(documentId) : await archiveDocument(documentId)
      setUpdated(result)
      try { setUpdated(await getDocument(documentId)) } catch { /* La respuesta 200 ya refleja el nuevo estado. */ }
      setFeedback({ tone: 'success', message: action === 'publish'
        ? 'Post publicado correctamente.' : 'Documento archivado.' })
    } catch (failure) {
      setFeedback({ tone: 'error', message: actionError(action, failure) })
    } finally {
      setBusy(false)
      setIntent(null)
    }
  }

  if (loading) return <p className="page-status" role="status">Cargando documento…</p>
  if (error instanceof ApiError && error.status === 404) return <div className="panel empty-state">Documento no encontrado. <Link to="/contenido">Volver a Contenido</Link></div>
  if (error) return <ErrorNotice message="No fue posible cargar el documento." />

  return <>
    <div className="page-heading">
      <Link className="back-link" to="/contenido">← Volver a Contenido</Link>
      <span className="eyebrow">{document.content_type} · {document.slug}</span>
      <h1>{document.title}</h1>
      <StatusBadge status={document.status} />
    </div>
    {location.state?.flash && <Feedback tone="success">{location.state.flash}</Feedback>}
    {feedback && <Feedback tone={feedback.tone}>{feedback.message}</Feedback>}
    {busy && <p className="page-status" role="status">{intent === 'publish' ? 'Publicando y generando el sitio...' : 'Procesando…'}</p>}
    <section className="panel detail-panel" aria-label="Detalle del documento">
      <dl className="detail-grid">
        <div><dt>Tipo</dt><dd>{document.content_type}</dd></div>
        <div><dt>Slug</dt><dd>{document.slug}</dd></div>
        <div><dt>Plantilla</dt><dd>{template?.name || document.template_id}</dd></div>
        <div><dt>Creado</dt><dd>{formatDate(document.created_at)}</dd></div>
        <div><dt>Actualizado</dt><dd>{formatDate(document.updated_at)}</dd></div>
        <div><dt>Publicado</dt><dd>{formatDate(document.published_at)}</dd></div>
      </dl>
      <h2>Metadatos</h2>
      {Object.keys(document.metadata_values || {}).length === 0 ? <p className="muted">Sin metadatos.</p> : (
        <dl className="metadata-summary">{Object.entries(document.metadata_values).map(([key, value]) => (
          <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>
        ))}</dl>
      )}
      <h2>Contenido</h2>
      <pre className="content-text">{document.content || 'Sin contenido todavía.'}</pre>
    </section>
    <div className="detail-actions">
      {document.status === 'BORRADOR' && <>
        <Link className="secondary-button button-link" to={`/contenido/${documentId}/editar`}>Editar</Link>
        <button type="button" className="primary-button" onClick={askPublish} disabled={busy}>Publicar</button>
        <button type="button" className="danger-button" onClick={() => setIntent('delete')} disabled={busy}>Eliminar borrador</button>
      </>}
      {document.status === 'PUBLICADO' && <button type="button" className="secondary-button"
        onClick={() => setIntent('archive')} disabled={busy}>Archivar</button>}
    </div>
    {document.status === 'ARCHIVADO' && <p className="muted">Archivado: no admite nuevas acciones editoriales.</p>}
    {intent && <ConfirmDialog
      title={intent === 'publish' ? 'Publicar documento' : intent === 'archive' ? 'Archivar documento' : 'Eliminar borrador'}
      confirmLabel={intent === 'publish' ? 'Publicar ahora' : intent === 'archive' ? 'Archivar ahora' : 'Eliminar borrador'}
      danger={intent === 'delete'} busy={busy} onConfirm={confirmAction} onCancel={() => setIntent(null)}>
      {intent === 'publish' ? <p>{document.content_type === 'POST'
        ? 'Al publicar este post ya no podrá editarse. Se generarán el QMD y el sitio Quarto. ¿Deseas continuar?'
        : 'Se publicará este documento. ¿Deseas continuar?'}</p>
        : intent === 'archive' ? <p>¿Deseas archivar este documento? El estado administrativo cambiará, pero la retirada del sitio público aún no está automatizada.</p>
          : <p>Esta acción eliminará el borrador. ¿Deseas continuar?</p>}
    </ConfirmDialog>}
  </>
}
