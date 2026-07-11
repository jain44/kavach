import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Search, BarChart3, Shield, Bell, LogOut, Zap, Users } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import type { UserRole } from '../contexts/AuthContext'

const ROLE_META: Record<string, { label: string; color: string; short: string }> = {
  risk_officer: { label: 'Risk Officer',          color: '#b3a086', short: 'RO' },
  rm:           { label: 'Relationship Manager',  color: '#8c8070', short: 'RM' },
  cro:          { label: 'Chief Risk Officer',    color: '#C9A84C', short: 'CR' },
  compliance:   { label: 'Compliance Officer',    color: '#7a9c8a', short: 'CO' },
  admin:        { label: 'Administrator',         color: '#e879f9', short: 'AD' },
}

const NAV_ITEMS = [
  { path: '/portfolio',   label: 'Portfolio Heatmap',  icon: LayoutDashboard, roles: ['risk_officer','rm','cro'] },
  { path: '/account',     label: 'Account Detail',     icon: Search,          roles: ['risk_officer','rm','cro','compliance'] },
  { path: '/simulator',   label: 'What-If Simulator',  icon: Zap,             roles: ['risk_officer','rm','cro'] },
  { path: '/analytics',   label: 'Portfolio Analytics',icon: BarChart3,       roles: ['cro','risk_officer'] },
  { path: '/governance',  label: 'Model Governance',   icon: Shield,          roles: ['compliance','cro','risk_officer'] },
  { path: '/alerts',      label: 'Alerts',             icon: Bell,            roles: ['risk_officer','rm','cro'] },
  { path: '/users',       label: 'User Management',    icon: Users,           roles: ['cro','admin'] },
]

export const Sidebar = () => {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  if (!user) return null

  const meta  = ROLE_META[user.role] ?? ROLE_META['risk_officer']
  const items = NAV_ITEMS.filter(i => i.roles.includes(user.role))

  return (
    <aside
      className="sidebar-gradient"
      style={{
        width: 'var(--sidebar-w)',
        position: 'fixed', top: 0, left: 0,
        height: '100vh',
        display: 'flex', flexDirection: 'column',
        zIndex: 40, overflowY: 'auto',
      }}
    >
      {/* ── Logo ──────────────────────────────────────────────────── */}
      <div style={{ padding: '18px 16px 14px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 10,
            background: 'linear-gradient(135deg, var(--accent-gold), #aa8a34)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
            boxShadow: '0 0 10px rgba(201,168,76,0.2)',
          }}>
            <Shield size={17} style={{ color: '#000' }} />
          </div>
          <div>
            <div style={{ fontFamily: "'Cormorant Garamond', 'Space Grotesk', serif", fontWeight: 700, color: '#f5f5f4', fontSize: '1.1rem', lineHeight: 1, letterSpacing: '0.02em' }}>
              KAVACH
            </div>
            <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)', marginTop: 3, letterSpacing: '0.05em', textTransform: 'uppercase', fontWeight: 500 }}>
              IDBI Early Warning
            </div>
          </div>
        </div>
      </div>

      {/* ── User Badge ────────────────────────────────────────────── */}
      <div style={{ padding: '10px 12px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '9px 10px', borderRadius: 10,
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <div style={{
            width: 30, height: 30, borderRadius: 8,
            background: meta.color,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.68rem', fontWeight: 700, color: '#000', flexShrink: 0,
          }}>
            {meta.short}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user.username}
            </div>
            <div style={{ fontSize: '0.7rem', color: meta.color, marginTop: 1 }}>
              {meta.label}
            </div>
          </div>
        </div>
      </div>

      {/* ── Nav ───────────────────────────────────────────────────── */}
      <nav style={{ flex: 1, padding: '4px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div style={{ fontSize: '0.62rem', fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', padding: '8px 6px 6px' }}>
          Navigation
        </div>
        {items.map(item => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={15} />
              <span>{item.label}</span>
            </NavLink>
          )
        })}
      </nav>

      {/* ── Footer ────────────────────────────────────────────────── */}
      <div style={{ padding: '10px 12px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
        {/* Model info */}
        <div style={{
          padding: '10px 12px', borderRadius: 10, marginBottom: 6,
          background: 'rgba(201,168,76,0.03)',
          border: '1px solid var(--border-subtle)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 500 }}>Model Version</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div className="status-dot-green" />
              <span style={{ fontSize: '0.65rem', color: '#10b981', fontWeight: 600 }}>Live</span>
            </div>
          </div>
          <div style={{ fontFamily: 'JetBrains Mono,monospace', fontWeight: 700, fontSize: '0.75rem', color: 'var(--accent-gold)' }}>v1.0.0</div>
          <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: '0.68rem', color: 'var(--text-secondary)', marginTop: 2 }}>AUC-ROC 0.7294</div>
        </div>

        {/* Sign out */}
        <button
          onClick={() => { logout(); navigate('/login') }}
          className="nav-item"
          style={{ width: '100%', color: '#ef4444', border: 'none', background: 'none' }}
        >
          <LogOut size={14} />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  )
}
