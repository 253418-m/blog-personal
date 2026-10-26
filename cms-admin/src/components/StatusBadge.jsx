const STATUS_LABELS = {
  BORRADOR: 'Borrador',
  PUBLICADO: 'Publicado',
  ARCHIVADO: 'Archivado',
}

export function StatusBadge({ status }) {
  return <span className={`status-badge status-${status?.toLowerCase() || 'unknown'}`}>
    {STATUS_LABELS[status] || status}
  </span>
}
