import { ApiError } from '../api/http'

export function dataErrorMessage(error) {
  if (error instanceof ApiError && error.status === 0) return 'No fue posible conectar con el CMS.'
  if (error instanceof ApiError && error.status === 403) return 'No tienes permiso para ver estos datos.'
  return 'No fue posible cargar los datos. Inténtalo de nuevo.'
}

export function ErrorNotice({ message }) {
  return <p className="notice error-notice" role="alert">{message}</p>
}
