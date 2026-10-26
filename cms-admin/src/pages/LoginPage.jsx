import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api/http'
import { useAuth } from '../auth/AuthContext'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()
    if (loading) return
    const form = event.currentTarget
    const fields = new FormData(form)
    const username = String(fields.get('username') || '').trim()
    const password = String(fields.get('password') || '')
    if (!username || !password) {
      setError('Escribe usuario y contraseña.')
      return
    }
    form.elements.password.value = ''
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/dashboard', { replace: true })
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) {
        setError('Usuario o contraseña incorrectos.')
      } else if (failure instanceof ApiError && failure.status === 0) {
        setError('No fue posible conectar con el CMS.')
      } else {
        setError('No fue posible iniciar sesión. Inténtalo de nuevo.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-screen">
      <section className="login-card" aria-labelledby="login-title">
        <span className="login-brand">CMS · Blog personal</span>
        <h1 id="login-title">Acceso administrativo</h1>
        <p className="login-intro">Gestiona el contenido editorial desde un espacio privado.</p>
        <form onSubmit={handleSubmit} noValidate>
          <label htmlFor="username">Usuario</label>
          <input id="username" name="username" autoComplete="username" required />
          <label htmlFor="password">Contraseña</label>
          <input id="password" name="password" type="password" autoComplete="current-password" required />
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? 'Iniciando sesión…' : 'Iniciar sesión'}
          </button>
        </form>
      </section>
    </main>
  )
}
