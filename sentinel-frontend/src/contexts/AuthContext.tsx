import React, { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { login as apiLogin } from '../lib/api'

export type UserRole = 'risk_officer' | 'rm' | 'cro' | 'compliance'

interface AuthUser {
  username: string
  role: UserRole
  token: string
}

interface AuthContextType {
  user: AuthUser | null
  isLoading: boolean
  login: (username: string, password: string, role: UserRole) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Restore session from localStorage
    const token = localStorage.getItem('kavach_token')
    const role = localStorage.getItem('kavach_role') as UserRole | null
    const username = localStorage.getItem('kavach_username')
    if (token && role && username) {
      setUser({ token, role, username })
    }
    setIsLoading(false)
  }, [])

  const login = async (username: string, password: string, role: UserRole) => {
    const data = await apiLogin(username, password, role)
    const authUser: AuthUser = {
      token: data.access_token,
      role: data.role as UserRole,
      username: data.username,
    }
    localStorage.setItem('kavach_token', authUser.token)
    localStorage.setItem('kavach_role', authUser.role)
    localStorage.setItem('kavach_username', authUser.username)
    setUser(authUser)
  }

  const logout = () => {
    localStorage.removeItem('kavach_token')
    localStorage.removeItem('kavach_role')
    localStorage.removeItem('kavach_username')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
