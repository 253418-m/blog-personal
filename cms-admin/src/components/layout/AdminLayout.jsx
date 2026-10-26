import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'

const NAVIGATION = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/contenido', label: 'Contenido' },
  { to: '/plantillas', label: 'Plantillas' },
]

export function AdminLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="admin-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">CMS</span>
          <span>Panel editorial</span>
        </div>
        <nav className="sidebar-nav" aria-label="Navegación administrativa">
          {NAVIGATION.map(({ to, label }) => (
            <NavLink key={to} to={to} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              {label}
            </NavLink>
          ))}
        </nav>
        <p className="sidebar-footnote">Administración privada</p>
      </aside>
      <div className="admin-workspace">
        <header className="topbar">
          <div>
            <span className="topbar-eyebrow">CMS personal</span>
            <strong>Administración de contenido</strong>
          </div>
          <div className="account-actions">
            <span className="account-name">{user?.username}</span>
            <button type="button" className="secondary-button" onClick={handleLogout}>Cerrar sesión</button>
          </div>
        </header>
        <main className="admin-main"><Outlet /></main>
      </div>
    </div>
  )
}
