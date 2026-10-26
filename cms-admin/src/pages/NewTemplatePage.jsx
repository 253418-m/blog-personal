import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createTemplate, getTemplates } from '../api/templates'
import { ApiError } from '../api/http'
import { ErrorNotice } from '../components/ErrorNotice'
import { TemplateForm } from '../components/TemplateForm'
import { useApiData } from '../hooks/useApiData'

export function NewTemplatePage() {
  const navigate = useNavigate()
  const { loading, data: templates, error } = useApiData(getTemplates)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  async function save(payload) {
    setSaving(true)
    setSaveError('')
    try {
      const result = await createTemplate(payload)
      navigate(`/plantillas/${result.template_id}`, { replace: true, state: { flash: 'Plantilla creada.' } })
    } catch (failure) {
      setSaveError(failure instanceof ApiError && failure.status === 409
        ? 'Ya existe una plantilla con ese nombre.'
        : failure instanceof ApiError && failure.status === 422
          ? 'Revisa los campos, la estructura y la plantilla predeterminada.'
          : 'No fue posible crear la plantilla.')
    } finally {
      setSaving(false)
    }
  }

  return <>
    <div className="page-heading">
      <Link className="back-link" to="/plantillas">← Volver a Plantillas</Link>
      <span className="eyebrow">Estructura editorial</span>
      <h1>Nueva plantilla</h1>
    </div>
    {loading ? <p className="page-status" role="status">Cargando plantillas…</p>
      : error ? <ErrorNotice message="No fue posible comprobar las plantillas existentes." />
        : <TemplateForm firstTemplate={templates.length === 0} onSubmit={save} saving={saving} error={saveError} />}
  </>
}
