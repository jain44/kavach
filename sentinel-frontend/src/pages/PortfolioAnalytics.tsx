import React, { useEffect, useState } from 'react'
import { BarChart3, TrendingUp, Users, AlertTriangle, PieChart as PieIcon, MapPin, Briefcase, Download } from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Bar, BarChart
} from 'recharts'
import { getAnalytics } from '../lib/api'
import { MetricCard, PageLoader, RiskGradeBadge, gradeToColor, stressToColor } from '../components/ui'
import { motion } from 'framer-motion'

const GRADE_COLORS: Record<string, string> = {
  AAA: '#10b981', AA: '#34d399', A: '#6ee7b7',
  BBB: '#fbbf24', BB: '#f59e0b', B: '#f97316',
  C: '#ef4444', D: '#991b1b',
}

export default function PortfolioAnalytics() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [segmentView, setSegmentView] = useState<'loan_type' | 'industry' | 'region'>('loan_type')

  useEffect(() => {
    getAnalytics()
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="page-content"><PageLoader /></div>
  if (!data) return null

  const segmentData =
    segmentView === 'loan_type' ? data.loan_type_breakdown :
    segmentView === 'industry' ? data.industry_breakdown :
    data.region_breakdown

  const totalAccounts = data.total_accounts ?? 0
  const avgStress = data.portfolio_avg_stress ?? 0
  const highRisk = data.high_risk_accounts ?? 0

  return (
    <div className="page-content">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(201,168,76,0.12)', flexShrink: 0, marginTop: 2 }}>
            <BarChart3 size={15} style={{ color: 'var(--accent-gold)' }} />
          </div>
          <div>
            <h1 className="page-title" style={{ marginBottom: 2 }}>Portfolio Analytics</h1>
            <p className="page-subtitle">Aggregate stress trends, segment comparisons, and distribution analysis</p>
          </div>
        </div>
        <button onClick={() => window.print()} className="btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Download size={13} /> Export to PDF
        </button>
      </div>

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
        {[
          { label: 'Total Accounts', value: totalAccounts.toLocaleString(), sub: 'active portfolio size', icon: <Users size={18} />, color: 'var(--accent-gold)' },
          { label: 'Portfolio Avg Stress', value: avgStress.toFixed(1), sub: 'out of 100 max', icon: <BarChart3 size={18} />, color: avgStress > 40 ? '#ef4444' : '#10b981', accent: avgStress > 40 },
          { label: 'High Risk Accounts', value: highRisk.toLocaleString(), sub: `${totalAccounts ? ((highRisk / totalAccounts) * 100).toFixed(1) : 0}% of portfolio`, icon: <AlertTriangle size={18} />, color: '#f97316' },
          { label: 'Grade AAA (Safest)', value: (data.grade_distribution.find((g: any) => g.grade === 'AAA')?.count ?? 0).toLocaleString(), sub: 'top tier credit risk', icon: <TrendingUp size={18} />, color: '#10b981' }
        ].map((c, i) => (
          <motion.div
            key={c.label}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className={`glass-card ${c.accent ? 'glass-card-accent' : ''}`}
            style={{ padding: '18px 20px' }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
              <span className="metric-label">{c.label}</span>
              <div style={{ width: 30, height: 30, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', background: `${c.color}14`, color: c.color, flexShrink: 0 }}>
                {c.icon}
              </div>
            </div>
            <div className="metric-value" style={{ color: c.color, fontSize: '1.75rem' }}>{c.value}</div>
            <div style={{ fontSize: '0.75rem', marginTop: 5, color: 'var(--text-muted)' }}>{c.sub}</div>
          </motion.div>
        ))}
      </div>

      {/* Stress Trend */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card" style={{ padding: 20, marginBottom: 20 }}>
        <div style={{ marginBottom: 16 }}>
          <span className="section-title">Portfolio Stress Trend</span>
          <p className="section-sub">Average stress score and high-risk account count over time</p>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={data.stress_trend} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
            <defs>
              <linearGradient id="stressAreaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--accent-gold)" stopOpacity={0.15} />
                <stop offset="95%" stopColor="var(--accent-gold)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="month" tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis yAxisId="stress" domain={[0, 60]} tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis yAxisId="count" orientation="right" tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: 'var(--bg-surface)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, fontSize: 12 }}
              labelStyle={{ color: '#94a3b8' }}
            />
            <Area
              yAxisId="stress"
              type="monotone"
              dataKey="avg_stress_score"
              name="Avg Stress Score"
              stroke="var(--accent-gold)"
              strokeWidth={2}
              fill="url(#stressAreaGrad)"
              dot={false}
            />
            <Bar yAxisId="count" dataKey="high_risk_count" name="High Risk Count" fill="rgba(239,68,68,0.22)" radius={[2, 2, 0, 0]} />
          </AreaChart>
        </ResponsiveContainer>
      </motion.div>

      {/* Segment + Grade Distribution Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* Segment Breakdown */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div>
              <span className="section-title">Segment Breakdown</span>
              <p className="section-sub">Average stress by dimensions</p>
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              {[
                { v: 'loan_type', lbl: 'Loan Type', icon: <Briefcase size={11} /> },
                { v: 'industry', lbl: 'Industry', icon: <Users size={11} /> },
                { v: 'region', lbl: 'Region', icon: <MapPin size={11} /> }
              ].map((opt) => (
                <button
                  key={opt.v}
                  onClick={() => setSegmentView(opt.v as any)}
                  className={`filter-pill ${segmentView === opt.v ? 'active' : ''}`}
                  style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.75rem', padding: '4px 10px' }}
                >
                  {opt.icon} {opt.lbl}
                </button>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {segmentData?.slice(0, 6).map((seg: any) => (
              <div key={seg.segment}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{seg.segment}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: '0.72rem', color: seg.high_risk_pct > 15 ? '#ef4444' : 'var(--text-muted)' }}>
                      {seg.high_risk_pct.toFixed(1)}% High Risk
                    </span>
                    <span style={{ fontSize: '0.78rem', fontFamily: 'JetBrains Mono,monospace', fontWeight: 600, color: stressToColor(seg.avg_stress_score) }}>
                      {seg.avg_stress_score.toFixed(1)}
                    </span>
                  </div>
                </div>
                <div style={{ height: 5, borderRadius: 100, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      width: `${Math.min(100, seg.avg_stress_score)}%`,
                      background: stressToColor(seg.avg_stress_score),
                      borderRadius: 100
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Grade Pie */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="glass-card" style={{ padding: 20 }}>
          <div style={{ marginBottom: 12 }}>
            <span className="section-title">Grade Distribution</span>
            <p className="section-sub">Overview of active rating grades</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ width: '45%', height: 160 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.grade_distribution.filter((g: any) => g.count > 0)}
                    cx="50%"
                    cy="50%"
                    outerRadius={65}
                    innerRadius={45}
                    dataKey="count"
                    nameKey="grade"
                    strokeWidth={1.5}
                    stroke="var(--bg-surface)"
                  >
                    {data.grade_distribution.filter((g: any) => g.count > 0).map((entry: any) => (
                      <Cell key={entry.grade} fill={GRADE_COLORS[entry.grade] ?? '#64748b'} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, fontSize: 11 }}
                    formatter={(val: any, name: any) => [`${val} accounts`, name]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
              {data.grade_distribution.filter((g: any) => g.count > 0).map((g: any) => (
                <div key={g.grade} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: GRADE_COLORS[g.grade] }} />
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    {g.grade} <span style={{ color: 'var(--text-muted)', fontFamily: 'JetBrains Mono,monospace' }}>{g.percentage}%</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

      {/* Quarter over Quarter Default Predictions Comparison */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* Q/Q Chart */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }} className="glass-card" style={{ padding: 20 }}>
          <div style={{ marginBottom: 12 }}>
            <span className="section-title">Quarter-over-Quarter Predictions Comparison</span>
            <p className="section-sub">Average default stress comparison (Current vs Prior Quarter)</p>
          </div>
          {data.quarter_comparison && data.quarter_comparison.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={data.quarter_comparison} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
                <XAxis dataKey="segment" tick={{ fill: '#888', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#888', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, fontSize: 11 }}
                  formatter={(val: any) => [`${val}`, 'Avg Stress']}
                />
                <Bar dataKey="prior_q_avg_pd" name="Prior Quarter" fill="#2e4960" radius={[2, 2, 0, 0]} />
                <Bar dataKey="current_q_avg_pd" name="Current Quarter" fill="var(--accent-gold)" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>Comparison data unavailable</div>
          )}
        </motion.div>

        {/* Q/Q Metrics List */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.22 }} className="glass-card" style={{ padding: 20 }}>
          <div style={{ marginBottom: 12 }}>
            <span className="section-title">Risk Change Summary</span>
            <p className="section-sub">Quarterly delta across product lines</p>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.quarter_comparison?.map((qc: any) => {
              const worsened = qc.delta_pp > 0;
              return (
                <div key={qc.segment} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 10, background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.03)' }}>
                  <div>
                    <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)' }}>{qc.segment}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 2 }}>
                      Prior Q: {qc.prior_q_avg_pd.toFixed(1)} · Current Q: {qc.current_q_avg_pd.toFixed(1)}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: '0.78rem', fontFamily: 'JetBrains Mono,monospace', fontWeight: 700, color: worsened ? '#ef4444' : '#10b981' }}>
                      {worsened ? '+' : ''}{qc.delta_pp.toFixed(1)}
                    </span>
                    <span style={{ fontSize: '0.68rem', padding: '2px 8px', borderRadius: 6, background: worsened ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)', color: worsened ? '#ef4444' : '#10b981' }}>
                      {worsened ? 'Worsening' : 'Improving'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>
      </div>

      {/* Industry Summary Table */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass-card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
          <span className="section-title">Industry Risk Summary</span>
          <p className="section-sub">Average stress score and high-risk exposure by industry sector</p>
        </div>
        <table className="kavach-table">
          <thead>
            <tr>
              <th>Industry</th>
              <th>Accounts</th>
              <th style={{ minWidth: 150 }}>Avg Stress Score</th>
              <th>High Risk %</th>
              <th>Risk Level</th>
            </tr>
          </thead>
          <tbody>
            {data.industry_breakdown?.map((row: any) => (
              <tr key={row.segment} style={{ cursor: 'default' }}>
                <td style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.82rem' }}>{row.segment}</td>
                <td>{row.count.toLocaleString()}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 100, height: 5, borderRadius: 100, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                      <div style={{ width: `${row.avg_stress_score}%`, height: '100%', background: stressToColor(row.avg_stress_score), borderRadius: 100 }} />
                    </div>
                    <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{row.avg_stress_score.toFixed(1)}</span>
                  </div>
                </td>
                <td style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: '0.78rem', color: row.high_risk_pct > 20 ? '#ef4444' : row.high_risk_pct > 10 ? 'var(--accent-gold)' : 'var(--text-muted)' }}>
                  {row.high_risk_pct.toFixed(1)}%
                </td>
                <td>
                  <span
                    className="info-chip"
                    style={{
                      background: row.avg_stress_score > 60 ? 'rgba(239,68,68,0.08)' : row.avg_stress_score > 40 ? 'rgba(201,168,76,0.06)' : 'rgba(16,185,129,0.08)',
                      color: row.avg_stress_score > 60 ? '#ef4444' : row.avg_stress_score > 40 ? 'var(--accent-gold)' : '#10b981',
                      borderColor: row.avg_stress_score > 60 ? 'rgba(239,68,68,0.2)' : row.avg_stress_score > 40 ? 'var(--border-subtle)' : 'rgba(16,185,129,0.2)'
                    }}
                  >
                    {row.avg_stress_score > 60 ? 'High' : row.avg_stress_score > 40 ? 'Moderate' : 'Low'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </motion.div>
    </div>
  )
}
