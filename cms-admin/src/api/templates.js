import { apiRequest } from './http'

export async function getTemplates() {
  const response = await apiRequest('/api/v1/templates')
  if (!Array.isArray(response?.items)) throw new Error('Respuesta de Templates inválida.')
  return response.items
}
