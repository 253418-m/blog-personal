import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'

export function SessionStatus() {
  const { status, validateSession } = useAuth()
  if (status === 'checking') return <p className="screen-status" role="status">Validando sesión…</p>
  return (
    <div className="screen-status" role="alert">
      <p>No fue posible validar la sesión con el CMS.</p>
      <button type="button" onClick={validateSession}>Reintentar</button>
    </div>
  )
}

export function ProtectedRoute() {
  const { status } = useAuth()
  if (status === 'checking' || status === 'error') return <SessionStatus />
  return status === 'authenticated' ? <Outlet /> : <Navigate to="/login" replace />
}
