import { useCallback, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getTemplate, updateTemplate } from '../api/templates'
import { ApiError } from '../api/http'
import { ErrorNotice } from '../components/ErrorNotice'
import { TemplateForm } from '../components/TemplateForm'
import { useApiData } from '../hooks/useApiData'

export function EditTemplatePage() {
  const { templateId } = useParams()
  const navigate = useNavigate()
  const load = useCallback(() => getTemplate(templateId), [templateId])
  const { loading, data: template, error } = useApiData(load)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  async function save(payload) {
    setSaving(true)
    setSaveError('')
    try {
      await updateTemplate(templateId, payload)
      navigate(`/plantillas/${templateId}`, { replace: true, state: { flash: 'Plantilla actualizada.' } })
    } catch (failure) {
      setSaveError(failure instanceof ApiError && failure.status === 409
        ? 'Ya existe una plantilla con ese nombre.'
        : failure instanceof ApiError && failure.status === 422
          ? 'Revisa los campos y la predeterminada: debe permanecer una plantilla predeterminada.'
          : 'No fue posible guardar los cambios.')
    } finally {
      setSaving(false)
    }
  }

  return <>
    <div className="page-heading">
      <Link className="back-link" to={`/plantillas/${templateId}`}>← Volver a la plantilla</Link>
      <span className="eyebrow">Estructura editorial</span>
      <h1>Editar plantilla</h1>
    </div>
    {loading ? <p className="page-status" role="status">Cargando plantilla…</p>
      : error ? <ErrorNotice message="No fue posible cargar la plantilla." />
        : !template ? <div className="panel empty-state">Plantilla no encontrada. <Link to="/plantillas">Volver a Plantillas</Link></div>
          : <TemplateForm key={templateId} initialTemplate={template} onSubmit={save} saving={saving} error={saveError} />}
  </>
}
