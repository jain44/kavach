import React, { useEffect, useState } from 'react'
import { Users, Plus, Edit3, UserX, UserCheck, Shield, ChevronDown, X, Check, AlertCircle } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import api from '../lib/api'

// ─── Types ────────────────────────────────────────────────────────────────────

interface UserRecord {
  id: number
  username: string
  name: string
  role: string
  is_active: boolean
  created_at: string
  updated_at?: string
}

const ROLE_COLORS: Record<string, string> = {
  risk_officer: '#b3a086',
  rm:           '#8c8070',
  cro:          '#C9A84C',
  compliance:   '#7a9c8a',
  admin:        '#e879f9',
}
const ROLE_LABELS: Record<string, string> = {
  risk_officer: 'Risk Officer',
  rm:           'Relationship Manager',
  cro:          'Chief Risk Officer',
  compliance:   'Compliance Officer',
  admin:        'Admin',
}
const ALL_ROLES = ['risk_officer', 'rm', 'cro', 'compliance', 'admin']

// ─── Sub-components ───────────────────────────────────────────────────────────

const RoleBadge = ({ role }: { role: string }) => (
  <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 5,
    padding: '3px 10px', borderRadius: 20,
    fontSize: '0.7rem', fontWeight: 600,
    background: `${ROLE_COLORS[role] || '#888'}18`,
    color: ROLE_COLORS[role] || '#aaa',
    border: `1px solid ${ROLE_COLORS[role] || '#888'}30`,
  }}>
    {ROLE_LABELS[role] || role}
  </span>
)

const StatusDot = ({ active }: { active: boolean }) => (
  <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 5,
    fontSize: '0.72rem', fontWeight: 600,
    color: active ? '#10b981' : '#ef4444',
  }}>
    <span style={{
      width: 7, height: 7, borderRadius: '50%',
      background: active ? '#10b981' : '#ef4444',
      boxShadow: active ? '0 0 6px #10b98188' : 'none',
    }} />
    {active ? 'Active' : 'Inactive'}
  </span>
)

// ─── Create / Edit Modal ─────────────────────────────────────────────────────

interface ModalProps {
  user?: UserRecord | null
  onClose: () => void
  onSave: () => void
}

