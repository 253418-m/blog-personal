import { apiRequest } from './http'

const documentPath = (id) => `/api/v1/documents/${encodeURIComponent(id)}`

export async function getDocuments({ status, content_type } = {}) {
  const query = new URLSearchParams()
  if (status) query.set('status', status)
  if (content_type) query.set('content_type', content_type)
  const response = await apiRequest(`/api/v1/documents${query.size ? `?${query}` : ''}`)
  if (!Array.isArray(response?.items)) throw new Error('Respuesta de Documents inválida.')
  return response.items
}

export const getDocument = (id) => apiRequest(documentPath(id))
export const createDocument = (payload) => apiRequest('/api/v1/documents', { method: 'POST', body: payload })
export const updateDocument = (id, payload) => apiRequest(documentPath(id), { method: 'PUT', body: payload })
export const publishDocument = (id) => apiRequest(`${documentPath(id)}/publish`, { method: 'POST' })
export const archiveDocument = (id) => apiRequest(`${documentPath(id)}/archive`, { method: 'POST' })
export const deleteDocument = (id) => apiRequest(documentPath(id), { method: 'DELETE' })
