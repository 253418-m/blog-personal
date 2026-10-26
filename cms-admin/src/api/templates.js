import { apiRequest } from './http'

export async function getTemplates({ target_type } = {}) {
  const query = new URLSearchParams()
  if (target_type) query.set('target_type', target_type)
  const response = await apiRequest(`/api/v1/templates${query.size ? `?${query}` : ''}`)
  if (!Array.isArray(response?.items)) throw new Error('Respuesta de Templates inválida.')
  return response.items
}
