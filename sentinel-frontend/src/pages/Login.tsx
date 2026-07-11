import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import type { UserRole } from '../contexts/AuthContext'

const DEMO_CREDENTIALS: { username: string; role: UserRole; label: string; color: string; description: string }[] = [
  { username: 'risk_officer', role: 'risk_officer', label: 'Risk Officer', color: '#f1c443', description: 'Portfolio triage & alerts' },
  { username: 'rm', role: 'rm', label: 'Relationship Manager', color: '#8c8070', description: 'Borrower insights & simulator' },
  { username: 'cro', role: 'cro', label: 'Chief Risk Officer', color: '#C9A84C', description: 'Portfolio analytics & trends' },
  { username: 'compliance', role: 'compliance', label: 'Compliance Officer', color: '#7a9c8a', description: 'Model governance & audit' },
]

const PASSWORD = 'kavach123'

/* ── Animated counter hook ───────────────────────────────────────── */
function useCountUp(target: string, duration = 1400) {
  const [display, setDisplay] = useState('0')
  useEffect(() => {
    const numeric = parseFloat(target.replace(/[^0-9.]/g, ''))
    if (isNaN(numeric)) { setDisplay(target); return }
    const prefix = target.match(/^[^0-9]*/)?.[0] ?? ''
    const suffix = target.match(/[^0-9.]+$/)?.[0] ?? ''
    const decimals = (target.split('.')[1] ?? '').replace(/[^0-9]/g, '').length
    const start = performance.now()
    let raf: number
    const step = (now: number) => {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3)
      const val = (numeric * eased).toFixed(decimals)
      setDisplay(`${prefix}${val}${suffix}`)
      if (t < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])
  return display
}

/* ── Particle canvas ─────────────────────────────────────────────── */
function ParticleCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    let animId: number

    const resize = () => {
      canvas.width = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    }
    resize()
    window.addEventListener('resize', resize)

    const COUNT = 52
    const GOLD = [216, 171, 87]
    type Pt = { x: number; y: number; vx: number; vy: number; r: number; a: number }
    const pts: Pt[] = Array.from({ length: COUNT }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.38,
      vy: (Math.random() - 0.5) * 0.38,
      r: Math.random() * 1.6 + 0.6,
      a: Math.random(),
    }))

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      for (const p of pts) {
        p.x += p.vx; p.y += p.vy
        if (p.x < 0) p.x = canvas.width
        if (p.x > canvas.width) p.x = 0
        if (p.y < 0) p.y = canvas.height
        if (p.y > canvas.height) p.y = 0
      }
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const dx = pts[i].x - pts[j].x
          const dy = pts[i].y - pts[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 130) {
            const alpha = (1 - dist / 130) * 0.18
            ctx.beginPath()
            ctx.moveTo(pts[i].x, pts[i].y)
            ctx.lineTo(pts[j].x, pts[j].y)
            ctx.strokeStyle = `rgba(${GOLD[0]},${GOLD[1]},${GOLD[2]},${alpha})`
            ctx.lineWidth = 0.7
            ctx.stroke()
          }
        }
      }
      for (const p of pts) {
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${GOLD[0]},${GOLD[1]},${GOLD[2]},${p.a * 0.55})`
        ctx.fill()
      }
      animId = requestAnimationFrame(draw)
    }
    draw()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0 }}
    />
  )
}

/* ── Metric row with animated counter ───────────────────────────── */
function MetricRow({ name, value, note }: { name: string; value: string; note: string }) {
  const counted = useCountUp(value)
  return (
    <div className="metric">
      <div className="metric-name">{name}</div>
      <div className="metric-value">
        {counted}
        <div className="metric-note">{note}</div>
      </div>
    </div>
  )
}

/* ── Main component ──────────────────────────────────────────────── */
export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [selectedRole, setSelectedRole] = useState<typeof DEMO_CREDENTIALS[0]>(DEMO_CREDENTIALS[0])
  const [password, setPassword] = useState(PASSWORD)
  const [showPass, setShowPass] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [showRoleDropdown, setShowRoleDropdown] = useState(false)
  const [focusedField, setFocusedField] = useState<string | null>(null)
  const [visible, setVisible] = useState(false)

  const ROLE_DEFAULT_ROUTES: Record<UserRole, string> = {
    risk_officer: '/portfolio',
    rm: '/account',
    cro: '/analytics',
    compliance: '/governance',
  }

  useEffect(() => {
    document.body.classList.add('login-page-active')
    const t = setTimeout(() => setVisible(true), 60)
    return () => {
      document.body.classList.remove('login-page-active')
      clearTimeout(t)
    }
  }, [])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    try {
      await login(selectedRole.username, password, selectedRole.role)
      navigate(ROLE_DEFAULT_ROUTES[selectedRole.role])
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Login failed. Please check credentials.')
    } finally {
      setIsLoading(false)
    }
  }

  const inputStyle = (field: string): React.CSSProperties => ({
    width: '100%',
    height: '48px',
    border: focusedField === field
      ? '1px solid rgba(216, 171, 87, 0.75)'
      : '1px solid rgba(255, 255, 255, 0.2)',
    borderRadius: '9px',
    background: 'var(--field)',
    color: '#e8e6e3',
    fontSize: 'clamp(14px, 1.75vh, 18px)',
    outline: 'none',
    padding: '0 17px',
    boxShadow: focusedField === field
      ? 'inset 0 1px 0 rgba(255,255,255,0.05), 0 0 0 3px rgba(216,171,87,0.18), 0 12px 28px rgba(0,0,0,0.16)'
      : 'inset 0 1px 0 rgba(255,255,255,0.05), 0 12px 28px rgba(0,0,0,0.16)',
    transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
  })

  return (
    <>
      <style>{`
        :root {
          --bg: #0d0e11;
          --panel: rgba(255, 255, 255, 0.035);
          --line: rgba(255, 255, 255, 0.12);
          --line-strong: rgba(255, 255, 255, 0.2);
          --text: #f5f3ef;
          --muted: #a9a7a4;
          --gold: #d8ab57;
          --gold-bright: #f1c443;
          --field: rgba(42, 42, 47, 0.86);
          --serif: Georgia, "Times New Roman", serif;
          --sans: Inter, "Segoe UI", Arial, sans-serif;
        }

        body.login-page-active {
          margin: 0;
          width: 100vw;
          height: 100vh;
          color: var(--text);
          font-family: var(--sans);
          background:
            radial-gradient(circle at 24% 62%, rgba(255, 255, 255, 0.055), transparent 24rem),
            radial-gradient(circle at 64% 36%, rgba(255, 255, 255, 0.035), transparent 30rem),
            linear-gradient(115deg, #1c1d21 0%, #101113 38%, #090a0c 100%);
          overflow: hidden;
        }

        body.login-page-active::before {
          content: "";
          position: fixed;
          inset: 0;
          pointer-events: none;
          background-image:
            linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
          background-size: 2px 2px;
          opacity: 0.18;
          mix-blend-mode: overlay;
        }

        .page {
          position: relative;
          height: 100vh;
          display: grid;
          grid-template-columns: minmax(390px, 34.8vw) 1fr;
        }

        /* ── Left panel entry animation ── */
        .left {
          position: relative;
          z-index: 1;
          height: 100vh;
          padding: clamp(20px, 3.1vh, 30px) 40px 46px;
          border-right: 1px solid var(--line-strong);
          background: linear-gradient(90deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.015));
          box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.04);
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          opacity: 0;
          transform: translateX(-22px);
          transition: opacity 0.65s ease, transform 0.65s cubic-bezier(0.22,1,0.36,1);
        }
        .left.visible {
          opacity: 1;
          transform: translateX(0);
        }

        /* ── Right panel entry animation ── */
        .main {
          position: relative;
          height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 72px 32px 78px;
          overflow: hidden;
          opacity: 0;
          transform: translateX(22px);
          transition: opacity 0.65s ease 0.1s, transform 0.65s cubic-bezier(0.22,1,0.36,1) 0.1s;
        }
        .main.visible {
          opacity: 1;
          transform: translateX(0);
        }

        .brand {
          display: flex;
          align-items: center;
          gap: 15px;
          margin-bottom: clamp(14px, 2.1vh, 22px);
        }

        .shield {
          width: 54px;
          height: 63px;
          filter: drop-shadow(0 10px 16px rgba(0, 0, 0, 0.28));
        }

        .brand-title {
          font-family: var(--serif);
          font-size: clamp(24px, 2.9vh, 29px);
          font-weight: 800;
          letter-spacing: 0;
          color: #efd486;
          text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
        }

        .brand-subtitle {
          margin-top: 2px;
          color: #bd9660;
          font-size: clamp(13px, 1.65vh, 17px);
        }

        h1 {
          margin: 0 0 clamp(12px, 1.8vh, 18px);
          max-width: 620px;
          font-family: var(--serif);
          font-size: clamp(36px, 5.15vh, 54px);
          line-height: 1.02;
          font-weight: 900;
          letter-spacing: 0;
          text-shadow: 0 2px 6px rgba(0, 0, 0, 0.55);
        }

        .gold-text { color: var(--gold); }

        .intro {
          max-width: 650px;
          margin: 0;
          color: #eeece8;
          font-size: clamp(16px, 1.95vh, 21px);
          line-height: 1.38;
          text-shadow: 0 1px 5px rgba(0, 0, 0, 0.35);
        }

        .tagline {
          margin-top: clamp(12px, 2vh, 20px);
          font-size: clamp(16px, 1.95vh, 20px);
          color: #f0eee9;
        }

        .metrics {
          margin-top: clamp(24px, 5.1vh, 50px);
          max-width: 650px;
        }

        .metrics-title {
          margin-bottom: clamp(8px, 1.4vh, 14px);
          color: var(--gold);
          font-weight: 800;
          font-size: clamp(14px, 1.75vh, 18px);
          letter-spacing: 0.01em;
        }

        .metric {
          display: grid;
          grid-template-columns: 1fr auto;
          align-items: center;
          min-height: clamp(62px, 8.1vh, 78px);
          border-top: 1px solid var(--line);
        }

        .metric:last-child { border-bottom: 1px solid var(--line); }

        .metric-name {
          font-size: clamp(17px, 2.05vh, 22px);
          color: #f0eee9;
        }

        .metric-value {
          text-align: right;
          color: var(--gold);
          font-size: clamp(24px, 3.15vh, 32px);
          line-height: 1.05;
          font-weight: 800;
        }

        .metric-note {
          margin-top: 3px;
          color: #c2beb8;
          font-size: clamp(13px, 1.65vh, 17px);
          font-weight: 400;
        }

        .login {
          position: relative;
          z-index: 1;
          width: min(565px, 100%);
          margin-top: -10px;
        }

        .login h2 {
          margin: 0 0 13px;
          font-family: var(--serif);
          font-size: clamp(42px, 5.1vh, 51px);
          line-height: 1;
          color: #f7f5f0;
          text-shadow: 0 2px 8px rgba(0, 0, 0, 0.45);
        }

        .login-subtitle {
          margin: 0 0 clamp(12px, 1.8vh, 18px);
          color: var(--muted);
          font-size: clamp(14px, 1.75vh, 18px);
        }

        label {
          display: block;
          margin: 14px 0 6px;
          color: #b5b3b0;
          font-size: 16px;
          font-weight: 600;
        }

        .select {
          width: 100%;
          height: 48px;
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 9px;
          background: var(--field);
          color: var(--gold);
          font-size: clamp(14px, 1.75vh, 18px);
          outline: none;
          box-shadow:
            inset 0 1px 0 rgba(255, 255, 255, 0.05),
            0 12px 28px rgba(0, 0, 0, 0.16);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 18px;
          cursor: pointer;
          transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .select:hover {
          border-color: rgba(216, 171, 87, 0.45);
        }

        .role {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .dot {
          width: 11px;
          height: 11px;
          border-radius: 50%;
          background: var(--gold-bright);
          box-shadow: 0 0 11px rgba(241, 196, 67, 0.35);
          flex-shrink: 0;
        }

        .chevron {
          width: 10px;
          height: 10px;
          border-right: 1.8px solid #d6d4d2;
          border-bottom: 1.8px solid #d6d4d2;
          transform: rotate(45deg) translateY(-3px);
          flex-shrink: 0;
        }

        .input-wrap { position: relative; }

        .input::placeholder {
          color: #9d9a9b;
          opacity: 1;
        }

        .eye {
          position: absolute;
          right: 17px;
          top: 50%;
          width: 25px;
          height: 25px;
          transform: translateY(-50%);
          color: #c7c3c0;
          opacity: 0.85;
          cursor: pointer;
          transition: opacity 0.15s ease;
        }
        .eye:hover { opacity: 1; color: var(--gold); }

        /* ── Gold shimmer button ── */
        @keyframes shimmer-sweep {
          0%   { background-position: -200% center; }
          100% { background-position:  200% center; }
        }

        .button {
          position: relative;
          overflow: hidden;
          width: 100%;
          height: 48px;
          margin-top: 17px;
          border: 0;
          border-radius: 8px;
          background: linear-gradient(180deg, #f3ca44, #e8b936);
          color: #191816;
          font-size: 18px;
          font-weight: 800;
          cursor: pointer;
          box-shadow:
            inset 0 1px 0 rgba(255, 255, 255, 0.45),
            0 12px 22px rgba(0, 0, 0, 0.25);
          transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease;
        }

        .button::after {
          content: '';
          position: absolute;
          inset: 0;
          background: linear-gradient(
            105deg,
            transparent 35%,
            rgba(255, 255, 255, 0.52) 50%,
            transparent 65%
          );
          background-size: 200% 100%;
          animation: shimmer-sweep 2.4s ease-in-out infinite;
        }

        .button:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow:
            inset 0 1px 0 rgba(255, 255, 255, 0.45),
            0 18px 32px rgba(0, 0, 0, 0.35),
            0 0 0 2px rgba(216, 171, 87, 0.4);
        }

        .button:active:not(:disabled) {
          transform: translateY(0);
        }

        .button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        .button:disabled::after { animation: none; }

        /* ── Spinner ── */
        @keyframes spin { to { transform: rotate(360deg); } }
        .spinner {
          display: inline-block;
          width: 16px;
          height: 16px;
          border: 2px solid rgba(25,24,22,0.25);
          border-top-color: #191816;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
          vertical-align: middle;
          margin-right: 8px;
        }

        .demo {
          margin-top: 17px;
          padding: 12px 16px;
          border: 1px solid rgba(216, 171, 87, 0.34);
          border-radius: 8px;
          background: linear-gradient(90deg, rgba(160, 118, 38, 0.22), rgba(161, 116, 33, 0.11));
          color: #f0eee8;
          font-size: clamp(14px, 1.75vh, 18px);
          line-height: 1.28;
          box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
        }

        .demo strong {
          display: block;
          color: var(--gold);
          font-weight: 800;
        }

        .footer {
          position: fixed;
          left: 34.8vw;
          right: 0;
          bottom: 0;
          height: 46px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-top: 1px solid rgba(255, 255, 255, 0.12);
          color: #9a9896;
          font-size: 16px;
          background: rgba(12, 13, 15, 0.5);
          backdrop-filter: blur(8px);
          z-index: 2;
        }

        .footer a {
          color: #e3dfd8;
          text-decoration: none;
        }
        .footer a:hover { color: var(--gold); }

        .dropdown-menu {
          position: absolute;
          top: 100%;
          left: 0;
          right: 0;
          margin-top: 4px;
          border: 1px solid rgba(216, 171, 87, 0.28);
          border-radius: 9px;
          background: #121215;
          z-index: 50;
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
          overflow: hidden;
        }

        .dropdown-option {
          width: 100%;
          text-align: left;
          padding: 12px 18px;
          background: transparent;
          border: none;
          color: #e8e6e3;
          font-size: clamp(14px, 1.75vh, 18px);
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 12px;
          transition: background 0.15s ease;
        }

        .dropdown-option:hover {
          background: rgba(216, 171, 87, 0.08);
          color: var(--gold);
        }

        .dropdown-option .dot {
          width: 9px;
          height: 9px;
          border-radius: 50%;
          flex-shrink: 0;
        }

        .error-box {
          margin-top: 12px;
          padding: 10px 14px;
          border-radius: 6px;
          background: rgba(239, 68, 68, 0.08);
          color: #ef4444;
          border: 1px solid rgba(239, 68, 68, 0.2);
          font-size: 14px;
        }

        @media (max-width: 1050px) {
          .page { grid-template-columns: 1fr; height: auto; overflow-y: auto; }
          .left { height: auto; border-right: 0; border-bottom: 1px solid var(--line-strong); padding: 30px 24px; }
          .main { min-height: 610px; height: auto; padding: 40px 24px; }
          .footer { position: static; height: auto; min-height: 46px; padding: 12px 18px; text-align: center; width: 100%; left: 0; }
        }

        @media (max-width: 620px) {
          .left, .main { padding-left: 22px; padding-right: 22px; }
          .brand-title { font-size: 25px; }
          .brand-subtitle { font-size: 16px; }
          h1 { font-size: 42px; }
          .intro, .tagline { font-size: clamp(14px, 1.75vh, 18px); }
          .metrics { margin-top: 46px; }
          .metric { min-height: 88px; }
          .metric-name { font-size: 21px; }
          .metric-value { font-size: clamp(24px, 2.9vh, 29px); }
          .metric-note { font-size: 15px; }
          .login h2 { font-size: 43px; }
        }
      `}</style>

      <div className="page">
        {/* ── Left panel ── */}
        <aside className={`left${visible ? ' visible' : ''}`}>
          <div>
            <div className="brand">
              <svg className="shield" viewBox="0 0 76 88" aria-hidden="true">
                <defs>
                  <linearGradient id="shieldGold" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stopColor="#f6df86" />
                    <stop offset="0.52" stopColor="#d4a258" />
                    <stop offset="1" stopColor="#b57d4b" />
                  </linearGradient>
                </defs>
                <path fill="url(#shieldGold)" d="M38 2 72 15v25c0 22.5-13.7 37.8-34 46C17.7 77.8 4 62.5 4 40V15L38 2Z" />
                <path fill="none" stroke="#24201b" strokeWidth="5" strokeLinejoin="round" d="M38 24 54 30v11c0 10.3-6.1 17.4-16 21.5C28.1 58.4 22 51.3 22 41V30l16-6Z" />
              </svg>
              <div>
                <div className="brand-title">KAVACH</div>
                <div className="brand-subtitle">IDBI Innovate 2026</div>
              </div>
            </div>

            <h1>Early Warning<br /><span className="gold-text">for MSME Credit</span></h1>
            <p className="intro">An AI-driven platform for predicting borrower default 12 months ahead. Fusing structured financial data with GST signals, bureau trends, and transaction behavior — all in a unified Risk Grade.</p>
            <p className="tagline">Precise. Predictive. Essential.</p>
          </div>

          <section className="metrics" aria-label="Performance metrics">
            <div className="metrics-title">PERFORMANCE METRICS</div>
            <MetricRow name="AUC-ROC"            value="0.7894"    note="honest baseline: 0.65" />
            <MetricRow name="Precision @ Top 10%" value="39.2%"     note="baseline: 21.0%" />
            <MetricRow name="Alert Lead Time"     value="12 months" note="vs. reactive baseline: 1 month" />
            <MetricRow name="Accuracy Lift"       value="+1.8x"     note="over 20.8% default rate" />
          </section>
        </aside>

        {/* ── Right panel ── */}
        <main className={`main${visible ? ' visible' : ''}`}>
          {/* Animated gold particle network */}
          <ParticleCanvas />

          <form onSubmit={handleLogin} className="login" aria-label="Sign in">
            <h2>Sign In</h2>
            <p className="login-subtitle">Select your role to access Kavach</p>

            <label htmlFor="role">ROLE</label>
            <div style={{ position: 'relative' }}>
              <div
                className="select"
                id="role"
                role="button"
                tabIndex={0}
                aria-label={`Role: ${selectedRole.label}`}
                onClick={() => setShowRoleDropdown(v => !v)}
                onKeyDown={e => e.key === 'Enter' && setShowRoleDropdown(v => !v)}
              >
                <span className="role">
                  <span className="dot" style={{ background: selectedRole.color, boxShadow: `0 0 11px ${selectedRole.color}55` }} />
                  {selectedRole.label}
                </span>
                <span className="chevron" style={{ transform: showRoleDropdown ? 'rotate(225deg) translateY(3px)' : 'rotate(45deg) translateY(-3px)', transition: 'transform 0.2s ease' }} />
              </div>

              {showRoleDropdown && (
                <div className="dropdown-menu">
                  {DEMO_CREDENTIALS.map((cred) => (
                    <button
                      key={cred.role}
                      type="button"
                      className="dropdown-option"
                      onClick={() => { setSelectedRole(cred); setShowRoleDropdown(false) }}
                    >
                      <span className="dot" style={{ background: cred.color }} />
                      {cred.label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <label htmlFor="username">USERNAME</label>
            <input
              id="username"
              type="text"
              value={selectedRole.username}
              readOnly
              style={{ ...inputStyle('username'), color: 'rgba(255,255,255,0.4)' }}
              onFocus={() => setFocusedField('username')}
              onBlur={() => setFocusedField(null)}
            />

            <label htmlFor="password">PASSWORD</label>
            <div className="input-wrap">
              <input
                id="password"
                type={showPass ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ ...inputStyle('password'), paddingRight: '50px' }}
                onFocus={() => setFocusedField('password')}
                onBlur={() => setFocusedField(null)}
              />
              <svg className="eye" viewBox="0 0 24 24" aria-hidden="true" onClick={() => setShowPass(v => !v)}>
                {showPass ? (
                  <path fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" />
                ) : (
                  <path fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.2A9.7 9.7 0 0 1 12 5c5.5 0 9 5.2 9 7 0 1-.9 2.7-2.5 4.2M6.6 6.7C4.4 8.1 3 10.7 3 12c0 1.8 3.5 7 9 7 1.5 0 2.8-.4 4-1" />
                )}
              </svg>
            </div>

            {error && <div className="error-box">{error}</div>}

            <button className="button" type="submit" disabled={isLoading}>
              {isLoading ? <><span className="spinner" />Signing In…</> : `Sign In as ${selectedRole.label}`}
            </button>

            <div className="demo">
              <strong>Demo Credentials</strong>
              Password: kavach123
            </div>
          </form>
        </main>
      </div>

      <footer className="footer">
        © 2026 IDBI Innovate — Track 04: MSME Credit Risk | Kavach is a service mark of IDBI Bank Ltd. | <a href="#support">Contact Support</a>
      </footer>
    </>
  )
}
