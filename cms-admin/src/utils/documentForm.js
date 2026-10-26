export const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

export function suggestSlug(title) {
  return title.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

export function buildMetadataValues(contract, values) {
  const metadata = {}
  const errors = {}
  for (const field of contract) {
    const value = values[field.field_key]
    if (field.expected_type === 'BOOLEAN') {
      metadata[field.field_key] = value === true
    } else if (value !== undefined && String(value).trim() !== '') {
      if (field.expected_type === 'INTEGER') {
        const integer = String(value).trim()
        if (!/^-?\d+$/.test(integer) || !Number.isSafeInteger(Number(integer))) {
          errors[field.field_key] = 'Escribe un número entero válido.'
        } else metadata[field.field_key] = Number(integer)
      } else {
        metadata[field.field_key] = String(value).trim()
      }
    }
  }
  return { metadata, errors }
}

export function missingPublishFields(document, template) {
  const missing = []
  if (!document.title?.trim()) missing.push('título')
  if (!document.content?.trim()) missing.push('contenido')
  for (const field of template?.metadata_contract || []) {
    const value = document.metadata_values?.[field.field_key]
    if (field.is_required && (value === undefined || value === null ||
        (typeof value === 'string' && !value.trim()))) missing.push(field.field_key)
  }
  return missing
}
