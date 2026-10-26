import { getTemplates } from '../api/templates'
import { dataErrorMessage, ErrorNotice } from '../components/ErrorNotice'
import { useApiData } from '../hooks/useApiData'

export function TemplatesPage() {
  const { loading, data: templates, error } = useApiData(getTemplates)

  if (loading) return <p className="page-status" role="status">Cargando plantillas…</p>
  if (error) return <ErrorNotice message={dataErrorMessage(error)} />

  return (
    <>
      <div className="page-heading">
        <span className="eyebrow">Estructura editorial</span>
        <h1>Plantillas</h1>
        <p>Contratos disponibles para los Documents del CMS.</p>
      </div>
      <section className="panel" aria-label="Lista de plantillas">
        {templates.length === 0 ? <p className="empty-state">Todavía no hay plantillas.</p> : (
          <div className="table-scroll"><table>
            <thead><tr><th scope="col">Nombre</th><th scope="col">Tipo</th>
              <th scope="col">Predeterminada</th><th scope="col">Edición publicada</th>
              <th scope="col">Metadatos</th></tr></thead>
            <tbody>{templates.map((item) => (
              <tr key={item.template_id}>
                <td className="title-cell">{item.name}</td>
                <td>{item.target_type}</td>
                <td>{item.is_default ? 'Sí' : 'No'}</td>
                <td>{item.allow_published_edit ? 'Permitida' : 'No permitida'}</td>
                <td>{Array.isArray(item.metadata_contract) ? item.metadata_contract.length : 0}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </section>
    </>
  )
}
