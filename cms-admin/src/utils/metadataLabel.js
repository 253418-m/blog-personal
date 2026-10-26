const metadataLabels = {
  category: 'Categoría',
  reading_time: 'Tiempo de lectura',
}

export function metadataLabel(fieldKey) {
  return metadataLabels[fieldKey] || fieldKey.replace(/[_-]+/g, ' ').replace(/^./, (letter) => letter.toUpperCase())
}
