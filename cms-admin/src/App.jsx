import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { ProtectedRoute, SessionStatus } from './auth/ProtectedRoute'
import { AdminLayout } from './components/layout/AdminLayout'
import { ContentPage } from './pages/ContentPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { TemplatesPage } from './pages/TemplatesPage'

function HomeRoute() {
  const { status } = useAuth()
  if (status === 'checking' || status === 'error') return <SessionStatus />
  return <Navigate to={status === 'authenticated' ? '/dashboard' : '/login'} replace />
}

function LoginRoute() {
  const { status } = useAuth()
  if (status === 'checking') return <SessionStatus />
  return status === 'authenticated' ? <Navigate to="/dashboard" replace /> : <LoginPage />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<HomeRoute />} />
          <Route path="/login" element={<LoginRoute />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AdminLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/contenido" element={<ContentPage />} />
              <Route path="/plantillas" element={<TemplatesPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
