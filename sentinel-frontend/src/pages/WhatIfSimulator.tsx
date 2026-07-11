import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Zap, RefreshCw, ArrowRight, TrendingUp, TrendingDown,
  Search, SlidersHorizontal,
} from 'lucide-react'
import { simulate, predict } from '../lib/api'
import { RiskGradeBadge, StressGauge, PageLoader, gradeToColor, stressToColor } from '../components/ui'
import { motion, AnimatePresence } from 'framer-motion'

const SLIDERS = [
  { key:'dscr_delta',                label:'DSCR Change',          desc:'Debt Service Coverage Ratio delta',       min:-1.5, max:1.5,  step:0.05, fmt:(v:number)=>`${v>=0?'+':''}${v.toFixed(2)}`,   positiveIsBad:false },
  { key:'gst_delay_days',            label:'GST Filing Delay',      desc:'Additional days of GST delay',            min:0,    max:90,   step:5,    fmt:(v:number)=>v===0?'0d':`+${v}d`,              positiveIsBad:true  },
  { key:'bureau_score_delta',        label:'Bureau Score Change',   desc:'Change in CIBIL / bureau score',          min:-150, max:150,  step:10,   fmt:(v:number)=>`${v>=0?'+':''}${v} pts`,          positiveIsBad:false },
  { key:'overdraft_utilization_delta',label:'OD Utilisation Change',desc:'Overdraft utilisation change (%)',        min:-0.5, max:0.5,  step:0.05, fmt:(v:number)=>`${v>=0?'+':''}${(v*100).toFixed(0)}%`, positiveIsBad:true  },
  { key:'dpd_change',                label:'DPD Change',            desc:'Days Past Due change — lower is better', min:-90,  max:90,   step:10,   fmt:(v:number)=>`${v>=0?'+':''}${v}d`,             positiveIsBad:true  },
  { key:'epfo_change_pct',           label:'Workforce Change',      desc:'Employee headcount change (%)',           min:-0.5, max:0.5,  step:0.05, fmt:(v:number)=>`${v>=0?'+':''}${(v*100).toFixed(0)}%`, positiveIsBad:false },
]

const defaults = Object.fromEntries(SLIDERS.map(s => [s.key, 0]))

