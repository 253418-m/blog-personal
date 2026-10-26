import { useCallback, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { deleteTemplate, getTemplate, getTemplates } from '../api/templates'
import { ApiError } from '../api/http'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorNotice } from '../components/ErrorNotice'
import { Feedback } from '../components/Feedback'
import { targetTypeLabel } from '../components/TemplateForm'
import { useApiData } from '../hooks/useApiData'
import { formatDate } from '../utils/format'
import { metadataLabel } from '../utils/metadataLabel'

const DATA_TYPES = { STRING: 'Texto', INTEGER: 'Número entero', BOOLEAN: 'Sí / No', DATE: 'Fecha' }

export function TemplateDetailPage() {
  const { templateId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const load = useCallback(() => getTemplate(templateId), [templateId])
  const { loading, data: template, error } = useApiData(load)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')

  async function remove() {
    setBusy(true)
    setFeedback('')
    try {
      await deleteTemplate(templateId)
      navigate('/plantillas', { replace: true, state: { flash: 'Plantilla eliminada.' } })
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 409) {
        try {
          const templates = await getTemplates()
          setFeedback(templates.length === 1
            ? 'No se puede eliminar la última plantilla.'
            : 'No se puede eliminar esta plantilla porque está siendo utilizada por uno o más documentos.')
        } catch {
          setFeedback('No se puede eliminar esta plantilla. Comprueba si está en uso o es la última.')
        }
      } else {
        setFeedback('No fue posible eliminar la plantilla.')
      }
    } finally {
      setBusy(false)
      setConfirmDelete(false)
    }
  }

  if (loading) return <p className="page-status" role="status">Cargando plantilla…</p>
  if (error) return <ErrorNotice message="No fue posible cargar la plantilla." />
  if (!template) return <div className="panel empty-state">Plantilla no encontrada. <Link to="/plantillas">Volver a Plantillas</Link></div>

  return <>
    <div className="page-heading">
      <Link className="back-link" to="/plantillas">← Volver a Plantillas</Link>
      <span className="eyebrow">Estructura editorial</span>
      <h1>{template.name}</h1>
    </div>
    {location.state?.flash && <Feedback tone="success">{location.state.flash}</Feedback>}
    {feedback && <Feedback tone="error">{feedback}</Feedback>}
    <section className="panel detail-panel" aria-label="Detalle de la plantilla">
      <dl className="detail-grid">
        <div><dt>Tipo de contenido</dt><dd>{targetTypeLabel(template.target_type)}</dd></div>
        <div><dt>Plantilla predeterminada</dt><dd>{template.is_default ? 'Sí' : 'No'}</dd></div>
        <div><dt>Permitir edición después de publicar</dt><dd>{template.allow_published_edit ? 'Sí' : 'No'}</dd></div>
        <div><dt>Creada</dt><dd>{formatDate(template.created_at)}</dd></div>
      </dl>
      <h2>Campos adicionales</h2>
      <div className="table-scroll"><table>
        <thead><tr><th scope="col">Nombre visible</th><th scope="col">Identificador del campo</th>
          <th scope="col">Tipo de dato</th><th scope="col">Obligatorio al publicar</th></tr></thead>
        <tbody>{template.metadata_contract.map((field) => <tr key={field.field_key}>
          <td>{metadataLabel(field.field_key)}</td><td>{field.field_key}</td>
          <td>{DATA_TYPES[field.expected_type] || field.expected_type}</td>
          <td>{field.is_required ? 'Sí' : 'No'}</td>
        </tr>)}</tbody>
      </table></div>
      <h2>Estructura de contenido</h2>
      <pre className="content-text">{JSON.stringify(template.layout_structure, null, 2)}</pre>
    </section>
    <div className="detail-actions">
      <Link className="secondary-button button-link" to={`/plantillas/${templateId}/editar`}>Editar</Link>
      <button type="button" className="danger-button" onClick={() => setConfirmDelete(true)}>Eliminar plantilla</button>
    </div>
    {confirmDelete && <ConfirmDialog title="Eliminar plantilla" confirmLabel="Eliminar plantilla" danger
      busy={busy} onConfirm={remove} onCancel={() => setConfirmDelete(false)}>
      <p>La plantilla solo podrá eliminarse si no está siendo utilizada por documentos. ¿Deseas continuar?</p>
    </ConfirmDialog>}
  </>
}
