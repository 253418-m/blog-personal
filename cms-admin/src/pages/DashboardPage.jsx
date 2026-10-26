import { getDocuments } from '../api/documents'
import { getTemplates } from '../api/templates'
import { dataErrorMessage, ErrorNotice } from '../components/ErrorNotice'
import { StatusBadge } from '../components/StatusBadge'
import { useApiData } from '../hooks/useApiData'
import { formatDate } from '../utils/format'

async function loadDashboard() {
  const [documents, templates] = await Promise.all([getDocuments(), getTemplates()])
  return { documents, templates }
}

export function DashboardPage() {
  const { loading, data, error } = useApiData(loadDashboard)

  if (loading) return <p className="page-status" role="status">Cargando resumen del CMS…</p>
  if (error) return <ErrorNotice message={dataErrorMessage(error)} />

  const { documents, templates } = data
  const metrics = [
    { label: 'Borradores', value: documents.filter((item) => item.status === 'BORRADOR').length },
    { label: 'Publicados', value: documents.filter((item) => item.status === 'PUBLICADO').length },
    { label: 'Archivados', value: documents.filter((item) => item.status === 'ARCHIVADO').length },
    { label: 'Plantillas', value: templates.length },
  ]
  const recent = [...documents]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 5)

  return (
    <>
      <div className="page-heading">
        <span className="eyebrow">Vista general</span>
        <h1>Dashboard</h1>
        <p>Estado actual del contenido y las plantillas del CMS.</p>
      </div>
      <section className="metrics-grid" aria-label="Resumen editorial">
        {metrics.map(({ label, value }) => (
          <article className="metric-card" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>
      <section className="panel" aria-labelledby="recent-title">
        <div className="panel-heading"><h2 id="recent-title">Documentos recientes</h2></div>
        {recent.length === 0 ? <p className="empty-state">Todavía no hay documentos.</p> : (
          <ul className="recent-list">
            {recent.map((item) => (
              <li key={item.document_id}>
                <div><strong>{item.title}</strong><span>{item.content_type} · {formatDate(item.updated_at)}</span></div>
                <StatusBadge status={item.status} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
