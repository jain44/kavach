import React from 'react'

const GRADE_ORDER = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'C', 'D'] as const
export type RiskGrade = typeof GRADE_ORDER[number]

interface RiskGradeBadgeProps {
  grade: string
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export const RiskGradeBadge = ({ grade, size = 'md', showLabel = false }: RiskGradeBadgeProps) => {
  const sizeClass = {
    sm: 'text-xs px-2 py-0.5 min-w-[36px]',
    md: 'text-xs px-2.5 py-1 min-w-[44px]',
    lg: 'text-sm px-3 py-1.5 min-w-[52px]',
  }[size]

  return (
    <span className={`grade-badge grade-${grade} ${sizeClass}`}>
      {grade}
    </span>
  )
}

// Stress bar with gradient fill based on value
interface StressBarProps {
  score: number
  showValue?: boolean
  height?: number
}

export const StressBar = ({ score, showValue = true, height = 6 }: StressBarProps) => {
  const getColor = (s: number) => {
    if (s < 20) return '#10b981'
    if (s < 40) return '#fbbf24'
    if (s < 60) return '#f97316'
    if (s < 80) return '#ef4444'
    return '#991b1b'
  }

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 stress-bar-track" style={{ height }}>
        <div
          className="stress-bar-fill"
          style={{
            width: `${Math.min(100, score)}%`,
            background: getColor(score),
          }}
        />
      </div>
      {showValue && (
        <span
          className="font-mono text-xs font-medium w-8 text-right flex-shrink-0"
          style={{ color: getColor(score) }}
        >
          {score.toFixed(0)}
        </span>
      )}
    </div>
  )
}

// Circular stress gauge
interface StressGaugeProps {
  score: number
  size?: number
}

export const StressGauge = ({ score, size = 120 }: StressGaugeProps) => {
  const radius = (size - 20) / 2
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference * (1 - score / 100)

  const getColor = (s: number) => {
    if (s < 20) return '#10b981'
    if (s < 40) return '#fbbf24'
    if (s < 60) return '#f97316'
    if (s < 80) return '#ef4444'
    return '#991b1b'
  }

  const color = getColor(score)

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="8"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s cubic-bezier(0.4,0,0.2,1), stroke 0.3s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display font-bold" style={{ fontSize: size * 0.22, color }}>
          {score.toFixed(0)}
        </span>
        <span className="text-xs" style={{ color: 'var(--text-muted)', fontSize: size * 0.1 }}>
          / 100
        </span>
      </div>
    </div>
  )
}

// Metric card
interface MetricCardProps {
  label: string
  value: string | number
  sub?: string
  delta?: number
  deltaLabel?: string
  accent?: boolean
  icon?: React.ReactNode
}

export const MetricCard = ({ label, value, sub, delta, deltaLabel, accent, icon }: MetricCardProps) => {
  const isDeltaPositive = (delta ?? 0) > 0

  return (
    <div className={`glass-card p-5 ${accent ? 'glass-card-accent' : ''}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="metric-label">{label}</div>
          <div className="metric-value mt-2">{value}</div>
          {sub && (
            <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              {sub}
            </div>
          )}
          {delta !== undefined && (
            <div className={`text-xs mt-1 font-semibold ${isDeltaPositive ? 'metric-delta-up' : 'metric-delta-down'}`}>
              {isDeltaPositive ? '+' : ''}{delta?.toFixed(1)} {deltaLabel}
            </div>
          )}
        </div>
        {icon && (
          <div className="ml-3 flex-shrink-0 opacity-60">
            {icon}
          </div>
        )}
      </div>
    </div>
  )
}

// Skeleton loader
export const Skeleton = ({ className = '' }: { className?: string }) => (
  <div className={`skeleton ${className}`} />
)

// Page loader
export const PageLoader = () => (
  <div className="flex flex-col items-center justify-center h-64 gap-4">
    <div
      className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin"
      style={{ borderColor: 'rgba(245,158,11,0.3)', borderTopColor: '#f59e0b' }}
    />
    <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
      Loading...
    </span>
  </div>
)

// SHAP reason code card
interface ReasonCode {
  feature: string
  description: string
  shap_contribution: number
  direction: string
  feature_value: number
}

export const ReasonCodeCard = ({ reason, rank }: { reason: ReasonCode; rank: number }) => {
  const isUp = reason.direction === 'increases'
  const maxContrib = 0.25
  const color = isUp ? '#ef4444' : '#10b981'
  const bgLight = isUp ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)'
  const borderLight = isUp ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'

  return (
    <div 
      className="glass-card p-5 fade-in-up" 
      style={{ 
        animationDelay: `${rank * 0.07}s`,
        border: `1px solid ${borderLight}`,
        background: `linear-gradient(135deg, ${bgLight} 0%, rgba(20,20,22,0.6) 100%)`
      }}
    >
      <div className="flex items-start gap-4">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-sm font-bold shadow-md"
          style={{
            background: isUp ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)',
            color,
            border: `1px solid ${color}44`
          }}
        >
          {rank + 1}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium leading-snug" style={{ color: 'var(--text-primary)' }}>
            {reason.description}
          </p>
          
          <div className="mt-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold" style={{ color }}>
                {isUp ? '+' : ''}{(reason.shap_contribution * 100).toFixed(1)}%
              </span>
              <span className="text-xs font-medium" style={{ color: isUp ? '#fca5a5' : '#a7f3d0' }}>
                {isUp ? 'increases risk' : 'reduces risk'}
              </span>
            </div>
            
            <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${Math.min(100, (Math.abs(reason.shap_contribution) / maxContrib) * 100)}%`,
                  background: `linear-gradient(90deg, ${color}dd, ${color})`,
                  boxShadow: `0 0 8px ${color}88`
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Grade color helpers
export const gradeToColor = (grade: string): string => {
  const map: Record<string, string> = {
    AAA: '#10b981', AA: '#34d399', A: '#6ee7b7',
    BBB: '#fbbf24', BB: '#f59e0b', B: '#f97316',
    C: '#ef4444', D: '#991b1b',
  }
  return map[grade] ?? '#64748b'
}

export const stressToColor = (score: number): string => {
  if (score < 20) return '#10b981'
  if (score < 40) return '#fbbf24'
  if (score < 60) return '#f97316'
  if (score < 80) return '#ef4444'
  return '#991b1b'
}
