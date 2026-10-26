import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { ProtectedRoute, SessionStatus } from './auth/ProtectedRoute'
import { AdminLayout } from './components/layout/AdminLayout'
import { ContentPage } from './pages/ContentPage'
import { DashboardPage } from './pages/DashboardPage'
import { DocumentDetailPage } from './pages/DocumentDetailPage'
import { EditTemplatePage } from './pages/EditTemplatePage'
import { EditDocumentPage } from './pages/EditDocumentPage'
import { LoginPage } from './pages/LoginPage'
import { NewPostPage } from './pages/NewPostPage'
import { NewTemplatePage } from './pages/NewTemplatePage'
import { TemplateDetailPage } from './pages/TemplateDetailPage'
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
              <Route path="/contenido/nuevo" element={<NewPostPage />} />
              <Route path="/contenido/:documentId" element={<DocumentDetailPage />} />
              <Route path="/contenido/:documentId/editar" element={<EditDocumentPage />} />
              <Route path="/plantillas" element={<TemplatesPage />} />
              <Route path="/plantillas/nueva" element={<NewTemplatePage />} />
              <Route path="/plantillas/:templateId" element={<TemplateDetailPage />} />
              <Route path="/plantillas/:templateId/editar" element={<EditTemplatePage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