export default function WhatIfSimulator() {
  const [searchParams] = useSearchParams()
  const [borrowerId, setBorrowerId] = useState(searchParams.get('id') ?? '')
  const [inputId, setInputId]       = useState(searchParams.get('id') ?? '')
  const [original, setOriginal]     = useState<any>(null)
  const [result, setResult]         = useState<any>(null)
  const [changes, setChanges]       = useState<Record<string, number>>(defaults)
  const [simulating, setSimulating] = useState(false)
  const [loadingOrig, setLoadingOrig] = useState(false)

  const loadOriginal = async (bid: string) => {
    if (!bid) return
    setLoadingOrig(true); setResult(null)
    try { setOriginal(await predict(bid)) }
    catch { /* ignore */ }
    finally { setLoadingOrig(false) }
  }

  useEffect(() => { if (borrowerId) loadOriginal(borrowerId) }, [borrowerId])

  const runSim = async () => {
    if (!borrowerId || !original) return
    setSimulating(true)
    try { setResult(await simulate(borrowerId, changes)) }
    catch { /* ignore */ }
    finally { setSimulating(false) }
  }

  const resetAll = () => { setChanges(defaults); setResult(null) }
  const hasChanges = SLIDERS.some(s => changes[s.key] !== 0)

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (inputId.trim()) setBorrowerId(inputId.trim().toUpperCase())
  }

  return (
    <div className="page-content">
      {/* ── Header ────────────────────────────────────────────────── */}
      <div style={{ display:'flex', alignItems:'flex-start', gap:10, marginBottom:20 }}>
        <div style={{ width:32, height:32, borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(201,168,76,0.12)', flexShrink:0, marginTop:2 }}>
          <Zap size={15} style={{ color:'var(--accent-gold)' }} />
        </div>
        <div>
          <h1 className="page-title" style={{ marginBottom:2 }}>What-If Simulator</h1>
          <p className="page-subtitle">Stress-test a borrower's risk by adjusting key parameters</p>
        </div>
      </div>

      {/* ── Search ────────────────────────────────────────────────── */}
      <form onSubmit={handleSearch} style={{ display:'flex', gap:8, marginBottom:20, maxWidth:380 }}>
        <div style={{ position:'relative', flex:1 }}>
          <Search size={13} style={{ position:'absolute', left:10, top:'50%', transform:'translateY(-50%)', color:'var(--text-muted)' }} />
          <input className="input-field" style={{ paddingLeft:32, fontSize:'0.82rem' }} placeholder="Borrower ID (e.g. MSME00042)" value={inputId} onChange={e=>setInputId(e.target.value)} />
        </div>
        <button type="submit" className="btn-primary">Load</button>
      </form>

      {loadingOrig && <div className="glass-card" style={{ padding:48 }}><PageLoader /></div>}

      {/* Empty */}
      {!borrowerId && !loadingOrig && (
        <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} className="glass-card"
          style={{ padding:56, display:'flex', flexDirection:'column', alignItems:'center', gap:14 }}>
          <div style={{ width:56, height:56, borderRadius:16, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(201,168,76,0.04)', border:'1px solid var(--border-subtle)' }}>
            <SlidersHorizontal size={24} style={{ color:'var(--accent-gold)' }} />
          </div>
          <div style={{ textAlign:'center' }}>
            <div style={{ fontWeight:600, color:'var(--text-primary)', marginBottom:4 }}>Run a What-If Scenario</div>
            <div style={{ fontSize:'0.82rem', color:'var(--text-muted)' }}>Load a borrower, adjust parameters, and see the projected risk impact</div>
          </div>
        </motion.div>
      )}

      {original && !loadingOrig && (
        <div style={{ display:'grid', gridTemplateColumns:'1fr 280px', gap:16 }}>

          {/* ── Sliders ─────────────────────────────────────────── */}
          <div className="glass-card" style={{ padding:22 }}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20 }}>
              <div>
                <div className="section-title">Adjust Parameters</div>
                <div className="section-sub">
                  Simulating for <span style={{ fontFamily:'JetBrains Mono,monospace', color:'var(--accent-gold)' }}>{borrowerId}</span>
                </div>
              </div>
              {hasChanges && (
                <button onClick={resetAll} className="btn-ghost" style={{ display:'flex', alignItems:'center', gap:5, fontSize:'0.78rem' }}>
                  <RefreshCw size={12} /> Reset
                </button>
              )}
            </div>

            <div style={{ display:'flex', flexDirection:'column', gap:18 }}>
              {SLIDERS.map(s => {
                const val      = changes[s.key]
                const isDef    = val === 0
                const isBad    = s.positiveIsBad ? val > 0 : val < 0
                const valColor = isDef ? 'var(--text-muted)' : isBad ? '#ef4444' : '#10b981'
                const pct      = ((val - s.min) / (s.max - s.min)) * 100

                return (
                  <div key={s.key}>
                    <div style={{ display:'flex', alignItems:'baseline', justifyContent:'space-between', marginBottom:7 }}>
                      <div>
                        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
                          <span style={{ fontSize:'0.82rem', fontWeight:500, color: isDef ? 'var(--text-secondary)' : 'var(--text-primary)' }}>{s.label}</span>
                          {!isDef && <div style={{ width:6, height:6, borderRadius:'50%', background:valColor, flexShrink:0 }} />}
                        </div>
                        <div style={{ fontSize:'0.72rem', color:'var(--text-muted)', marginTop:2 }}>{s.desc}</div>
                      </div>
                      <span style={{ fontFamily:'JetBrains Mono,monospace', fontSize:'0.82rem', fontWeight:700, color:valColor, marginLeft:12, whiteSpace:'nowrap' }}>
                        {s.fmt(val)}
                      </span>
                    </div>
                    <input
                      type="range" min={s.min} max={s.max} step={s.step} value={val}
                      onChange={e => { setChanges(p => ({ ...p, [s.key]: parseFloat(e.target.value) })); setResult(null) }}
                      style={{ width:'100%', background:`linear-gradient(to right, ${isDef?'rgba(255,255,255,0.12)':valColor} ${pct}%, rgba(255,255,255,0.07) ${pct}%)` }}
                    />
                  </div>
                )
              })}
            </div>

            <div style={{ marginTop:22 }}>
              <button
                onClick={runSim}
                disabled={simulating || !hasChanges}
                className="btn-primary"
                style={{ width:'100%', display:'flex', alignItems:'center', justifyContent:'center', gap:7 }}
              >
                {simulating
                  ? <><div style={{ width:14, height:14, border:'2px solid rgba(0,0,0,0.25)', borderTopColor:'#000', borderRadius:'50%', animation:'spin 0.7s linear infinite' }} /> Simulating…</>
                  : <><Zap size={14} /> Run Simulation</>
                }
              </button>
              {!hasChanges && <div style={{ fontSize:'0.72rem', textAlign:'center', color:'var(--text-muted)', marginTop:6 }}>Adjust at least one parameter</div>}
            </div>
          </div>

          {/* ── Results ─────────────────────────────────────────── */}
          <div style={{ display:'flex', flexDirection:'column', gap:12 }}>

            {/* Current */}
            <div className="glass-card" style={{ padding:16 }}>
              <div style={{ fontSize:'0.68rem', fontWeight:700, textTransform:'uppercase', letterSpacing:'0.07em', color:'var(--text-muted)', marginBottom:12 }}>Current State</div>
              <div style={{ display:'flex', alignItems:'center', gap:12 }}>
                <StressGauge score={original.stress_score} size={80} />
                <div>
                  <RiskGradeBadge grade={original.risk_grade} size="lg" />
                  <div style={{ marginTop:8, display:'flex', flexDirection:'column', gap:3 }}>
                    <div style={{ fontSize:'0.72rem', color:'var(--text-muted)' }}>
                      Score: <span style={{ fontFamily:'JetBrains Mono,monospace', fontWeight:700, color:stressToColor(original.stress_score) }}>{original.stress_score.toFixed(1)}</span>
                    </div>
                    <div style={{ fontSize:'0.72rem', color:'var(--text-muted)' }}>
                      PD: <span style={{ fontFamily:'JetBrains Mono,monospace' }}>{(original.pd_probability*100).toFixed(1)}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Simulated */}
            <AnimatePresence>
              {result && (
                <motion.div
                  initial={{ opacity:0, y:8, scale:0.97 }}
                  animate={{ opacity:1, y:0,  scale:1 }}
                  exit={{ opacity:0, scale:0.97 }}
                  className="glass-card"
                  style={{ padding:16, borderColor:`${gradeToColor(result.simulated_risk_grade)}35` }}
                >
                  <div style={{ fontSize:'0.68rem', fontWeight:700, textTransform:'uppercase', letterSpacing:'0.07em', color:'var(--text-muted)', marginBottom:12 }}>Simulated Outcome</div>
                  <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:12 }}>
                    <StressGauge score={result.simulated_stress_score} size={80} />
                    <div>
                      <RiskGradeBadge grade={result.simulated_risk_grade} size="lg" />
                      <div style={{ fontSize:'0.72rem', color:'var(--text-muted)', marginTop:8 }}>
                        Score: <span style={{ fontFamily:'JetBrains Mono,monospace', fontWeight:700, color:stressToColor(result.simulated_stress_score) }}>{result.simulated_stress_score.toFixed(1)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Delta */}
                  <div style={{
                    padding:'8px 12px', borderRadius:8, marginBottom:10,
                    display:'flex', alignItems:'center', justifyContent:'space-between',
                    background: result.delta_stress_score>0 ? 'rgba(239,68,68,0.07)' : 'rgba(16,185,129,0.07)',
                    border:`1px solid ${result.delta_stress_score>0 ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}`,
                  }}>
                    <span style={{ fontSize:'0.78rem', color:'var(--text-secondary)' }}>Stress Δ</span>
                    <span style={{ fontFamily:'JetBrains Mono,monospace', fontWeight:700, fontSize:'0.9rem', display:'flex', alignItems:'center', gap:4, color: result.delta_stress_score>0 ? '#ef4444' : '#10b981' }}>
                      {result.delta_stress_score>0 ? <TrendingUp size={12}/> : <TrendingDown size={12}/>}
                      {result.delta_stress_score>=0?'+':''}{result.delta_stress_score.toFixed(1)}
                    </span>
                  </div>

                  {result.grade_changed && (
                    <div style={{ padding:'7px 10px', borderRadius:8, marginBottom:10, display:'flex', alignItems:'center', justifyContent:'center', gap:7, background:'rgba(245,158,11,0.07)', border:'1px solid rgba(245,158,11,0.2)', fontSize:'0.78rem', fontWeight:700, color:'#f59e0b' }}>
                      Grade changed! <RiskGradeBadge grade={result.original_risk_grade} size="sm" />
                      <ArrowRight size={10}/> <RiskGradeBadge grade={result.simulated_risk_grade} size="sm" />
                    </div>
                  )}

                  <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
                    {result.delta_explanation?.map((exp:string, i:number) => (
                      <div key={i} style={{ fontSize:'0.72rem', padding:'7px 10px', borderRadius:7, background:'rgba(255,255,255,0.025)', color:'var(--text-secondary)', display:'flex', alignItems:'flex-start', gap:6 }}>
                        <div style={{ width:4, height:4, borderRadius:'50%', background:'#f59e0b', marginTop:4, flexShrink:0 }} />
                        {exp}
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Hint */}
            {!result && !simulating && (
              <div className="glass-card" style={{ padding:24, display:'flex', flexDirection:'column', alignItems:'center', gap:8, border:'1px dashed rgba(255,255,255,0.07)' }}>
                <Zap size={20} style={{ color:'var(--text-muted)' }} />
                <div style={{ fontSize:'0.78rem', color:'var(--text-muted)', textAlign:'center' }}>Adjust parameters and run simulation</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Spin animation */}
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}
