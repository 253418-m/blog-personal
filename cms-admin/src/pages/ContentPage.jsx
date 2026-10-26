import { useState } from 'react'
import { getDocuments } from '../api/documents'
import { dataErrorMessage, ErrorNotice } from '../components/ErrorNotice'
import { StatusBadge } from '../components/StatusBadge'
import { useApiData } from '../hooks/useApiData'
import { formatDate } from '../utils/format'

const FILTERS = [
  { label: 'Todos', value: 'TODOS' },
  { label: 'Borradores', value: 'BORRADOR' },
  { label: 'Publicados', value: 'PUBLICADO' },
  { label: 'Archivados', value: 'ARCHIVADO' },
]

export function ContentPage() {
  const { loading, data: documents, error } = useApiData(getDocuments)
  const [filter, setFilter] = useState('TODOS')

  if (loading) return <p className="page-status" role="status">Cargando documentos…</p>
  if (error) return <ErrorNotice message={dataErrorMessage(error)} />

  const visible = filter === 'TODOS' ? documents : documents.filter((item) => item.status === filter)
  return (
    <>
      <div className="page-heading">
        <span className="eyebrow">Biblioteca editorial</span>
        <h1>Contenido</h1>
        <p>Consulta los Documents disponibles y su estado de publicación.</p>
      </div>
      <section className="panel" aria-label="Lista de documentos">
        <div className="filter-bar" role="group" aria-label="Filtrar documentos por estado">
          {FILTERS.map(({ label, value }) => (
            <button key={value} type="button" aria-pressed={filter === value}
              className={filter === value ? 'filter-button selected' : 'filter-button'}
              onClick={() => setFilter(value)}>{label}</button>
          ))}
        </div>
        {visible.length === 0 ? <p className="empty-state">
          {documents.length === 0 ? 'Todavía no hay documentos.' : 'No hay documentos en este estado.'}
        </p> : (
          <div className="table-scroll"><table>
            <thead><tr><th scope="col">Título</th><th scope="col">Tipo</th>
              <th scope="col">Estado</th><th scope="col">Actualizado</th></tr></thead>
            <tbody>{visible.map((item) => (
              <tr key={item.document_id}>
                <td className="title-cell">{item.title}</td>
                <td>{item.content_type}</td>
                <td><StatusBadge status={item.status} /></td>
                <td>{formatDate(item.updated_at)}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </section>
    </>
  )
}
