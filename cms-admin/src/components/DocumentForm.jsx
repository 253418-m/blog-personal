import { useState } from 'react'
import { buildMetadataValues, SLUG_PATTERN, suggestSlug } from '../utils/documentForm'
import { metadataLabel } from '../utils/metadataLabel'
import { Feedback } from './Feedback'
import { HelpTooltip } from './HelpTooltip'

const metadataHelp = {
  category: 'Tema principal al que pertenece el artículo.',
  reading_time: 'Tiempo aproximado que necesita una persona para leer el artículo.',
}

function MetadataFields({ contract, values, errors, onChange, isPost }) {
  return <fieldset className="metadata-fields">
    <legend><span className="field-label-row">{isPost ? 'Datos del artículo' : 'Datos de la página'}
      <HelpTooltip text="Información adicional utilizada para clasificar y describir el contenido." />
    </span></legend>
    {contract.map((field) => {
      const id = `metadata-${field.field_key}`
      const hint = field.is_required ? 'Obligatorio al publicar' : 'Opcional'
      const label = metadataLabel(field.field_key)
      const help = field.field_key === 'category' && !isPost
        ? 'Tema principal al que pertenece la página.'
        : metadataHelp[field.field_key] || 'Campo adicional definido por la plantilla seleccionada.'
      const describedBy = [field.field_key === 'reading_time' && `${id}-unit`, errors[field.field_key] && `${id}-error`]
        .filter(Boolean).join(' ') || undefined
      return <div className="form-field" key={field.field_key}>
        {field.expected_type === 'BOOLEAN' ? (
          <>
            <div className="field-label-row">
              <label className="checkbox-label" htmlFor={id}>
                <input id={id} type="checkbox" checked={values[field.field_key] === true}
                  onChange={(event) => onChange(field.field_key, event.target.checked)} />
                <span>{label}</span>
              </label>
              <HelpTooltip text={help} />
            </div>
            <small className="field-status">{hint}</small>
          </>
        ) : (
          <>
            <div className="field-label-row">
              <label htmlFor={id}>{label}</label>
              <HelpTooltip text={help} />
            </div>
            <small className="field-status">{hint}</small>
            <div className={field.field_key === 'reading_time' ? 'field-with-unit' : undefined}>
              <input id={id} type={field.expected_type === 'INTEGER' ? 'number' :
                field.expected_type === 'DATE' ? 'date' : 'text'}
                step={field.expected_type === 'INTEGER' ? '1' : undefined}
                placeholder={field.field_key === 'category' ? 'Programación' : undefined}
                value={values[field.field_key] ?? ''}
                aria-invalid={Boolean(errors[field.field_key])} aria-describedby={describedBy}
                onChange={(event) => onChange(field.field_key, event.target.value)} />
              {field.field_key === 'reading_time' && <span id={`${id}-unit`} className="field-unit">minutos</span>}
            </div>
            {errors[field.field_key] && <small id={`${id}-error`} className="field-error">{errors[field.field_key]}</small>}
          </>
        )}
      </div>
    })}
  </fieldset>
}

