import React, { useEffect, useState } from 'react'
import { Shield, CheckCircle, XCircle, Clock, Download, Activity } from 'lucide-react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Legend
} from 'recharts'
import { getGovernance } from '../lib/api'
import { PageLoader } from '../components/ui'
import { motion } from 'framer-motion'

const TARGETS: Record<string, number> = {
  auc_roc: 0.90,
  precision_at_top10pct: 0.70,
  recall: 0.80,
  false_positive_rate: 0.15,
}

export default function ModelGovernance() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getGovernance()
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="page-content"><PageLoader /></div>
  if (!data) return null

  const metTarget = (key: string, val: number) => {
    const target = TARGETS[key]
    if (key === 'false_positive_rate') return val <= target
    return val >= target
  }

  const radarData = data.per_segment_metrics?.map((m: any) => ({
    subject: m.loan_type.replace(' ', '\n'),
    AUC: Math.round(m.auc_roc * 100),
    Recall: Math.round(m.recall * 100),
    Precision: Math.round(m.precision_at_top10pct * 100),
  })) ?? []

  return (
    <div className="page-content">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(201,168,76,0.12)' }}>
            <Shield size={15} style={{ color: 'var(--accent-gold)' }} />
          </div>
          <div>
            <h1 className="page-title" style={{ marginBottom: 2 }}>Model Governance</h1>
            <p className="page-subtitle">Active model metrics, audit trail, and fairness evaluation</p>
          </div>
        </div>
        <button className="btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Download size={13} /> Export Model Card
        </button>
      </div>

      {/* Model Version Card */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card glass-card-accent" style={{ padding: '18px 20px', marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(201,168,76,0.14)' }}>
              <Shield size={20} style={{ color: 'var(--accent-gold)' }} />
            </div>
            <div>
              <div style={{ fontFamily: "'Cormorant Garamond', 'Space Grotesk', serif", fontWeight: 700, fontSize: '1.25rem', color: '#fff' }}>Model {data.model_version}</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 2 }}>
                {data.algorithm} · {data.feature_count} features
              </div>
            </div>
          </div>
          <div>
            <span className="info-chip" style={{ background: 'rgba(99,102,241,0.08)', color: '#818cf8', borderColor: 'rgba(99,102,241,0.22)', padding: '5px 12px', fontWeight: 600 }}>
              AUC-ROC: {data.avg_auc_roc?.toFixed(4) ?? 'N/A'}
            </span>
          </div>
        </div>

        <div className="divider" style={{ margin: '14px 0' }} />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          {[
            { label: 'Trained At', value: new Date(data.trained_at).toLocaleDateString() },
            { label: 'Train Period', value: `Months ${data.train_months}` },
            { label: 'Test Period', value: `Months ${data.test_months}` },
            { label: 'Calibration', value: 'Isotonic Calibration' },
          ].map(({ label, value }) => (
            <div key={label}>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f1f5f9', marginTop: 3 }}>{value}</div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Metrics Table Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* Performance Metrics */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="glass-card" style={{ padding: 20 }}>
          <span className="section-title">Performance Metrics</span>
          <p className="section-sub" style={{ marginBottom: 16 }}>Key model accuracy and threshold parameters</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {[
              { 
                key: 'avg_auc_roc', 
                label: 'AUC-ROC', 
                value: data.avg_auc_roc, 
                target: 0.90, 
                format: (v: number) => {
                  const ci_lo = data.avg_auc_roc_ci_2p5;
                  const ci_hi = data.avg_auc_roc_ci_97p5;
                  if (ci_lo !== undefined && ci_hi !== undefined && ci_lo !== null && ci_hi !== null) {
                    const delta = (ci_hi - ci_lo) / 2;
                    return `${v.toFixed(4)} ± ${delta.toFixed(4)}`;
                  }
                  return v.toFixed(4);
                } 
              },
              { 
                key: 'avg_precision_at_top10', 
                label: 'Precision @ Top 10%', 
                value: data.avg_precision_at_top10, 
                target: 0.70, 
                format: (v: number) => {
                  const ci_lo = data.avg_precision_at_top10_ci_2p5;
                  const ci_hi = data.avg_precision_at_top10_ci_97p5;
                  if (ci_lo !== undefined && ci_hi !== undefined && ci_lo !== null && ci_hi !== null) {
                    const delta = (ci_hi - ci_lo) / 2;
                    return `${(v * 100).toFixed(1)}% ± ${(delta * 100).toFixed(1)}%`;
                  }
                  return `${(v * 100).toFixed(1)}%`;
                } 
              },
              { 
                key: 'avg_recall', 
                label: 'Recall', 
                value: data.avg_recall, 
                target: 0.80, 
                format: (v: number) => {
                  const ci_lo = data.avg_recall_ci_2p5;
                  const ci_hi = data.avg_recall_ci_97p5;
                  if (ci_lo !== undefined && ci_hi !== undefined && ci_lo !== null && ci_hi !== null) {
                    const delta = (ci_hi - ci_lo) / 2;
                    return `${(v * 100).toFixed(1)}% ± ${(delta * 100).toFixed(1)}%`;
                  }
                  return `${(v * 100).toFixed(1)}%`;
                } 
              },
              { 
                key: 'avg_false_positive_rate', 
                label: 'False Positive Rate', 
                value: data.avg_false_positive_rate, 
                target: 0.15, 
                format: (v: number) => {
                  const ci_lo = data.avg_false_positive_rate_ci_2p5;
                  const ci_hi = data.avg_false_positive_rate_ci_97p5;
                  if (ci_lo !== undefined && ci_hi !== undefined && ci_lo !== null && ci_hi !== null) {
                    const delta = (ci_hi - ci_lo) / 2;
                    return `${(v * 100).toFixed(1)}% ± ${(delta * 100).toFixed(1)}%`;
                  }
                  return `${(v * 100).toFixed(1)}%`;
                }, 
                lowerBetter: true 
              },
            ].map(({ key, label, value, target, format, lowerBetter }) => {
              const met = lowerBetter ? value <= target : value >= target
              return (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {met ? (
                    <CheckCircle size={15} style={{ color: '#10b981', flexShrink: 0 }} />
                  ) : (
                    <XCircle size={15} style={{ color: '#ef4444', flexShrink: 0 }} />
                  )}
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{label}</span>
                      <div style={{ display: 'flex', gap: 8, fontSize: '0.72rem' }}>
                        <span style={{ color: 'var(--text-muted)' }}>
                          target: {lowerBetter ? '≤' : '≥'} {target < 1 ? `${(target * 100).toFixed(0)}%` : target}
                        </span>
                        <span style={{ fontFamily: 'JetBrains Mono,monospace', fontWeight: 700, color: met ? '#10b981' : '#ef4444' }}>
                          {format(value)}
                        </span>
                      </div>
                    </div>
                    <div style={{ height: 4, borderRadius: 100, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          width: `${Math.min(100, value * 100)}%`,
                          background: met ? '#10b981' : '#ef4444',
                          borderRadius: 100
                        }}
                      />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </motion.div>

        {/* Per-Segment Radar */}
        {radarData.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card" style={{ padding: 20, display: 'flex', flexDirection: 'column' }}>
            <span className="section-title">Segment Performance</span>
            <p className="section-sub" style={{ marginBottom: 12 }}>Performance comparison across products</p>
            <div style={{ display: 'flex', gap: 12, flex: 1, alignItems: 'center' }}>
              <div style={{ width: '50%', height: 150 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                    <PolarGrid stroke="rgba(255,255,255,0.04)" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#888', fontSize: 9 }} />
                    <Radar name="AUC" dataKey="AUC" stroke="var(--accent-gold)" fill="var(--accent-gold)" fillOpacity={0.15} />
                    <Radar name="Recall" dataKey="Recall" stroke="#8c8070" fill="#8c8070" fillOpacity={0.05} />
                    <Radar name="Precision" dataKey="Precision" stroke="#7a9c8a" fill="#7a9c8a" fillOpacity={0.05} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {data.per_segment_metrics?.map((m: any) => {
                  const ci_lo = m.auc_roc_ci_2p5;
                  const ci_hi = m.auc_roc_ci_97p5;
                  const ci_str = (ci_lo !== undefined && ci_hi !== undefined && ci_lo !== null && ci_hi !== null) 
                    ? ` ± ${((ci_hi - ci_lo) / 2).toFixed(3)}` 
                    : '';
                  return (
                    <div key={m.loan_type} style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(201,168,76,0.03)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', border: '1px solid var(--border-subtle)' }}>
                      <span style={{ fontSize: '0.78rem', color: '#fff', fontWeight: 500 }}>{m.loan_type}</span>
                      <span style={{ fontSize: '0.75rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--accent-gold)', fontWeight: 600 }}>
                        AUC {m.auc_roc.toFixed(3)}{ci_str}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </motion.div>
        )}
      </div>

      {/* Fairness & Bias Table */}
      {data.fairness && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
          className="glass-card"
          style={{ padding: 20, marginBottom: 20, overflow: 'hidden' }}
        >
          <div style={{ marginBottom: 16 }}>
            <span className="section-title">Model Fairness & Demographic Parity</span>
            <p className="section-sub">
              Wilson Score 95% Confidence Intervals computed on test set (months 21–23) against { (data.fairness.overall.fnr * 100).toFixed(1) }% baseline FNR. Flagged segments deviate by &gt; 5pp.
            </p>
          </div>
          <div className="table-responsive" style={{ overflowX: 'auto' }}>
            <table className="kavach-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.06)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '8px 12px' }}>Industry Segment</th>
                  <th style={{ padding: '8px 12px' }}>FPR</th>
                  <th style={{ padding: '8px 12px' }}>FNR</th>
                  <th style={{ padding: '8px 12px' }}>Defaulters (Pos/Total)</th>
                  <th style={{ padding: '8px 12px' }}>FNR 95% Wilson CI</th>
                  <th style={{ padding: '8px 12px', textAlign: 'right' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.fairness.by_industry)
                  .map(([name, val]: [string, any]) => ({ name, ...val }))
                  .sort((a, b) => {
                    const aFlag = a.status.includes('flag') ? 1 : 0;
                    const bFlag = b.status.includes('flag') ? 1 : 0;
                    return bFlag - aFlag || a.name.localeCompare(b.name);
                  })
                  .map((row: any) => {
                    const isFlagged = row.status.includes('flag');
                    return (
                      <tr
                        key={row.name}
                        style={{
                          borderBottom: '1px solid rgba(255,255,255,0.03)',
                          background: isFlagged ? 'rgba(239,68,68,0.015)' : 'transparent',
                        }}
                      >
                        <td style={{ padding: '10px 12px', fontWeight: 600, color: '#f1f5f9' }}>{row.name}</td>
                        <td style={{ padding: '10px 12px', fontFamily: 'JetBrains Mono,monospace' }}>
                          {row.fpr !== undefined ? `${(row.fpr * 100).toFixed(2)}%` : 'N/A'}
                        </td>
                        <td
                          style={{
                            padding: '10px 12px',
                            fontFamily: 'JetBrains Mono,monospace',
                            color: isFlagged ? '#fca5a5' : 'var(--text-primary)',
                          }}
                        >
                          {row.fnr !== undefined ? `${(row.fnr * 100).toFixed(2)}%` : 'N/A'}
                        </td>
                        <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>
                          {row.n_positive} / {row.n_total}
                        </td>
                        <td style={{ padding: '10px 12px', fontFamily: 'JetBrains Mono,monospace', color: 'var(--text-muted)' }}>
                          {row.fnr_ci_95_lo !== undefined ? `[${(row.fnr_ci_95_lo * 100).toFixed(1)}%, ${(row.fnr_ci_95_hi * 100).toFixed(1)}%]` : 'N/A'}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                          {isFlagged ? (
                            <span
                              className="info-chip"
                              style={{
                                background: 'rgba(239,68,68,0.08)',
                                color: '#ef4444',
                                borderColor: 'rgba(239,68,68,0.25)',
                                fontSize: '0.7rem',
                                padding: '2px 8px',
                              }}
                            >
                              Flagged
                            </span>
                          ) : (
                            <span
                              className="info-chip"
                              style={{
                                background: 'rgba(16,185,129,0.08)',
                                color: '#10b981',
                                borderColor: 'rgba(16,185,129,0.25)',
                                fontSize: '0.7rem',
                                padding: '2px 8px',
                              }}
                            >
                              Passed
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}

      {/* Walk-Forward Backtest Chart */}
      {data.backtest_results && data.backtest_results.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.14 }}
          className="glass-card"
          style={{ padding: 20, marginBottom: 20 }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <Activity size={14} style={{ color: 'var(--accent-gold)' }} />
            <span className="section-title">Walk-Forward Temporal Validation</span>
          </div>
          <p className="section-sub" style={{ marginBottom: 16 }}>
            Model performance across rolling out-of-time windows — confirming stability and absence of temporal data leakage.
          </p>
          <div style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data.backtest_results.map((pt: any) => ({
                  name: pt.window.replace(/Window \d+ \(/, '').replace(')', ''),
                  AUC: +(pt.auc * 100).toFixed(1),
                  Precision: +(pt.precision * 100).toFixed(1),
                  Recall: +(pt.recall * 100).toFixed(1),
                }))}
                margin={{ top: 4, right: 20, left: 0, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="name" tick={{ fill: '#888', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#888', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                <Tooltip
                  contentStyle={{ background: 'rgba(15,15,20,0.95)', border: '1px solid rgba(201,168,76,0.2)', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#f1f5f9', fontWeight: 600, marginBottom: 4 }}
                  formatter={(v: any, name: string) => [`${v}%`, name]}
                />
                <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
                <Line type="monotone" dataKey="AUC" stroke="var(--accent-gold)" strokeWidth={2} dot={{ r: 4, fill: 'var(--accent-gold)' }} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="Precision" stroke="#7a9c8a" strokeWidth={2} dot={{ r: 4, fill: '#7a9c8a' }} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="Recall" stroke="#8c8070" strokeWidth={2} dot={{ r: 4, fill: '#8c8070' }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {/* Summary row */}
          <div style={{ display: 'flex', gap: 12, marginTop: 16, flexWrap: 'wrap' }}>
            {(['AUC', 'Precision', 'Recall'] as const).map((metric, idx) => {
              const key = metric.toLowerCase() as 'auc' | 'precision' | 'recall'
              const vals = data.backtest_results.map((p: any) => p[key])
              const avg = vals.reduce((a: number, b: number) => a + b, 0) / vals.length
              const min = Math.min(...vals)
              const max = Math.max(...vals)
              const colors = ['var(--accent-gold)', '#7a9c8a', '#8c8070']
              return (
                <div key={metric} style={{ flex: 1, minWidth: 120, padding: '10px 14px', borderRadius: 8, background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>{metric}</div>
                  <div style={{ fontSize: '1.1rem', fontFamily: 'JetBrains Mono,monospace', fontWeight: 700, color: colors[idx] }}>
                    {(avg * 100).toFixed(1)}%
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 3 }}>
                    Range: {(min * 100).toFixed(1)}% – {(max * 100).toFixed(1)}%
                  </div>
                </div>
              )
            })}
          </div>
        </motion.div>
      )}

      {/* Audit Log */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="glass-card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
          <span className="section-title">Audit Trail</span>
          <p className="section-sub">Immutable record of model lifecycle events and threshold updates</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {data.audit_log?.map((entry: any, i: number) => (
            <div key={i} style={{ padding: '12px 20px', display: 'flex', alignItems: 'flex-start', gap: 12, borderBottom: i === data.audit_log.length - 1 ? 'none' : '1px solid rgba(255,255,255,0.03)' }}>
              <Clock size={13} style={{ color: 'var(--text-muted)', marginTop: 2, flexShrink: 0 }} />
              <div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{entry.event}</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{new Date(entry.timestamp).toLocaleString()}</span>
                  <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.04)', color: 'var(--text-secondary)' }}>{entry.user}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}
