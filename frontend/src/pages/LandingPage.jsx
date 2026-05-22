import { useNavigate } from 'react-router-dom'
import './LandingPage.css'

function LandingPage() {
  const navigate = useNavigate()

  return (
    <div className="landing">

      {/* Navbar */}
      <nav className="landing-nav">
        <img src="/logo.webp" alt="InventoryIQ" className="landing-logo-img" />
        <button className="landing-nav-btn" onClick={() => navigate('/upload')}>
          Get Started
        </button>
      </nav>

      {/* Hero */}
      <div className="landing-hero">
        <span className="landing-badge">AI-Powered Retail Forecasting</span>
        <h1 className="landing-title">
          Smarter Retail Decisions,<br />
          <span className="landing-title-accent">Powered by AI</span>
        </h1>
        <p className="landing-subtitle">
          Upload your sales data and get instant forecasts, risk alerts,
          and AI-generated insights — no technical knowledge required.
        </p>
        <button
          className="landing-btn-primary"
          onClick={() => navigate('/upload')}
        >
          ✦ Get Started
        </button>

        {/* Stats */}
        <div className="landing-stats">
          <div className="landing-stat">
            <span className="landing-stat-number">3</span>
            <span className="landing-stat-label">Dashboard Views</span>
          </div>
          <div className="landing-stat-divider" />
          <div className="landing-stat">
            <span className="landing-stat-number">AI</span>
            <span className="landing-stat-label">Gemini Powered</span>
          </div>
          <div className="landing-stat-divider" />
          <div className="landing-stat">
            <span className="landing-stat-number">Live</span>
            <span className="landing-stat-label">Real-time Alerts</span>
          </div>
          <div className="landing-stat-divider" />
          <div className="landing-stat">
            <span className="landing-stat-number">LightGBM</span>
            <span className="landing-stat-label">Forecast Model</span>
          </div>
        </div>
      </div>

      {/* Four cards in a row */}
      <div className="landing-cards">
        <div className="landing-card">
          <div className="landing-card-icon-wrap" style={{backgroundColor: '#e6f4ea'}}>
            <span>📂</span>
          </div>
          <h3>Upload Your Data</h3>
          <p>Drag and drop your retail CSV or Excel file. We normalize and clean it automatically.</p>
        </div>
        <div className="landing-card">
          <div className="landing-card-icon-wrap" style={{backgroundColor: '#e8f0fe'}}>
            <span>🤖</span>
          </div>
          <h3>AI Analyzes Everything</h3>
          <p>Gemini AI reads your dashboard and writes a plain-English business summary instantly.</p>
        </div>
        <div className="landing-card">
          <div className="landing-card-icon-wrap" style={{backgroundColor: '#fef7e0'}}>
            <span>📈</span>
          </div>
          <h3>Demand Forecasting</h3>
          <p>LightGBM predicts future sales per store and category so you can plan ahead.</p>
        </div>
        <div className="landing-card">
          <div className="landing-card-icon-wrap" style={{backgroundColor: '#fce8e6'}}>
            <span>🚨</span>
          </div>
          <h3>Live Risk Alerts</h3>
          <p>Automatic anomaly detection flags sales spikes, declines, and margin issues in real time.</p>
        </div>
      </div>

      {/* Footer */}
      <footer className="landing-footer">
        <p>© 2025 InventoryIQ</p>
      </footer>

    </div>
  )
}

export default LandingPage