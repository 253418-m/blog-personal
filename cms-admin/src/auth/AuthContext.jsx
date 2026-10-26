import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { getCurrentAdmin, loginRequest } from '../api/auth'
import { ApiError, setUnauthorizedHandler } from '../api/http'
import { clearToken, getToken, saveToken } from '../api/session'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const requestVersion = useRef(0)
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState(getToken() ? 'checking' : 'guest')

  const logout = useCallback(() => {
    requestVersion.current += 1
    clearToken()
    setUser(null)
    setStatus('guest')
  }, [])

  const validateSession = useCallback(async () => {
    if (!getToken()) {
      logout()
      return
    }
    const version = ++requestVersion.current
    setStatus('checking')
    try {
      const current = await getCurrentAdmin()
      if (requestVersion.current === version) {
        setUser(current)
        setStatus('authenticated')
      }
    } catch (error) {
      if (requestVersion.current !== version) return
      if (error instanceof ApiError && [401, 403].includes(error.status)) logout()
      else setStatus('error')
    }
  }, [logout])

  useEffect(() => {
    const removeHandler = setUnauthorizedHandler(logout)
    validateSession()
    return removeHandler
  }, [logout, validateSession])

  const login = async (username, password) => {
    clearToken()
    const version = ++requestVersion.current
    const result = await loginRequest(username, password)
    if (typeof result?.access_token !== 'string' || !result.access_token) throw new ApiError(0)
    saveToken(result.access_token)
    try {
      const current = await getCurrentAdmin()
      if (requestVersion.current === version) {
        setUser(current)
        setStatus('authenticated')
      }
    } catch (error) {
      logout()
      throw error
    }
  }

  return (
    <AuthContext.Provider value={{ user, status, login, logout, validateSession }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider es obligatorio.')
  return value
}