export function DocumentForm({ templates, initialDocument, onSubmit, saving = false, error = '' }) {
  const [title, setTitle] = useState(initialDocument?.title || '')
  const [slug, setSlug] = useState(initialDocument?.slug || '')
  const [slugEdited, setSlugEdited] = useState(Boolean(initialDocument))
  const [templateId, setTemplateId] = useState(initialDocument?.template_id ||
    templates.find((item) => item.is_default)?.template_id || templates[0]?.template_id || '')
  const [metadata, setMetadata] = useState(initialDocument?.metadata_values || {})
  const [content, setContent] = useState(initialDocument?.content || '')
  const [errors, setErrors] = useState({})
  const selected = templates.find((item) => item.template_id === templateId)
  const isPost = !initialDocument || initialDocument.content_type === 'POST'

  function changeTitle(value) {
    setTitle(value)
    if (!slugEdited) setSlug(suggestSlug(value))
  }

  function changeTemplate(value) {
    setTemplateId(value)
    setMetadata({})
    setErrors({})
  }

  function handleSubmit(event) {
    event.preventDefault()
    if (saving) return
    const nextErrors = {}
    if (!title.trim()) nextErrors.title = 'Escribe un título.'
    if (!SLUG_PATTERN.test(slug)) nextErrors.slug = 'Usa minúsculas, números y guiones simples.'
    if (!selected) nextErrors.template_id = 'Selecciona una plantilla.'
    const { metadata: metadata_values, errors: metadataErrors } = buildMetadataValues(
      selected?.metadata_contract || [], metadata,
    )
    Object.assign(nextErrors, metadataErrors)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return
    onSubmit({ title: title.trim(), slug, template_id: templateId, metadata_values, content,
      ...(initialDocument ? {} : { content_type: 'POST' }) })
  }

  return <form className="document-form panel" onSubmit={handleSubmit} noValidate>
    <div className="form-note">
      <p>Tipo: <strong>{isPost ? 'Artículo / Post' : 'Página / Landing'}</strong></p>
      {isPost && <p>Este contenido se publicará como un artículo dentro de la sección Contenido del sitio.</p>}
      <p>{initialDocument ? 'Estás editando un borrador.' : 'Estás creando un artículo.'} Puedes guardarlo como borrador aunque todavía falte información; los campos obligatorios se validarán al publicarlo.</p>
    </div>
    <div className="form-grid">
      <div className="form-field">
        <div className="field-label-row"><label htmlFor="document-title">Título</label>
          <HelpTooltip text={`Es el nombre principal que verán los visitantes en ${isPost ? 'el artículo' : 'la página'}.`} />
        </div>
        <input id="document-title" value={title} aria-invalid={Boolean(errors.title)}
          aria-describedby={errors.title ? 'title-error' : undefined} onChange={(event) => changeTitle(event.target.value)} />
        {errors.title && <small id="title-error" className="field-error">{errors.title}</small>}
      </div>
      <div className="form-field">
        <div className="field-label-row"><label htmlFor="document-slug">Identificador URL</label>
          <HelpTooltip text={`Define la dirección web ${isPost ? 'del artículo' : 'de la página'}. Se genera automáticamente a partir del título y puedes modificarlo mientras ${isPost ? 'el post' : 'la página'} siga siendo un borrador.`} />
        </div>
        <input id="document-slug" value={slug} aria-invalid={Boolean(errors.slug)}
          aria-describedby={[isPost && 'slug-preview', errors.slug && 'slug-error'].filter(Boolean).join(' ') || undefined}
          onChange={(event) => { setSlugEdited(true); setSlug(event.target.value) }} />
        {isPost && <small id="slug-preview" className="field-hint">Dirección: <output htmlFor="document-slug">/posts/{slug || '...'}/</output></small>}
        {errors.slug && <small id="slug-error" className="field-error">{errors.slug}</small>}
      </div>
    </div>
    <div className="form-field">
      <div className="field-label-row"><label htmlFor="document-template">Plantilla</label>
        <HelpTooltip text={`La plantilla define qué información adicional debe tener ${isPost ? 'este artículo' : 'esta página'}. Los campos de abajo cambian según la plantilla seleccionada.`} />
      </div>
      <select id="document-template" value={templateId} aria-invalid={Boolean(errors.template_id)}
        aria-describedby={errors.template_id ? 'template-error' : undefined}
        onChange={(event) => changeTemplate(event.target.value)}>
        {templates.map((item) => <option key={item.template_id} value={item.template_id}>{item.name}</option>)}
      </select>
      {errors.template_id && <small id="template-error" className="field-error">{errors.template_id}</small>}
    </div>
    <MetadataFields contract={selected?.metadata_contract || []} values={metadata} errors={errors} isPost={isPost}
      onChange={(key, value) => setMetadata((current) => ({ ...current, [key]: value }))} />
    <div className="form-field">
      <div className="field-label-row"><label htmlFor="document-content">Contenido</label>
        <HelpTooltip text={`Escribe el cuerpo ${isPost ? 'del artículo' : 'de la página'}. Puedes utilizar Markdown y sintaxis Quarto.`} />
      </div>
      <textarea id="document-content" rows="18" value={content}
        onChange={(event) => setContent(event.target.value)} />
    </div>
    <Feedback tone="error">{error}</Feedback>
    <div className="form-actions">
      <button type="submit" className="primary-button" disabled={saving}>
        {saving ? 'Guardando…' : 'Guardar borrador'}
      </button>
    </div>
  </form>
}
