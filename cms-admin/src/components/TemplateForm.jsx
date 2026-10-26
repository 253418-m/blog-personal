import { useState } from 'react'
import { Feedback } from './Feedback'
import { metadataLabel } from '../utils/metadataLabel'

const DATA_TYPES = [
  { value: 'STRING', label: 'Texto' },
  { value: 'INTEGER', label: 'Número entero' },
  { value: 'BOOLEAN', label: 'Sí / No' },
  { value: 'DATE', label: 'Fecha' },
]

export function targetTypeLabel(type) {
  return type === 'POST' ? 'Artículos / Posts' : 'Páginas del sitio'
}

function blankField() {
  return { field_key: '', expected_type: 'STRING', is_required: false }
}

export function TemplateForm({ initialTemplate, firstTemplate = false, onSubmit, saving = false, error = '' }) {
  const editing = Boolean(initialTemplate)
  const [name, setName] = useState(initialTemplate?.name || '')
  const [targetType, setTargetType] = useState(initialTemplate?.target_type || 'POST')
  const [isDefault, setIsDefault] = useState(initialTemplate?.is_default ?? firstTemplate)
  const [allowPublishedEdit, setAllowPublishedEdit] = useState(initialTemplate?.allow_published_edit || false)
  const [fields, setFields] = useState(initialTemplate?.metadata_contract?.map((item) => ({ ...item })) || [blankField()])
  const [layoutText, setLayoutText] = useState(JSON.stringify(initialTemplate?.layout_structure ?? {}, null, 2))
  const [errors, setErrors] = useState({})

  function changeField(index, key, value) {
    setFields((current) => current.map((item, position) => position === index ? { ...item, [key]: value } : item))
  }

  function submit(event) {
    event.preventDefault()
    if (saving) return
    const nextErrors = { fields: {} }
    if (!name.trim()) nextErrors.name = 'Escribe un nombre para la plantilla.'
    if (!fields.length) nextErrors.contract = 'Agrega al menos un campo adicional.'
    const usedKeys = new Set()
    const metadata_contract = fields.map((field, index) => {
      const fieldKey = field.field_key.trim()
      if (!fieldKey) nextErrors.fields[index] = 'Escribe el identificador del campo.'
      else if (usedKeys.has(fieldKey)) nextErrors.fields[index] = 'El identificador del campo está duplicado.'
      if (!DATA_TYPES.some((type) => type.value === field.expected_type)) {
        nextErrors.fields[index] = 'Selecciona un tipo de dato válido.'
      }
      usedKeys.add(fieldKey)
      return { field_key: fieldKey, expected_type: field.expected_type, is_required: field.is_required }
    })
    let layout_structure
    try {
      layout_structure = JSON.parse(layoutText)
      if (layout_structure === null || Array.isArray(layout_structure) || typeof layout_structure !== 'object') {
        nextErrors.layout = 'La estructura debe ser un objeto JSON válido.'
      }
    } catch {
      nextErrors.layout = 'La estructura debe ser un objeto JSON válido.'
    }
    setErrors(nextErrors)
    if (nextErrors.name || nextErrors.contract || Object.keys(nextErrors.fields).length || nextErrors.layout) return
    const payload = { name: name.trim(), is_default: isDefault, metadata_contract, layout_structure }
    if (!editing) {
      payload.target_type = targetType
      payload.allow_published_edit = allowPublishedEdit
    }
    onSubmit(payload)
  }

  return <form className="document-form panel" onSubmit={submit} noValidate>
    <div className="form-field">
      <label htmlFor="template-name">Nombre de la plantilla</label>
      <small id="template-name-help" className="field-hint">Nombre utilizado para identificar esta plantilla dentro del CMS.</small>
      <input id="template-name" value={name} placeholder="Plantilla Post"
        aria-invalid={Boolean(errors.name)}
        aria-describedby={errors.name ? 'template-name-help template-name-error' : 'template-name-help'}
        onChange={(event) => setName(event.target.value)} />
      {errors.name && <small id="template-name-error" className="field-error">{errors.name}</small>}
    </div>
    <div className="form-grid">
      <div className="form-field">
        {editing ? <>
          <span className="field-label">Tipo de contenido</span>
          <p className="readonly-value">{targetTypeLabel(targetType)} <small>No modificable</small></p>
        </> : <>
          <label htmlFor="template-target">Tipo de contenido</label>
          <small id="template-target-help" className="field-hint">Define qué clase de contenido puede utilizar esta plantilla.</small>
          <select id="template-target" value={targetType} aria-describedby="template-target-help"
            onChange={(event) => setTargetType(event.target.value)}>
            <option value="POST">Artículo / Post</option>
            <option value="LANDING">Página del sitio</option>
          </select>
        </>}
      </div>
      <div className="form-field">
        {editing ? <>
          <span className="field-label">Permitir edición después de publicar</span>
          <p className="readonly-value">{allowPublishedEdit ? 'Sí' : 'No'} <small>No modificable</small></p>
        </> : <>
          <label className="checkbox-label" htmlFor="template-published-edit">
            <input id="template-published-edit" type="checkbox" checked={allowPublishedEdit}
              onChange={(event) => setAllowPublishedEdit(event.target.checked)} />
            <span>Permitir edición después de publicar</span>
          </label>
          <small id="template-published-edit-help" className="field-hint">Indica si el contenido publicado puede seguir modificándose cuando las reglas del tipo de contenido lo permiten.</small>
        </>}
        {targetType === 'POST' && <small className="field-hint">Los artículos publicados son inmutables por regla de negocio, aunque esta opción esté activada.</small>}
      </div>
    </div>
    <div className="form-field">
      <label className="checkbox-label" htmlFor="template-default">
        <input id="template-default" type="checkbox" checked={isDefault}
          disabled={firstTemplate || (editing && initialTemplate.is_default)}
          onChange={(event) => setIsDefault(event.target.checked)} />
        <span>Plantilla predeterminada</span>
      </label>
      <small className="field-hint">Se seleccionará automáticamente al crear contenido de este tipo.</small>
      {firstTemplate && <small className="field-hint">La primera plantilla debe ser predeterminada.</small>}
      {editing && initialTemplate.is_default && <small className="field-hint">Para cambiar la predeterminada, activa otra plantilla.</small>}
      {isDefault && !firstTemplate && !(editing && initialTemplate.is_default) &&
        <small className="field-hint">La plantilla predeterminada actual dejará de serlo.</small>}
    </div>
    <fieldset className="metadata-fields template-metadata">
      <legend>Campos adicionales</legend>
      <p className="field-hint metadata-intro">Define la información adicional que deberá completar el administrador al crear contenido con esta plantilla.</p>
      {fields.map((field, index) => <div className="template-metadata-row" key={index}>
        <h3>Campo {index + 1}</h3>
        <div className="template-metadata-grid">
          <div className="form-field">
            <label htmlFor={`field-key-${index}`}>Identificador del campo</label>
            <small id={`field-key-help-${index}`} className="field-hint">Nombre interno utilizado por el CMS. Usa letras, números y guion bajo.</small>
            <input id={`field-key-${index}`} value={field.field_key} placeholder="category"
              aria-invalid={Boolean(errors.fields?.[index])}
              aria-describedby={errors.fields?.[index] ? `field-key-help-${index} field-key-error-${index}` : `field-key-help-${index}`}
              onChange={(event) => changeField(index, 'field_key', event.target.value)} />
            {errors.fields?.[index] && <small id={`field-key-error-${index}`} className="field-error">{errors.fields[index]}</small>}
            {field.field_key.trim() && <small className="field-hint">Se mostrará como: {metadataLabel(field.field_key.trim())}</small>}
          </div>
          <div className="form-field">
            <label htmlFor={`field-type-${index}`}>Tipo de dato</label>
            <select id={`field-type-${index}`} value={field.expected_type}
              onChange={(event) => changeField(index, 'expected_type', event.target.value)}>
              {DATA_TYPES.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <div className="form-field">
            <label className="checkbox-label" htmlFor={`field-required-${index}`}>
              <input id={`field-required-${index}`} type="checkbox" checked={field.is_required}
                onChange={(event) => changeField(index, 'is_required', event.target.checked)} />
              <span>Obligatorio al publicar</span>
            </label>
            <small className="field-hint">Si se activa, el contenido no podrá publicarse hasta completar este campo.</small>
          </div>
          <button type="button" className="secondary-button" onClick={() => setFields((current) => current.filter((_, position) => position !== index))}>Eliminar campo</button>
        </div>
      </div>)}
      {errors.contract && <small className="field-error">{errors.contract}</small>}
      <button type="button" className="secondary-button add-field-button" onClick={() => setFields((current) => [...current, blankField()])}>+ Agregar campo</button>
    </fieldset>
    <div className="form-field">
      <label htmlFor="template-layout">Estructura de contenido</label>
      <small id="template-layout-help" className="field-hint">Configuración interna que describe las secciones de esta plantilla. Escribe un objeto JSON.</small>
      <textarea id="template-layout" rows="9" value={layoutText} spellCheck="false"
        aria-invalid={Boolean(errors.layout)}
        aria-describedby={errors.layout ? 'template-layout-help template-layout-error' : 'template-layout-help'}
        onChange={(event) => setLayoutText(event.target.value)} />
      {errors.layout && <small id="template-layout-error" className="field-error">{errors.layout}</small>}
    </div>
    <Feedback tone="error">{error}</Feedback>
    <div className="form-actions"><button className="primary-button" type="submit" disabled={saving}>
      {saving ? 'Guardando…' : editing ? 'Guardar cambios' : 'Crear plantilla'}
    </button></div>
  </form>
}
