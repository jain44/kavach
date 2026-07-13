import React from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { Sidebar } from './components/Sidebar'

// Pages
import LoginPage from './pages/Login'
import PortfolioHeatmap from './pages/PortfolioHeatmap'
import AccountDetail from './pages/AccountDetail'
import WhatIfSimulator from './pages/WhatIfSimulator'
import PortfolioAnalytics from './pages/PortfolioAnalytics'
import ModelGovernance from './pages/ModelGovernance'
import AlertsPage from './pages/Alerts'
import UserManagement from './pages/UserManagement'

// Animated page wrapper
const PageWrapper = ({ children }: { children: React.ReactNode }) => (
  <motion.div
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -8 }}
    transition={{ duration: 0.25, ease: 'easeOut' }}
  >
    {children}
  </motion.div>
)

// Route guard — redirect to login if not authenticated
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, isLoading } = useAuth()
  if (isLoading) return null
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

// App shell with sidebar
const AppShell = () => {
  const location = useLocation()
  const { user } = useAuth()

  if (!user) return null

  return (
    <div className="page-layout gradient-bg">
      <Sidebar />
      <main className="main-content">
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/portfolio" element={<PageWrapper><PortfolioHeatmap /></PageWrapper>} />
            <Route path="/account" element={<PageWrapper><AccountDetail /></PageWrapper>} />
            <Route path="/simulator" element={<PageWrapper><WhatIfSimulator /></PageWrapper>} />
            <Route path="/analytics" element={<PageWrapper><PortfolioAnalytics /></PageWrapper>} />
            <Route path="/governance" element={<PageWrapper><ModelGovernance /></PageWrapper>} />
            <Route path="/alerts" element={<PageWrapper><AlertsPage /></PageWrapper>} />
            <Route path="/users" element={<PageWrapper><UserManagement /></PageWrapper>} />
            <Route path="*" element={<Navigate to="/portfolio" replace />} />
          </Routes>
        </AnimatePresence>
      </main>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}

const AppRoutes = () => {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center gradient-bg">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: 'rgba(245,158,11,0.3)', borderTopColor: '#f59e0b' }} />
          <div className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading Sentinel...</div>
        </div>
      </div>
    )
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/portfolio" replace /> : <LoginPage />}
      />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

export default App
