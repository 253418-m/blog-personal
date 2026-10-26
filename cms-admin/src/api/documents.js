import { apiRequest } from './http'

export async function getDocuments() {
  const response = await apiRequest('/api/v1/documents')
  if (!Array.isArray(response?.items)) throw new Error('Respuesta de Documents inválida.')
  return response.items
}
