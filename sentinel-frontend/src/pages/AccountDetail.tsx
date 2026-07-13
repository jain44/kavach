import React, { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Search, AlertTriangle, FileText,
  Zap, Building2, Activity, Calendar, Tag, Cpu,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { predict, explain, getAccountHistory, getAccountNotes, postAccountNote } from '../lib/api'
import {
  RiskGradeBadge, StressGauge, ReasonCodeCard,
  PageLoader, stressToColor, gradeToColor,
} from '../components/ui'
import { motion, AnimatePresence } from 'framer-motion'

const FEATURE_LABELS: Record<string, string> = {
  dscr: "Debt Service Coverage Ratio (DSCR)",
  dscr_slope_3m: "DSCR is declining over the last 3 months",
  dscr_slope_6m: "DSCR has a downward trend over 6 months",
  dscr_slope_12m: "DSCR is weakening over the last 12 months",
  dscr_min_3m: "DSCR minimum in last 3 months is low",
  dscr_below_1_count_6m: "Number of months DSCR was below 1.0",
  dscr_volatility_12m: "High volatility in DSCR over 12 months",
  dscr_x_industry_risk: "DSCR is low relative to industry sector risk",
  bureau_score: "CIBIL / Bureau credit score is low",
  bureau_slope_3m: "Credit bureau score is declining",
  bureau_score_change_6m: "Drop in bureau score over 6 months",
  gst_turnover_lakhs: "GST turnover is lower than expected",
  gst_delay_avg_6m: "Average GST filing delay is elevated",
  gst_delayed_count_6m: "Number of delayed GST filings is high",
  gst_missed_count_6m: "Frequent missed GST filings",
  gst_consecutive_miss_run: "Consecutive missed GST filing streak",
  gst_turnover_slope_3m: "GST turnover has been declining recently",
  gst_turnover_yoy_growth: "GST turnover has negative Year-over-Year growth",
  gst_turnover_seasonal_adj: "Seasonally adjusted GST turnover is low",
  bank_avg_balance_lakhs: "Average bank balance is low",
  balance_slope_3m: "Average bank balance is declining",
  balance_volatility_trend: "Bank balance volatility is high",
  loan_to_balance_ratio: "High ratio of loan amount to bank balance",
  overdraft_utilization_pct: "Overdraft utilization is elevated",
  od_util_slope_3m: "Overdraft utilization is rising",
  od_util_above_80_count_6m: "Frequent overdraft utilization above 80%",
  od_balance_squeeze: "Overdraft utilization squeezing bank balance",
  epfo_employee_count: "Employee count is low or declining",
  epfo_slope_6m: "Workforce size is declining over 6 months",
  epfo_pct_change_6m: "Workforce size decreased over 6 months",
  dpd_current: "Days Past Due (DPD) is elevated",
  dpd_max_12m: "Peak DPD in last 12 months is high",
  dpd_count_30plus_6m: "Frequent payments delayed over 30 days",
  dpd_count_60plus_6m: "Payments delayed over 60 days in last 6 months",
  dpd_escalating: "DPD is escalating month-over-month",
  dpd_recency_weighted_6m: "Recent escalation in Days Past Due (DPD)",
  gst_sentiment: "Negative sentiment in GST remarks/filing",
  txn_anomaly_score: "High transaction anomaly score flagged",
  litigation_flag: "Active litigation cases found",
  litigation_severity: "High severity of litigation cases",
  news_sentiment: "Negative news sentiment score",
  litigation_ever: "Has history of litigation cases",
};

export default function AccountDetail() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [borrowerId, setBorrowerId]     = useState(searchParams.get('id') ?? '')
  const [inputId, setInputId]           = useState(searchParams.get('id') ?? '')
  const [prediction, setPrediction]     = useState<any>(null)
  const [explanation, setExplanation]   = useState<any>(null)
  const [history, setHistory]           = useState<any[]>([])
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState('')

  const [notes, setNotes]               = useState<any[]>([])
  const [newNote, setNewNote]           = useState('')
  const [savingNote, setSavingNote]     = useState(false)

  const fetchNotes = async (bid: string) => {
    try {
      const data = await getAccountNotes(bid)
      setNotes(data.notes || [])
    } catch { /* ignore */ }
  }

  const fetchHistory = async (bid: string) => {
    try {
      const data = await getAccountHistory(bid)
      const mapped = data.history.map((h: any) => ({
        month: h.month,
        stress: h.stress_score,
        pd: h.pd_probability,
        forecast: false
      }))
      setHistory(mapped)
    } catch {
      buildHistory(30)
    }
  }

  const fetchAccount = async (bid: string) => {
    if (!bid) return
    setLoading(true); setError(''); setPrediction(null); setExplanation(null)
    try {
      const [pred, expl] = await Promise.all([predict(bid), explain(bid)])
      setPrediction(pred)
      setExplanation(expl)
      await Promise.all([fetchHistory(bid), fetchNotes(bid)])
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Borrower not found')
    } finally { setLoading(false) }
  }

  const buildHistory = (base: number) => {
    const labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    setHistory(labels.map((m, i) => {
      const s = Math.max(5, Math.min(95, (base-18)*(i/11)+10 + Math.sin(i*0.9)*5))
      return { month:m, stress:Math.round(s), forecast:false }
    }))
  }

  const handleSaveNote = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newNote.trim() || !borrowerId) return
    setSavingNote(true)
    try {
      const saved = await postAccountNote(borrowerId, newNote.trim())
      setNotes(prev => [saved, ...prev])
      setNewNote('')
    } catch (err) {
      alert("Failed to save note")
    } finally {
      setSavingNote(false)
    }
  }

  useEffect(() => { if (borrowerId) fetchAccount(borrowerId) }, [borrowerId])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (inputId.trim()) {
      const id = inputId.trim().toUpperCase()
      setBorrowerId(id); setSearchParams({ id })
    }
  }

  const color      = prediction ? stressToColor(prediction.stress_score) : '#64748b'
  const gradeColor = prediction ? gradeToColor(prediction.risk_grade)    : '#64748b'
  const riskLabel  = prediction
    ? prediction.stress_score > 60 ? 'High Risk'
    : prediction.stress_score > 30 ? 'Moderate Risk' : 'Low Risk'
    : ''

  // Split history into two series for solid vs dashed line
  const histOnly     = history.filter(h => !h.forecast)
  const forecastOnly = history.filter(h =>  h.forecast)
  // Recharts needs overlap point so the two lines connect
  const histLine     = [...histOnly, forecastOnly[0]].filter(Boolean)
  const forecastLine = [histOnly[histOnly.length-1], ...forecastOnly].filter(Boolean)

  return (
    <div className="page-content">
      {/* ── Back + Header ─────────────────────────────────────────── */}
      <div className="page-header">
        <button onClick={() => navigate(-1)} className="btn-ghost" style={{ display:'flex', alignItems:'center', gap:5, paddingLeft:0, marginBottom:14, color:'var(--text-muted)' }}>
          <ArrowLeft size={14} /> Back to Portfolio
        </button>

        <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', flexWrap:'wrap', gap:12 }}>
          <div>
            <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:4 }}>
              <div style={{ width:32, height:32, borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(201,168,76,0.12)' }}>
                <Building2 size={15} style={{ color:'var(--accent-gold)' }} />
              </div>
              <h1 className="page-title" style={{ marginBottom:0 }}>Account Detail</h1>
            </div>
            <p className="page-subtitle" style={{ paddingLeft:42 }}>Risk profile, SHAP explainability & stress trajectory</p>
          </div>
          <form onSubmit={handleSearch} style={{ display:'flex', gap:8 }}>
            <div style={{ position:'relative' }}>
              <Search size={13} style={{ position:'absolute', left:10, top:'50%', transform:'translateY(-50%)', color:'var(--text-muted)' }} />
              <input className="input-field" style={{ paddingLeft:32, width:200, fontSize:'0.82rem' }} placeholder="e.g. MSME00231" value={inputId} onChange={e=>setInputId(e.target.value)} />
            </div>
            <button type="submit" className="btn-primary">Lookup</button>
          </form>
        </div>
      </div>

      {/* ── Empty state ────────────────────────────────────────────── */}
      {!borrowerId && !loading && (
        <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} className="glass-card"
          style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', padding:'64px 24px', gap:16 }}>
          <div style={{ width:56, height:56, borderRadius:16, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(201,168,76,0.04)', border:'1px solid var(--border-subtle)' }}>
            <Search size={24} style={{ color:'var(--accent-gold)' }} />
          </div>
          <div style={{ textAlign:'center' }}>
            <div style={{ fontWeight:600, color:'var(--text-primary)', marginBottom:4 }}>Search a borrower</div>
            <div style={{ fontSize:'0.82rem', color:'var(--text-muted)' }}>Enter an ID like <span style={{ fontFamily:'JetBrains Mono,monospace', color:'var(--text-secondary)' }}>MSME00231</span> to view their full profile</div>
          </div>
        </motion.div>
      )}

      {loading && <div className="glass-card" style={{ padding:48 }}><PageLoader /></div>}

      {error && !loading && (
        <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} className="glass-card"
          style={{ padding:40, display:'flex', flexDirection:'column', alignItems:'center', gap:10, border:'1px solid rgba(239,68,68,0.2)' }}>
          <AlertTriangle size={28} style={{ color:'#ef4444' }} />
          <div style={{ fontWeight:600, color:'#ef4444' }}>{error}</div>
          <div style={{ fontSize:'0.82rem', color:'var(--text-muted)' }}>Check the borrower ID and try again</div>
        </motion.div>
      )}

      {/* ── Account Profile ────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        {prediction && !loading && (
          <motion.div key={borrowerId} initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }} style={{ display:'flex', flexDirection:'column', gap:16 }}>

            {/* Hero row */}
            <div style={{ display:'grid', gridTemplateColumns:'220px 1fr', gap:16 }}>

              {/* Gauge card */}
              <div className="glass-card" style={{ padding:20, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:12, borderColor:`${gradeColor}28` }}>
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', width:'100%' }}>
                  <span style={{ fontSize:'0.68rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'0.07em', color:'var(--text-muted)' }}>Stress Score</span>
                  <RiskGradeBadge grade={prediction.risk_grade} size="md" />
                </div>
                <StressGauge score={prediction.stress_score} size={130} />
                <div style={{ textAlign:'center' }}>
                  <div style={{ fontSize:'0.72rem', fontWeight:700, textTransform:'uppercase', letterSpacing:'0.06em', padding:'3px 12px', borderRadius:100, background:`${color}14`, color, marginBottom:6 }}>
                    {riskLabel}
                  </div>
                  <div style={{ fontSize:'0.75rem', color:'var(--text-muted)' }}>
                    12M PD: <span style={{ fontFamily:'JetBrains Mono,monospace', fontWeight:700, color }}>{(prediction.pd_probability*100).toFixed(2)}%</span>
                  </div>
                </div>
              </div>

              {/* Profile card */}
              <div className="glass-card" style={{ padding:20 }}>
                <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:18, flexWrap:'wrap', gap:10 }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ fontFamily:'Space Grotesk,sans-serif', fontWeight:700, fontSize:'1.4rem', color:'var(--text-primary)' }}>{prediction.borrower_id}</div>
                      {prediction.confidence_level && prediction.confidence_level.includes('limited') && (
                        <span className="info-chip" style={{ background: 'rgba(249,115,22,0.08)', color: '#f97316', borderColor: 'rgba(249,115,22,0.22)', padding: '2px 8px', fontWeight: 600, fontSize: '0.7rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <AlertTriangle size={10} /> NTC ({prediction.confidence_level.match(/\((\d+mo)\)/)?.[1] ?? 'limited'})
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize:'0.82rem', color:'var(--text-muted)', marginTop:2 }}>{prediction.industry} · {prediction.loan_type}</div>
                  </div>
                  <div style={{ display:'flex', gap:8 }}>
                    <button onClick={() => navigate(`/simulator?id=${prediction.borrower_id}`)} className="btn-primary" style={{ display:'flex', alignItems:'center', gap:6 }}>
                      <Zap size={13} /> What-If
                    </button>
                    <button className="btn-secondary" style={{ display:'flex', alignItems:'center', gap:6 }}>
                      <FileText size={13} /> Export
                    </button>
                  </div>
                </div>

                <div style={{ display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:10 }}>
                  {[
                    { label:'Borrower ID',   value: prediction.borrower_id,                          icon:<Tag size={11}/> },
                    { label:'Loan Type',     value: prediction.loan_type,                             icon:<FileText size={11}/> },
                    { label:'Industry',      value: prediction.industry,                              icon:<Building2 size={11}/> },
                    { label:'As of Month',   value: prediction.as_of_date,                           icon:<Calendar size={11}/> },
                    { label:'Model',         value: prediction.model_version,                        icon:<Cpu size={11}/> },
                    { label:'PD Probability',value:`${(prediction.pd_probability*100).toFixed(2)}%`, icon:<Activity size={11}/>, highlight:true },
                  ].map(({ label, value, icon, highlight }) => (
                    <div key={label} style={{
                      padding:'10px 12px', borderRadius:10,
                      background: highlight ? `${color}08` : 'rgba(255,255,255,0.02)',
                      border: `1px solid ${highlight ? `${color}22` : 'rgba(255,255,255,0.05)'}`,
                    }}>
                      <div style={{ display:'flex', alignItems:'center', gap:5, color:'var(--text-muted)', marginBottom:4 }}>
                        {icon} <span style={{ fontSize:'0.7rem' }}>{label}</span>
                      </div>
                      <div style={{ fontSize:'0.82rem', fontWeight:600, color: highlight ? color : 'var(--text-primary)', fontFamily: label==='Borrower ID'||label==='Model'||label==='PD Probability' ? 'JetBrains Mono,monospace' : 'inherit' }}>
                        {value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Stress Trend */}
            {history.length > 0 && (
              <div className="glass-card" style={{ padding:20 }}>
                <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:16, flexWrap:'wrap', gap:8 }}>
                  <div>
                    <div className="section-title">Stress Score Trajectory</div>
                    <div className="section-sub">12-month history + 6-month forecast</div>
                  </div>
                  <div style={{ display:'flex', gap:16, fontSize:'0.75rem' }}>
                    {[
                      { c: color,     l:'Historical' },
                      { c: 'var(--accent-gold)', l:'Forecast',  dashed:true },
                      { c: 'rgba(201,168,76,0.4)', l:'Alert @ 45' },
                    ].map(x => (
                      <div key={x.l} style={{ display:'flex', alignItems:'center', gap:5 }}>
                        <div style={{ width:20, height:2, background: x.dashed ? 'repeating-linear-gradient(90deg,var(--accent-gold) 0,var(--accent-gold) 4px,transparent 4px,transparent 8px)' : x.c, borderRadius:100 }} />
                        <span style={{ color:'var(--text-muted)' }}>{x.l}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={history} margin={{ top:4, right:8, bottom:0, left:-20 }}>
                    <defs>
                      <linearGradient id={`grad-hist-${borrowerId}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={color} stopOpacity={0.18} />
                        <stop offset="95%" stopColor={color} stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id={`grad-fore-${borrowerId}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor="var(--accent-gold)" stopOpacity={0.12} />
                        <stop offset="95%" stopColor="var(--accent-gold)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="month" tick={{ fill:'#475569', fontSize:10 }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0,100]} tick={{ fill:'#475569', fontSize:10 }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background:'var(--bg-surface)', border:'1px solid rgba(255,255,255,0.1)', borderRadius:10, fontSize:12 }}
                      labelStyle={{ color:'#94a3b8' }}
                      formatter={(v:any) => [`${v}/100`, 'Stress Score']}
                    />
                    <ReferenceLine y={45} stroke="rgba(201,168,76,0.35)" strokeDasharray="5 4"
                      label={{ value:'Alert', fill:'var(--accent-gold)', fontSize:9, position:'right' }} />
                    {/* Historical — solid */}
                    <Area type="monotone" data={histLine} dataKey="stress"
                      stroke={color} strokeWidth={2.5}
                      fill={`url(#grad-hist-${borrowerId})`} dot={false}
                      activeDot={{ r:5, fill:color, stroke:'#0d1117', strokeWidth:2 }} />
                    {/* Forecast — dashed */}
                    <Area type="monotone" data={forecastLine} dataKey="stress"
                      stroke="var(--accent-gold)" strokeWidth={2} strokeDasharray="6 4"
                      fill={`url(#grad-fore-${borrowerId})`} dot={false} fillOpacity={0.5} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* SHAP Reason Codes */}
            {explanation?.top_reason_codes?.length > 0 && (() => {
              const mappedReasons = explanation.top_reason_codes.map((r: any) => ({
                ...r,
                description: FEATURE_LABELS[r.feature]
                  ? `${FEATURE_LABELS[r.feature]} (Value: ${r.feature_value !== undefined && r.feature_value !== null ? (typeof r.feature_value === 'number' ? r.feature_value.toFixed(2) : r.feature_value) : 'N/A'})`
                  : r.description
              }));

              return (
                <div className="glass-card" style={{ padding:20 }}>
                  <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:16, flexWrap:'wrap', gap:10 }}>
                    <div>
                      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
                        <div style={{ width:28, height:28, borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(201,168,76,0.12)' }}>
                          <Activity size={13} style={{ color:'var(--accent-gold)' }} />
                        </div>
                        <span className="section-title">Risk Drivers (SHAP)</span>
                      </div>
                      <div className="section-sub" style={{ paddingLeft:36 }}>Top factors driving this risk score</div>
                    </div>
                    <span className="info-chip" style={{ background:'rgba(201,168,76,0.06)', color:'var(--accent-gold)', borderColor:'var(--border-accent)' }}>
                      SHAP Explainability
                    </span>
                  </div>

                  {explanation.narrative_summary && (
                    <div style={{ padding:'12px 14px', borderRadius:10, background:'rgba(201,168,76,0.04)', border:'1px solid var(--border-subtle)', marginBottom:14 }}>
                      <div style={{ fontSize:'0.7rem', fontWeight:700, textTransform:'uppercase', letterSpacing:'0.06em', color:'var(--accent-gold)', marginBottom:5 }}>AI Summary</div>
                      <p style={{ fontSize:'0.82rem', lineHeight:1.6, color:'var(--text-secondary)' }}>{explanation.narrative_summary}</p>
                    </div>
                  )}

                  <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(360px, 1fr))', gap:14 }}>
                    {mappedReasons.map((r:any, i:number) => (
                      <ReasonCodeCard key={i} reason={r} rank={i} />
                    ))}
                  </div>
                </div>
              );
            })()}

            {/* RM Notes & Flag Field */}
            <div className="glass-card" style={{ padding:20 }}>
              <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:16 }}>
                <div style={{ width:28, height:28, borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(201,168,76,0.12)' }}>
                  <FileText size={14} style={{ color:'var(--accent-gold)' }} />
                </div>
                <span className="section-title">Relationship Manager Notes & Flags</span>
              </div>
              
              <form onSubmit={handleSaveNote} style={{ display:'flex', flexDirection:'column', gap:10, marginBottom:16 }}>
                <textarea
                  className="input-field"
                  style={{ height:80, padding:10, fontSize:'0.82rem', resize:'none', background:'rgba(255,255,255,0.02)', borderColor:'var(--border-subtle)' }}
                  placeholder="Enter RM follow-up notes, audit updates or risk flags here..."
                  value={newNote}
                  onChange={e => setNewNote(e.target.value)}
                />
                <div style={{ display:'flex', justifyContent:'flex-end' }}>
                  <button type="submit" className="btn-primary" disabled={savingNote || !newNote.trim()} style={{ fontSize:'0.78rem', padding:'6px 16px' }}>
                    {savingNote ? 'Saving...' : 'Add Note'}
                  </button>
                </div>
              </form>

              <div style={{ display:'flex', flexDirection:'column', gap:10, maxHeight:200, overflowY:'auto', paddingRight:4 }}>
                {notes.length === 0 ? (
                  <div style={{ fontSize:'0.78rem', color:'var(--text-muted)', textAlign:'center', padding:10 }}>No RM notes on record for this borrower.</div>
                ) : (
                  notes.map((n: any) => (
                    <div key={n.id} style={{ padding:'10px 12px', borderRadius:10, background:'rgba(255,255,255,0.015)', border:'1px solid rgba(255,255,255,0.03)' }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:5 }}>
                        <span style={{ fontSize:'0.72rem', fontWeight:700, color:'var(--accent-gold)' }}>RM: {n.created_by}</span>
                        <span style={{ fontSize:'0.68rem', color:'var(--text-muted)' }}>{new Date(n.created_at).toLocaleString()}</span>
                      </div>
                      <p style={{ fontSize:'0.8rem', color:'var(--text-secondary)', lineHeight:1.4 }}>{n.note_text}</p>
                    </div>
                  ))
                )}
              </div>
            </div>

          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
