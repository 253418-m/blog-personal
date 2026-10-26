import { apiRequest } from './http'

export async function getTemplates({ target_type } = {}) {
  const query = new URLSearchParams()
  if (target_type) query.set('target_type', target_type)
  const response = await apiRequest(`/api/v1/templates${query.size ? `?${query}` : ''}`)
  if (!Array.isArray(response?.items)) throw new Error('Respuesta de Templates inválida.')
  return response.items
}

const templatePath = (id) => `/api/v1/templates/${encodeURIComponent(id)}`

export async function getTemplate(id) {
  const templates = await getTemplates()
  return templates.find((item) => item.template_id === id) || null
}

export const createTemplate = (payload) => apiRequest('/api/v1/templates', { method: 'POST', body: payload })
export const updateTemplate = (id, payload) => apiRequest(templatePath(id), { method: 'PUT', body: payload })
export const deleteTemplate = (id) => apiRequest(templatePath(id), { method: 'DELETE' })