const UserModal = ({ user, onClose, onSave }: ModalProps) => {
  const isEdit = !!user
  const [form, setForm] = useState({
    username: user?.username || '',
    name:     user?.name     || '',
    role:     user?.role     || 'risk_officer',
    password: '',
    is_active: user?.is_active ?? true,
  })
  const [saving, setSaving] = useState(false)
  const [error,  setError]  = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (isEdit) {
        const payload: Record<string, unknown> = {
          name: form.name, role: form.role, is_active: form.is_active,
        }
        if (form.password) payload.password = form.password
        await api.patch(`/users/${user!.id}`, payload)
      } else {
        await api.post('/users', {
          username: form.username,
          name:     form.name,
          role:     form.role,
          password: form.password,
        })
      }
      onSave()
      onClose()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e?.response?.data?.detail || 'Save failed. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '9px 12px', borderRadius: 8,
    background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
    color: 'var(--text-primary)', fontSize: '0.85rem', outline: 'none',
    boxSizing: 'border-box',
  }
  const labelStyle: React.CSSProperties = {
    fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)',
    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 5, display: 'block',
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div style={{
        background: 'var(--surface-1)', border: '1px solid var(--border-subtle)',
        borderRadius: 16, width: 440, padding: 28, boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 22 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Shield size={18} style={{ color: 'var(--accent-gold)' }} />
            <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-primary)' }}>
              {isEdit ? 'Edit User' : 'Create User'}
            </span>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
            <X size={18} />
          </button>
        </div>

        {error && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px',
            background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 8, marginBottom: 16, color: '#ef4444', fontSize: '0.82rem',
          }}>
            <AlertCircle size={14} />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {!isEdit && (
            <div>
              <label style={labelStyle}>Username</label>
              <input
                style={inputStyle}
                value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                required minLength={3} placeholder="e.g. priya_sharma"
              />
            </div>
          )}
          <div>
            <label style={labelStyle}>Full Name</label>
            <input
              style={inputStyle}
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              required placeholder="e.g. Priya Sharma"
            />
          </div>
          <div>
            <label style={labelStyle}>Role</label>
            <div style={{ position: 'relative' }}>
              <select
                style={{ ...inputStyle, appearance: 'none', paddingRight: 32, cursor: 'pointer' }}
                value={form.role}
                onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
              >
                {ALL_ROLES.map(r => (
                  <option key={r} value={r} style={{ background: '#1a1a1a' }}>{ROLE_LABELS[r]}</option>
                ))}
              </select>
              <ChevronDown size={14} style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
            </div>
          </div>
          <div>
            <label style={labelStyle}>{isEdit ? 'New Password (leave blank to keep)' : 'Password'}</label>
            <input
              type="password"
              style={inputStyle}
              value={form.password}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
              required={!isEdit}
              minLength={6}
              placeholder={isEdit ? '••••••• (unchanged)' : 'Min 6 characters'}
            />
          </div>
          {isEdit && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button
                type="button"
                onClick={() => setForm(f => ({ ...f, is_active: !f.is_active }))}
                style={{
                  width: 40, height: 22, borderRadius: 11, border: 'none', cursor: 'pointer', position: 'relative',
                  background: form.is_active ? '#10b981' : 'rgba(255,255,255,0.12)',
                  transition: 'background 0.2s',
                }}
              >
                <span style={{
                  position: 'absolute', top: 3, left: form.is_active ? 20 : 3,
                  width: 16, height: 16, borderRadius: '50%', background: '#fff',
                  transition: 'left 0.2s',
                }} />
              </button>
              <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Account active</span>
            </div>
          )}

          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <button type="button" onClick={onClose} style={{
              flex: 1, padding: '10px', borderRadius: 8, cursor: 'pointer',
              background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: 600,
            }}>
              Cancel
            </button>
            <button type="submit" disabled={saving} style={{
              flex: 1, padding: '10px', borderRadius: 8, cursor: saving ? 'not-allowed' : 'pointer',
              background: saving ? 'rgba(201,168,76,0.4)' : 'var(--accent-gold)',
              border: 'none', color: '#000', fontSize: '0.85rem', fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
              {saving ? 'Saving...' : <><Check size={14} />{isEdit ? 'Update' : 'Create'}</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function UserManagement() {
  const { user: currentUser } = useAuth()
  const [users,   setUsers]   = useState<UserRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')
  const [modal,   setModal]   = useState<{ open: boolean; user: UserRecord | null }>({ open: false, user: null })
  const [confirm, setConfirm] = useState<UserRecord | null>(null)

  const canManage = currentUser?.role === 'cro' // only CRO can create/edit

  const fetchUsers = async () => {
    setLoading(true)
    try {
      const data = await api.get('/users').then(r => r.data)
      setUsers(data)
      setError('')
    } catch {
      setError('Failed to load users. You may not have permission.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchUsers() }, [])

  const handleDeactivate = async (u: UserRecord) => {
    try {
      await api.delete(`/users/${u.id}`)
      setConfirm(null)
      fetchUsers()
    } catch {
      setError('Failed to deactivate user.')
    }
  }

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1000, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
            <div style={{
              width: 38, height: 38, borderRadius: 10,
              background: 'linear-gradient(135deg, var(--accent-gold), #aa8a34)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Users size={18} style={{ color: '#000' }} />
            </div>
            <h1 style={{ margin: 0, fontWeight: 800, fontSize: '1.5rem', color: 'var(--text-primary)' }}>
              User Management
            </h1>
          </div>
          <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Manage system users, roles, and access permissions.
            {!canManage && <span style={{ color: '#f59e0b', marginLeft: 6 }}>View-only — CRO role required to edit.</span>}
          </p>
        </div>
        {canManage && (
          <button
            onClick={() => setModal({ open: true, user: null })}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '9px 18px', borderRadius: 8, cursor: 'pointer',
              background: 'var(--accent-gold)', border: 'none',
              color: '#000', fontWeight: 700, fontSize: '0.85rem',
            }}
          >
            <Plus size={16} /> New User
          </button>
        )}
      </div>

      {/* Stats Bar */}
      {!loading && users.length > 0 && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
          {[
            { label: 'Total Users',   value: users.length,                              color: 'var(--accent-gold)' },
            { label: 'Active',        value: users.filter(u => u.is_active).length,     color: '#10b981' },
            { label: 'Inactive',      value: users.filter(u => !u.is_active).length,    color: '#ef4444' },
          ].map(stat => (
            <div key={stat.label} style={{
              padding: '12px 18px', borderRadius: 10,
              background: 'var(--surface-1)', border: '1px solid var(--border-subtle)',
              minWidth: 100,
            }}>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: stat.color }}>{stat.value}</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 500 }}>{stat.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 10, marginBottom: 16, color: '#ef4444', fontSize: '0.85rem',
        }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* Table */}
      <div style={{
        background: 'var(--surface-1)', border: '1px solid var(--border-subtle)',
        borderRadius: 14, overflow: 'hidden',
      }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)' }}>
            <div className="animate-spin" style={{ width: 28, height: 28, borderRadius: '50%', border: '2px solid rgba(201,168,76,0.3)', borderTopColor: 'var(--accent-gold)', margin: '0 auto 12px' }} />
            Loading users...
          </div>
        ) : users.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)' }}>
            No users found. Run the seed script first.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                {['#', 'Username', 'Full Name', 'Role', 'Status', 'Created', 'Actions'].map(h => (
                  <th key={h} style={{
                    padding: '12px 16px', textAlign: 'left',
                    fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)',
                    textTransform: 'uppercase', letterSpacing: '0.07em',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u, i) => (
                <tr key={u.id} style={{
                  borderBottom: '1px solid rgba(255,255,255,0.03)',
                  background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                  transition: 'background 0.15s',
                  opacity: u.is_active ? 1 : 0.5,
                }}>
                  <td style={{ padding: '12px 16px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{u.id}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{
                      fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem',
                      color: u.username === currentUser?.username ? 'var(--accent-gold)' : 'var(--text-primary)',
                      fontWeight: 600,
                    }}>
                      {u.username}
                      {u.username === currentUser?.username && (
                        <span style={{ marginLeft: 6, fontSize: '0.65rem', color: 'var(--accent-gold)', opacity: 0.7 }}>(you)</span>
                      )}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: '0.83rem', color: 'var(--text-secondary)' }}>{u.name}</td>
                  <td style={{ padding: '12px 16px' }}><RoleBadge role={u.role} /></td>
                  <td style={{ padding: '12px 16px' }}><StatusDot active={u.is_active} /></td>
                  <td style={{ padding: '12px 16px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {new Date(u.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    {canManage && (
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          onClick={() => setModal({ open: true, user: u })}
                          title="Edit"
                          style={{
                            padding: '5px 8px', borderRadius: 6, cursor: 'pointer',
                            background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          <Edit3 size={13} />
                        </button>
                        {u.username !== currentUser?.username && u.is_active && (
                          <button
                            onClick={() => setConfirm(u)}
                            title="Deactivate"
                            style={{
                              padding: '5px 8px', borderRadius: 6, cursor: 'pointer',
                              background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
                              color: '#ef4444',
                            }}
                          >
                            <UserX size={13} />
                          </button>
                        )}
                        {u.username !== currentUser?.username && !u.is_active && (
                          <button
                            onClick={() => handleDeactivate(u)}
                            title="Re-activate"
                            style={{
                              padding: '5px 8px', borderRadius: 6, cursor: 'pointer',
                              background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)',
                              color: '#10b981',
                            }}
                          >
                            <UserCheck size={13} />
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Confirm Deactivate Dialog */}
      {confirm && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: 'var(--surface-1)', border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 16, width: 360, padding: 28,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <UserX size={22} style={{ color: '#ef4444' }} />
              <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-primary)' }}>Deactivate User</span>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: 22 }}>
              Are you sure you want to deactivate <strong style={{ color: 'var(--text-primary)' }}>{confirm.name}</strong> ({confirm.username})?
              They will no longer be able to log in.
            </p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setConfirm(null)} style={{
                flex: 1, padding: '9px', borderRadius: 8, cursor: 'pointer',
                background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-subtle)',
                color: 'var(--text-secondary)', fontWeight: 600,
              }}>Cancel</button>
              <button onClick={() => handleDeactivate(confirm)} style={{
                flex: 1, padding: '9px', borderRadius: 8, cursor: 'pointer',
                background: 'rgba(239,68,68,0.9)', border: 'none',
                color: '#fff', fontWeight: 700,
              }}>Deactivate</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal */}
      {modal.open && (
        <UserModal
          user={modal.user}
          onClose={() => setModal({ open: false, user: null })}
          onSave={fetchUsers}
        />
      )}
    </div>
  )
}
