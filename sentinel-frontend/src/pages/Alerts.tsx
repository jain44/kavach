import React, { useEffect, useState } from 'react'
import { Bell, AlertTriangle, TrendingDown, ChevronRight, Clock } from 'lucide-react'
import { getAlerts } from '../lib/api'
import { RiskGradeBadge, PageLoader } from '../components/ui'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'

const SEV: Record<string, { label:string; color:string; bg:string; border:string }> = {
  critical: { label:'Critical', color:'#ef4444', bg:'rgba(239,68,68,0.08)',  border:'rgba(239,68,68,0.22)'  },
  high:     { label:'High',     color:'#f97316', bg:'rgba(249,115,22,0.08)', border:'rgba(249,115,22,0.22)' },
  medium:   { label:'Medium',   color:'var(--accent-gold)', bg:'rgba(201,168,76,0.06)', border:'var(--border-subtle)' },
}

const TYPE_ICON: Record<string, React.ReactNode> = {
  grade_downgrade: <TrendingDown size={14} />,
  stress_spike:    <AlertTriangle size={14} />,
  dpd_new:         <Bell size={14} />,
  litigation:      <AlertTriangle size={14} />,
}

const DAY_OPTIONS = [1, 7, 14, 30]

export default function AlertsPage() {
  const navigate = useNavigate()
  const [data, setData]         = useState<any>(null)
  const [loading, setLoading]   = useState(true)
  const [days, setDays]         = useState(7)
  const [sevFilter, setSevFilter] = useState<string>('all')

  useEffect(() => {
    setLoading(true)
    getAlerts(days).then(setData).finally(() => setLoading(false))
  }, [days])

  const alerts: any[] = (data?.alerts ?? []).filter((a: any) =>
    sevFilter === 'all' || a.severity === sevFilter
  )

  return (
    <div className="page-content">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:22, flexWrap:'wrap', gap:12 }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:4 }}>
            <div style={{ width:32, height:32, borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(239,68,68,0.12)' }}>
              <Bell size={15} style={{ color:'#ef4444' }} />
            </div>
            <h1 className="page-title" style={{ marginBottom:0 }}>Alerts</h1>
          </div>
          <p className="page-subtitle" style={{ paddingLeft:42 }}>
            {data?.total ?? '—'} alerts · {data?.critical_count ?? 0} critical · {data?.high_count ?? 0} high
          </p>
        </div>
        {/* Day range tabs */}
        <div style={{ display:'flex', gap:6 }}>
          {DAY_OPTIONS.map(d => (
            <button key={d} onClick={() => setDays(d)} className={`filter-pill ${days===d?'active':''}`}>
              {d === 1 ? 'Today' : `${d}d`}
            </button>
          ))}
        </div>
      </div>

      {/* ── Summary Cards ────────────────────────────────────────────── */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:12, marginBottom:18 }}>
        {[
          { key:'critical', label:'Critical', value: data?.critical_count ?? 0 },
          { key:'high',     label:'High',     value: data?.high_count ?? 0    },
          { key:'all',      label:'Total',    value: data?.total ?? 0          },
        ].map(({ key, label, value }) => {
          const cfg = SEV[key]
          const isActive = sevFilter === key
          return (
            <button
              key={key}
              onClick={() => setSevFilter(isActive ? 'all' : key)}
              className="glass-card"
              style={{
                padding:'16px 18px', textAlign:'left', cursor:'pointer',
                border: isActive && cfg ? `1px solid ${cfg.color}40` : undefined,
                background: isActive && cfg ? `${cfg.color}06` : undefined,
                transition:'all 0.15s ease',
              }}
            >
              <div style={{ fontFamily:'Space Grotesk,sans-serif', fontWeight:700, fontSize:'1.8rem', color: cfg?.color ?? 'var(--text-primary)', lineHeight:1 }}>
                {value}
              </div>
              <div style={{ fontSize:'0.72rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'0.06em', color: cfg?.color ?? 'var(--text-muted)', marginTop:5 }}>
                {label}
              </div>
            </button>
          )
        })}
      </div>

      {/* ── Severity filter ───────────────────────────────────────────── */}
      <div style={{ display:'flex', gap:6, marginBottom:16 }}>
        {['all','critical','high','medium'].map(s => (
          <button key={s} onClick={() => setSevFilter(s)} className={`filter-pill ${sevFilter===s?'active':''}`}>
            {s === 'all' ? 'All Alerts' : s.charAt(0).toUpperCase()+s.slice(1)}
          </button>
        ))}
      </div>

      {/* ── Alert List ────────────────────────────────────────────────── */}
      {loading ? (
        <div className="glass-card" style={{ padding:40 }}><PageLoader /></div>
      ) : alerts.length === 0 ? (
        <div className="glass-card" style={{ padding:56, display:'flex', flexDirection:'column', alignItems:'center', gap:12 }}>
          <Bell size={32} style={{ color:'var(--text-muted)' }} />
          <div style={{ fontWeight:600, color:'var(--text-secondary)' }}>No alerts for this period</div>
          <div style={{ fontSize:'0.82rem', color:'var(--text-muted)' }}>Try a wider time range</div>
        </div>
      ) : (
        <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
          {alerts.map((alert:any, i:number) => {
            const cfg = SEV[alert.severity] ?? SEV.medium
            return (
              <motion.div
                key={alert.alert_id}
                initial={{ opacity:0, x:-8 }} animate={{ opacity:1, x:0 }}
                transition={{ delay: i*0.025 }}
                onClick={() => navigate(`/account?id=${alert.borrower_id}`)}
                className="glass-card"
                style={{
                  padding:'14px 16px', cursor:'pointer',
                  display:'flex', alignItems:'flex-start', gap:12,
                  borderLeft:`3px solid ${cfg.color}`,
                  transition:'background 0.12s ease',
                }}
              >
                {/* Icon */}
                <div style={{
                  width:34, height:34, borderRadius:9, display:'flex', alignItems:'center', justifyContent:'center',
                  background:cfg.bg, color:cfg.color, border:`1px solid ${cfg.border}`, flexShrink:0, marginTop:1,
                }}>
                  {TYPE_ICON[alert.alert_type] ?? <Bell size={14}/>}
                </div>

                {/* Body */}
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:10 }}>
                    <div style={{ minWidth:0 }}>
                      {/* Row 1: ID + severity + grade change */}
                      <div style={{ display:'flex', alignItems:'center', gap:8, flexWrap:'wrap', marginBottom:4 }}>
                        <span style={{ fontSize:'0.85rem', fontWeight:700, color:'var(--text-primary)', fontFamily:'Space Grotesk,sans-serif' }}>
                          {alert.borrower_id}
                        </span>
                        <span className="info-chip" style={{ background:cfg.bg, color:cfg.color, borderColor:cfg.border }}>
                          {cfg.label}
                        </span>
                        {alert.old_grade && alert.new_grade && (
                          <div style={{ display:'flex', alignItems:'center', gap:5 }}>
                            <RiskGradeBadge grade={alert.old_grade} size="sm" />
                            <span style={{ fontSize:'0.7rem', color:'var(--text-muted)' }}>→</span>
                            <RiskGradeBadge grade={alert.new_grade} size="sm" />
                          </div>
                        )}
                      </div>
                      {/* Row 2: message */}
                      <div style={{ fontSize:'0.82rem', color:'var(--text-secondary)', marginBottom:5 }}>{alert.message}</div>
                      {/* Row 3: meta */}
                      <div style={{ display:'flex', alignItems:'center', gap:12, fontSize:'0.72rem', color:'var(--text-muted)', flexWrap:'wrap' }}>
                        <span>{alert.loan_type}</span>
                        <span>·</span>
                        <span>{alert.industry}</span>
                        <span>·</span>
                        <span>Stress: <span style={{ fontFamily:'JetBrains Mono,monospace', fontWeight:600, color:cfg.color }}>{alert.stress_score?.toFixed(0) ?? '—'}</span></span>
                        <span>·</span>
                        <span style={{ display:'flex', alignItems:'center', gap:3 }}>
                          <Clock size={10} />
                          {new Date(alert.triggered_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    <ChevronRight size={15} style={{ color:'var(--text-muted)', flexShrink:0 }} />
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}
