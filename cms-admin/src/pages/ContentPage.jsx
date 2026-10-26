import { useCallback, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { getDocuments } from '../api/documents'
import { dataErrorMessage, ErrorNotice } from '../components/ErrorNotice'
import { Feedback } from '../components/Feedback'
import { StatusBadge } from '../components/StatusBadge'
import { useApiData } from '../hooks/useApiData'
import { formatDate } from '../utils/format'

const FILTERS = [
  { label: 'Todos', value: '' },
  { label: 'Borradores', value: 'BORRADOR' },
  { label: 'Publicados', value: 'PUBLICADO' },
  { label: 'Archivados', value: 'ARCHIVADO' },
]

export function ContentPage() {
  const location = useLocation()
  const [status, setStatus] = useState('')
  const [contentType, setContentType] = useState('')
  const load = useCallback(() => getDocuments({ status, content_type: contentType }), [status, contentType])
  const { loading, data: documents, error } = useApiData(load)

  return <>
    <div className="page-heading content-heading">
      <div>
        <span className="eyebrow">Biblioteca editorial</span>
        <h1>Contenido</h1>
        <p>Consulta y administra los Documents del CMS.</p>
      </div>
      <Link className="primary-button button-link" to="/contenido/nuevo">+ Nuevo post</Link>
    </div>
    {location.state?.flash && <Feedback tone="success">{location.state.flash}</Feedback>}
    <section className="panel" aria-label="Lista de documentos">
      <div className="content-filters">
        <div className="filter-bar" role="group" aria-label="Filtrar documentos por estado">
          {FILTERS.map(({ label, value }) => (
            <button key={label} type="button" aria-pressed={status === value}
              className={status === value ? 'filter-button selected' : 'filter-button'}
              onClick={() => setStatus(value)}>{label}</button>
          ))}
        </div>
        <label className="type-filter" htmlFor="type-filter">Tipo
          <select id="type-filter" value={contentType} onChange={(event) => setContentType(event.target.value)}>
            <option value="">Todos</option>
            <option value="POST">POST</option>
            <option value="LANDING">LANDING</option>
          </select>
        </label>
      </div>
      {loading ? <p className="page-status" role="status">Cargando documentos…</p>
        : error ? <ErrorNotice message={dataErrorMessage(error)} />
          : documents.length === 0 ? <p className="empty-state">No hay documentos para estos filtros.</p>
            : <div className="table-scroll"><table className="document-table">
              <thead><tr><th scope="col">Título</th><th scope="col">Tipo</th><th scope="col">Estado</th>
                <th scope="col">Actualizado</th><th scope="col">Publicado</th><th scope="col">Acciones</th></tr></thead>
              <tbody>{documents.map((item) => (
                <tr key={item.document_id}>
                  <td className="title-cell" data-label="Título">{item.title}</td>
                  <td data-label="Tipo">{item.content_type}</td>
                  <td data-label="Estado"><StatusBadge status={item.status} /></td>
                  <td data-label="Actualizado">{formatDate(item.updated_at)}</td>
                  <td data-label="Publicado">{formatDate(item.published_at)}</td>
                  <td data-label="Acciones"><div className="row-actions">
                    <Link to={`/contenido/${item.document_id}`}>Ver</Link>
                    {item.status === 'BORRADOR' && <>
                      <Link to={`/contenido/${item.document_id}/editar`}>Editar</Link>
                      <Link to={`/contenido/${item.document_id}`} state={{ intent: 'publish' }}>Publicar</Link>
                      <Link className="danger-link" to={`/contenido/${item.document_id}`} state={{ intent: 'delete' }}>Eliminar</Link>
                    </>}
                    {item.status === 'PUBLICADO' && <Link to={`/contenido/${item.document_id}`}
                      state={{ intent: 'archive' }}>Archivar</Link>}
                  </div></td>
                </tr>
              ))}</tbody>
            </table></div>}
    </section>
  </>
}
