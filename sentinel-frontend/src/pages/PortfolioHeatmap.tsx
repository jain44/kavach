import React, { useEffect, useState, useCallback, useMemo, useTransition } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, RefreshCw, AlertTriangle, TrendingUp,
  TrendingDown, Minus, ChevronRight, LayoutGrid,
  List, Activity, Shield, Zap, BarChart2,
} from 'lucide-react'
import { getPortfolio } from '../lib/api'
import { RiskGradeBadge, StressBar, PageLoader, Skeleton, gradeToColor, stressToColor } from '../components/ui'
import { motion } from 'framer-motion'

const LOAN_TYPES = ['All', 'Working Capital', 'Term Loan', 'Trade Finance']
const GRADE_ORDER = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'C', 'D']
const GRADE_RANK: Record<string, number> = { AAA:0, AA:1, A:2, BBB:3, BB:4, B:5, C:6, D:7 }

export default function PortfolioHeatmap() {
  const navigate = useNavigate()
  const [data, setData]         = useState<any>(null)
  const [loading, setLoading]   = useState(true)
  const [loanType, setLoanType] = useState('All')
  const [minStress, setMinStress] = useState<number | undefined>()
  const [search, setSearch]     = useState('')
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table')
  const [industry, setIndustry] = useState('All')
  const [region, setRegion]     = useState('All')
  const [deltaFilter, setDeltaFilter] = useState<'all' | 'worsened' | 'improved'>('all')
  const [sortMode, setSortMode] = useState<'stress_desc' | 'stress_asc' | 'grade' | 'pd_desc'>('grade')
  const [isPending, startTransition] = useTransition()

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params: any = { page_size: 300 }
      if (loanType !== 'All') params.loan_type = loanType
      if (minStress !== undefined) params.min_stress = minStress
      setData(await getPortfolio(params))
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [loanType, minStress])

  useEffect(() => { fetchData() }, [fetchData])

  const accounts = useMemo(() => {
    const searchLower = search.toLowerCase()
    return (data?.accounts ?? []).filter((a: any) =>
      (!searchLower ||
        a.borrower_id.toLowerCase().includes(searchLower) ||
        (a.business_name ?? '').toLowerCase().includes(searchLower)) &&
      (industry === 'All' || a.industry === industry) &&
      (region === 'All' || a.region === region) &&
      (deltaFilter === 'all' ||
        (deltaFilter === 'worsened' && (a.stress_score_delta ?? 0) > 0) ||
        (deltaFilter === 'improved' && (a.stress_score_delta ?? 0) < 0))
    ).sort((a: any, b: any) => {
      if (sortMode === 'stress_desc') return b.stress_score - a.stress_score
      if (sortMode === 'stress_asc')  return a.stress_score - b.stress_score
      if (sortMode === 'pd_desc')     return b.pd_probability - a.pd_probability
      const gd = (GRADE_RANK[a.risk_grade] ?? 9) - (GRADE_RANK[b.risk_grade] ?? 9)
      return gd !== 0 ? gd : b.stress_score - a.stress_score
    })
  }, [data, search, industry, region, deltaFilter, sortMode])

  const gradeDist   = data?.grade_distribution ?? []
  const totalAccounts = data?.total_accounts ?? 0
  const avgStress   = data?.avg_stress_score ?? 0
  const highRisk    = data?.high_risk_count ?? 0
  const criticalN   = gradeDist.find((g: any) => g.grade === 'D')?.count ?? 0

  const getDelta = (d?: number | null) => {
    if (!d || Math.abs(d) < 1) return <Minus size={11} style={{ color: 'var(--text-muted)' }} />
    return d > 0
      ? <TrendingUp  size={11} style={{ color: '#ef4444' }} />
      : <TrendingDown size={11} style={{ color: '#10b981' }} />
  }

  return (
    <div className="page-content">

      {/* ── Topbar ──────────────────────────────────────────────────── */}
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:22, flexWrap:'wrap', gap:12 }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:4 }}>
            <div style={{ width:32, height:32, borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(201,168,76,0.12)' }}>
              <LayoutGrid size={15} style={{ color:'var(--accent-gold)' }} />
            </div>
            <h1 className="page-title" style={{ marginBottom:0 }}>Portfolio Heatmap</h1>
          </div>
          <p className="page-subtitle" style={{ paddingLeft:42 }}>
            {totalAccounts.toLocaleString()} accounts · {data?.as_of_month ?? '—'}
          </p>
        </div>
        <button onClick={fetchData} className="btn-secondary" style={{ display:'flex', alignItems:'center', gap:6 }} disabled={loading}>
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* ── KPI Row ──────────────────────────────────────────────────── */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:14, marginBottom:20 }}>
        {loading ? Array.from({length:4}).map((_,i) => <Skeleton key={i} className="h-24" />) : (
          <>
            {[
              { label:'Total Accounts',     value: totalAccounts.toLocaleString(), sub:'under monitoring',     icon:<Shield size={18}/>,       color:'var(--accent-gold)' },
              { label:'Avg Stress Score',   value: avgStress.toFixed(1),           sub:'portfolio average',     icon:<Activity size={18}/>,     color: avgStress>40 ? '#ef4444' : '#10b981', accent: avgStress>40 },
              { label:'High Risk (C / D)',  value: highRisk.toLocaleString(),       sub:`${totalAccounts ? ((highRisk/totalAccounts)*100).toFixed(1) : 0}% of portfolio`, icon:<AlertTriangle size={18}/>, color:'#f97316' },
              { label:'Critical (Grade D)', value: criticalN.toLocaleString(),      sub:'immediate action',      icon:<Zap size={18}/>,          color:'#ef4444' },
            ].map((c, i) => (
              <motion.div
                key={c.label}
                initial={{ opacity:0, y:12 }} animate={{ opacity:1, y:0 }}
                transition={{ delay: i*0.06 }}
                className={`glass-card ${c.accent ? 'glass-card-accent' : ''}`}
                style={{ padding:'18px 20px' }}
              >
                <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:10 }}>
                  <span className="metric-label">{c.label}</span>
                  <div style={{ width:30, height:30, borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', background:`${c.color}14`, color:c.color, flexShrink:0 }}>
                    {c.icon}
                  </div>
                </div>
                <div className="metric-value" style={{ color: c.color, fontSize:'1.75rem' }}>{c.value}</div>
                <div style={{ fontSize:'0.75rem', marginTop:5, color:'var(--text-muted)' }}>{c.sub}</div>
              </motion.div>
            ))}
          </>
        )}
      </div>

      {/* ── Grade Distribution ────────────────────────────────────────── */}
      {!loading && gradeDist.length > 0 && (
        <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} className="glass-card" style={{ padding:'16px 20px', marginBottom:18 }}>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10, flexWrap:'wrap', gap:8 }}>
            <span className="section-title">Grade Distribution</span>
            <div style={{ display:'flex', flexWrap:'wrap', gap:10 }}>
              {gradeDist.filter((g:any)=>g.count>0).map((item:any) => (
                <div key={item.grade} style={{ display:'flex', alignItems:'center', gap:5 }}>
                  <div style={{ width:8, height:8, borderRadius:2, background: gradeToColor(item.grade) }} />
                  <span style={{ fontSize:'0.72rem', color:'var(--text-muted)' }}>
                    {item.grade} <span style={{ color:'var(--text-secondary)', fontFamily:'JetBrains Mono,monospace' }}>{item.count}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ display:'flex', height:22, borderRadius:8, overflow:'hidden', gap:1 }}>
            {GRADE_ORDER.map(grade => {
              const item = gradeDist.find((g:any) => g.grade===grade)
              const pct  = item?.percentage ?? 0
              if (pct < 0.5) return null
              return (
                <div
                  key={grade}
                  style={{ width:`${pct}%`, background:gradeToColor(grade), display:'flex', alignItems:'center', justifyContent:'center', opacity:0.85 }}
                  title={`${grade}: ${item?.count} (${pct.toFixed(1)}%)`}
                >
                  {pct > 5 && <span style={{ fontSize:'0.65rem', fontWeight:700, color:'#fff', fontFamily:'Space Grotesk,sans-serif' }}>{grade}</span>}
                </div>
              )
            })}
          </div>
        </motion.div>
      )}

      {/* ── Toolbar ──────────────────────────────────────────────────── */}
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:16, flexWrap:'wrap' }}>
        {/* Search */}
        <div style={{ position:'relative', flex:'1', minWidth:200, maxWidth:240 }}>
          <Search size={13} style={{ position:'absolute', left:11, top:'50%', transform:'translateY(-50%)', color:'var(--text-muted)' }} />
          <input
            className="input-field"
            style={{ paddingLeft:34, fontSize:'0.8rem' }}
            placeholder="Search borrower…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        {/* Loan type pills */}
        <div style={{ display:'flex', gap:6 }}>
          {LOAN_TYPES.map(lt => (
            <button key={lt} onClick={() => startTransition(() => setLoanType(lt))} className={`filter-pill ${loanType===lt?'active':''}`}>
              {lt}
            </button>
          ))}
        </div>

        {/* Industry Filter Dropdown */}
        <select
          value={industry}
          onChange={e => startTransition(() => setIndustry(e.target.value))}
          style={{
            fontSize: '0.8rem', padding: '6px 24px 6px 12px', height: '34px',
            background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
            borderRadius: 8, color: 'var(--text-secondary)', cursor: 'pointer', outline: 'none'
          }}
        >
          <option value="All">All Industries</option>
          {Array.from(new Set((data?.accounts ?? []).map((a: any) => a.industry))).filter(Boolean).map(ind => (
            <option key={ind as string} value={ind as string}>{ind as string}</option>
          ))}
        </select>

        {/* Region Filter Dropdown */}
        <select
          value={region}
          onChange={e => startTransition(() => setRegion(e.target.value))}
          style={{
            fontSize: '0.8rem', padding: '6px 24px 6px 12px', height: '34px',
            background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
            borderRadius: 8, color: 'var(--text-secondary)', cursor: 'pointer', outline: 'none'
          }}
        >
          <option value="All">All Regions</option>
          {Array.from(new Set((data?.accounts ?? []).map((a: any) => a.region))).filter(Boolean).map(reg => (
            <option key={reg as string} value={reg as string}>{reg as string}</option>
          ))}
        </select>

        {/* Sort Dropdown */}
        <select
          value={sortMode}
          onChange={e => startTransition(() => setSortMode(e.target.value as any))}
          style={{
            fontSize: '0.8rem', padding: '6px 24px 6px 12px', height: '34px',
            background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
            borderRadius: 8, color: 'var(--text-secondary)', cursor: 'pointer', outline: 'none'
          }}
        >
          <option value="grade">Sort: By Grade (AAA → D)</option>
          <option value="stress_desc">Sort: Highest Stress First</option>
          <option value="stress_asc">Sort: Lowest Stress First</option>
          <option value="pd_desc">Sort: Highest PD First</option>
        </select>

        {/* Spacer */}
        <div style={{ flex:1 }} />

        {/* MoM Delta Toggle */}
        <button
          onClick={() => startTransition(() => setDeltaFilter(p => p === 'worsened' ? 'all' : 'worsened'))}
          className={`filter-pill ${deltaFilter==='worsened'?'active':''}`}
          style={{ display:'flex', alignItems:'center', gap:5 }}
        >
          <TrendingUp size={11} /> Worsened MoM Only
        </button>

        {/* High-risk toggle */}
        <button
          onClick={() => setMinStress(minStress===45 ? undefined : 45)}
          className={`filter-pill ${minStress===45?'active':''}`}
          style={{ display:'flex', alignItems:'center', gap:5 }}
        >
          <AlertTriangle size={11} /> High Risk Only
        </button>

        {/* View toggle */}
        <div style={{ display:'flex', borderRadius:8, overflow:'hidden', border:'1px solid var(--border-subtle)' }}>
          {([['table','Table',List] as const, ['grid','Grid',LayoutGrid] as const]).map(([m,lbl,Icon]) => (
            <button
              key={m}
              onClick={() => setViewMode(m)}
              style={{
                padding:'6px 12px', display:'flex', alignItems:'center', gap:5, fontSize:'0.78rem', fontWeight:500, cursor:'pointer', border:'none',
                background: viewMode===m ? 'rgba(201,168,76,0.12)' : 'transparent',
                color: viewMode===m ? 'var(--accent-gold)' : 'var(--text-muted)',
              }}
            >
              <Icon size={12} /> {lbl}
            </button>
          ))}
        </div>
      </div>

      {/* ── Content ──────────────────────────────────────────────────── */}
      <div style={{ opacity: isPending ? 0.6 : 1, transition: 'opacity 0.15s' }}>
      {loading ? (
        <div className="glass-card" style={{ padding:40 }}><PageLoader /></div>
      ) : viewMode==='table' ? (
        <TableView accounts={accounts} onSelect={id => navigate(`/account?id=${id}`)} getDelta={getDelta} />
      ) : (
        <GridView accounts={accounts} onSelect={id => navigate(`/account?id=${id}`)} />
      )}
      </div>
    </div>
  )
}

