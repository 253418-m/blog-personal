import { useCallback, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { getTemplates } from '../api/templates'
import { ErrorNotice } from '../components/ErrorNotice'
import { Feedback } from '../components/Feedback'
import { targetTypeLabel } from '../components/TemplateForm'
import { useApiData } from '../hooks/useApiData'
import { formatDate } from '../utils/format'

export function TemplatesPage() {
  const location = useLocation()
  const [targetType, setTargetType] = useState('')
  const load = useCallback(() => getTemplates({ target_type: targetType }), [targetType])
  const { loading, data: templates, error } = useApiData(load)

  return <>
    <div className="page-heading content-heading">
      <div>
        <span className="eyebrow">Estructura editorial</span>
        <h1>Plantillas</h1>
        <p>Las plantillas definen qué información debe completar cada tipo de contenido.</p>
      </div>
      <Link className="primary-button button-link" to="/plantillas/nueva">+ Nueva plantilla</Link>
    </div>
    <p className="muted">Las plantillas de artículos se utilizan en Contenido. Las de páginas servirán para administrar Inicio y Sobre mí cuando exista el editor LANDING.</p>
    {location.state?.flash && <Feedback tone="success">{location.state.flash}</Feedback>}
    <section className="panel" aria-label="Lista de plantillas">
      <div className="filter-bar" role="group" aria-label="Filtrar plantillas por tipo">
        {[
          { value: '', label: 'Todas' },
          { value: 'POST', label: 'Para artículos' },
          { value: 'LANDING', label: 'Para páginas' },
        ].map(({ value, label }) => <button key={value} type="button" aria-pressed={targetType === value}
          className={targetType === value ? 'filter-button selected' : 'filter-button'}
          onClick={() => setTargetType(value)}>{label}</button>)}
      </div>
      {loading ? <p className="page-status" role="status">Cargando plantillas…</p>
        : error ? <ErrorNotice message="No fue posible cargar las plantillas." />
          : templates.length === 0 ? <p className="empty-state">No hay plantillas para este filtro.</p>
            : <div className="table-scroll"><table className="template-table">
              <thead><tr><th scope="col">Nombre</th><th scope="col">Tipo</th>
                <th scope="col">Predeterminada</th><th scope="col">Edición después de publicar</th>
                <th scope="col">Campos adicionales</th><th scope="col">Creada</th><th scope="col">Acciones</th></tr></thead>
              <tbody>{templates.map((item) => <tr key={item.template_id}>
                <td className="title-cell" data-label="Nombre">{item.name}</td>
                <td data-label="Tipo">{targetTypeLabel(item.target_type)}</td>
                <td data-label="Predeterminada">{item.is_default ? 'Sí' : 'No'}</td>
                <td data-label="Edición publicada">{item.allow_published_edit ? 'Permitida' : 'No permitida'}</td>
                <td data-label="Campos adicionales">{item.metadata_contract.length}</td>
                <td data-label="Creada">{formatDate(item.created_at)}</td>
                <td data-label="Acciones"><div className="row-actions">
                  <Link to={`/plantillas/${item.template_id}`}>Ver</Link>
                  <Link to={`/plantillas/${item.template_id}/editar`}>Editar</Link>
                </div></td>
              </tr>)}</tbody>
            </table></div>}
    </section>
  </>
}