/* ─── Table View ─────────────────────────────────────────────────── */
function TableView({ accounts, onSelect, getDelta }: { accounts:any[]; onSelect:(id:string)=>void; getDelta:(d:any)=>React.ReactNode }) {
  return (
    <motion.div initial={{ opacity:0, y:8 }} animate={{ opacity:1, y:0 }} className="glass-card" style={{ overflow:'hidden' }}>
      <div style={{ overflowX:'auto' }}>
        <table className="kavach-table">
          <thead>
            <tr>
              <th>Borrower</th>
              <th>Loan Type</th>
              <th>Industry</th>
              <th>Grade</th>
              <th style={{ minWidth:130 }}>Stress Score</th>
              <th>12M PD</th>
              <th>DPD</th>
              <th>DSCR</th>
              <th>Trend</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {accounts.slice(0, 100).map((acc:any) => {
              const gradeColor = gradeToColor(acc.risk_grade)
              return (
                <tr key={acc.borrower_id} onClick={() => onSelect(acc.borrower_id)}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{ fontWeight:600, color:'var(--text-primary)', fontSize:'0.82rem' }}>{acc.borrower_id}</div>
                      {acc.confidence_level && acc.confidence_level.includes('limited') && (
                        <span style={{ fontSize: '0.62rem', background: 'rgba(249,115,22,0.08)', color: '#f97316', border: '1px solid rgba(249,115,22,0.22)', padding: '1px 5px', borderRadius: 4, fontWeight: 700 }}>NTC</span>
                      )}
                    </div>
                    {acc.business_name && <div style={{ fontSize:'0.7rem', color:'var(--text-muted)', marginTop:1 }}>{acc.business_name}</div>}
                  </td>
                  <td>
                    <span style={{
                      fontSize:'0.72rem', fontWeight:500, padding:'2px 8px', borderRadius:100,
                      background:'rgba(201,168,76,0.06)', color:'var(--accent-gold)', border:'1px solid var(--border-subtle)',
                      whiteSpace:'nowrap'
                    }}>
                      {acc.loan_type}
                    </span>
                  </td>
                  <td style={{ color:'var(--text-secondary)', fontSize:'0.8rem', maxWidth:140 }}>
                    <div style={{ overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{acc.industry}</div>
                  </td>
                  <td><RiskGradeBadge grade={acc.risk_grade} /></td>
                  <td style={{ minWidth:130 }}><StressBar score={acc.stress_score} /></td>
                  <td>
                    <span style={{ fontFamily:'JetBrains Mono,monospace', fontSize:'0.78rem', fontWeight:600, color: acc.pd_probability>0.4 ? '#ef4444' : 'var(--text-secondary)' }}>
                      {(acc.pd_probability*100).toFixed(1)}%
                    </span>
                  </td>
                  <td>
                    <span style={{
                      fontFamily:'JetBrains Mono,monospace', fontSize:'0.78rem', fontWeight:600,
                      padding:'2px 6px', borderRadius:5,
                      background: acc.dpd_current>0 ? 'rgba(239,68,68,0.08)' : 'transparent',
                      color: acc.dpd_current>0 ? '#ef4444' : 'var(--text-muted)',
                    }}>
                      {acc.dpd_current}d
                    </span>
                  </td>
                  <td>
                    <span style={{ fontFamily:'JetBrains Mono,monospace', fontSize:'0.78rem', color: (acc.dscr??2)<1 ? '#f97316' : 'var(--text-secondary)' }}>
                      {acc.dscr?.toFixed(2) ?? '—'}
                    </span>
                  </td>
                  <td>{getDelta(acc.stress_score_delta)}</td>
                  <td style={{ paddingRight:12 }}>
                    <ChevronRight size={14} style={{ color:'var(--text-muted)' }} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {accounts.length > 100 && (
          <div style={{ padding:'10px 16px', textAlign:'center', fontSize:'0.78rem', color:'var(--text-muted)', borderTop:'1px solid var(--border-subtle)' }}>
            Showing 100 of {accounts.length} — use filters to narrow down
          </div>
        )}
      </div>
    </motion.div>
  )
}

/* ─── Grid View ──────────────────────────────────────────────────── */
function GridView({ accounts, onSelect }: { accounts:any[]; onSelect:(id:string)=>void }) {
  return (
    <motion.div
      initial={{ opacity:0 }} animate={{ opacity:1 }}
      style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(96px,1fr))', gap:8 }}
    >
      {accounts.slice(0,350).map((acc:any, i:number) => {
        const color   = gradeToColor(acc.risk_grade)
        const isHigh  = ['C','D'].includes(acc.risk_grade)
        return (
          <motion.button
            key={acc.borrower_id}
            className="hmap-cell"
            initial={{ opacity:0, scale:0.88 }}
            animate={{ opacity:1, scale:1 }}
            transition={{ delay: i*0.0014, type:'spring', stiffness:300, damping:24 }}
            onClick={() => onSelect(acc.borrower_id)}
            style={{ background:`${color}10`, borderColor:`${color}28` }}
            title={`${acc.borrower_id} · ${acc.risk_grade} · Stress: ${acc.stress_score.toFixed(0)}`}
          >
            {isHigh && (
              <div className="pulse-dot" style={{ background:color, position:'absolute', top:6, right:6 }} />
            )}
            {acc.confidence_level && acc.confidence_level.includes('limited') && (
              <div style={{ fontSize: '0.52rem', background: 'rgba(249,115,22,0.15)', color: '#f97316', padding: '0px 3px', borderRadius: 2, position: 'absolute', top: 6, left: 6, fontWeight: 700 }}>NTC</div>
            )}
            <div style={{ fontFamily:'Space Grotesk,sans-serif', fontWeight:700, fontSize:'0.78rem', color }}>{acc.risk_grade}</div>
            <div>
              <div style={{ fontSize:'0.6rem', color:'var(--text-muted)', marginBottom:5, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                #{acc.borrower_id.replace('MSME','').replace(/^0+/,'')}
              </div>
              <div style={{ height:3, borderRadius:100, background:`${color}25`, overflow:'hidden' }}>
                <div style={{ height:'100%', width:`${Math.min(100,acc.stress_score)}%`, background:color, borderRadius:100 }} />
              </div>
            </div>
          </motion.button>
        )
      })}
    </motion.div>
  )
}
