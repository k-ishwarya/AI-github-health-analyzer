import { useState, useEffect } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000'

const QUICK_SAMPLES = [
  'fastapi/fastapi',
  'pallets/flask',
  'octocat/Hello-World',
  'facebook/react'
]

function App() {
  const [repoUrl, setRepoUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [profileSuggestions, setProfileSuggestions] = useState(null)
  const [data, setData] = useState(null)

  const handleAnalyze = async (targetRepo) => {
    const url = targetRepo || repoUrl
    if (!url || !url.trim()) return

    setLoading(true)
    setError(null)
    setProfileSuggestions(null)
    setRepoUrl(url)

    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ repo_url: url.trim() })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        if (errorData.detail && typeof errorData.detail === 'object' && errorData.detail.is_profile) {
          setProfileSuggestions(errorData.detail)
          throw new Error(errorData.detail.message)
        }
        throw new Error(
          (typeof errorData.detail === 'string' ? errorData.detail : null) ||
          `Request failed with status ${response.status}`
        )
      }

      const result = await response.json()
      setData(result)
    } catch (err) {
      setError(err.message || 'Failed to analyze repository. Check URL or network connection.')
    } finally {
      setLoading(false)
    }
  }

  // Auto-analyze a sample on first load
  useEffect(() => {
    handleAnalyze('fastapi/fastapi')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onSubmit = (e) => {
    e.preventDefault()
    handleAnalyze()
  }

  // Circular gauge calculations
  const score = data?.scores?.overall_score ?? 0
  const radius = 70
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (score / 100) * circumference

  return (
    <div className="app-container">
      {/* Top Navigation */}
      <header className="app-header">
        <div className="logo-wrapper">
          <div className="logo-icon">⚡</div>
          <div>
            <div className="brand-title">GitPulse AI</div>
            <div className="brand-subtitle">GitHub Repository Health Analyzer</div>
          </div>
        </div>
        <div className="status-badge">
          <span className="status-dot"></span>
          <span>API Connected (Port 8000)</span>
        </div>
      </header>

      {/* Hero & Search Input */}
      <section className="hero-section">
        <div className="hero-tag">AI-Powered Repository Intelligence</div>
        <h1 className="hero-title">
          Evaluate Repository <span className="hero-title-gradient">Health & Quality</span>
        </h1>
        <p className="hero-description">
          Instant deep-dive into commit velocity, community governance, issue resolution rates, and actionable AI maintenance recommendations.
        </p>

        <form onSubmit={onSubmit} className="search-form">
          <div className="search-box">
            <span className="search-icon-prefix">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
            </span>
            <input
              type="text"
              className="search-input"
              placeholder="Enter GitHub URL or owner/repo (e.g. facebook/react)"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="analyze-button" disabled={loading}>
              {loading ? 'Analyzing...' : 'Analyze Health'}
            </button>
          </div>
        </form>

        <div className="quick-samples">
          <span className="sample-label">Try popular repos:</span>
          {QUICK_SAMPLES.map((sample) => (
            <button
              key={sample}
              className="chip-btn"
              onClick={() => handleAnalyze(sample)}
              disabled={loading}
            >
              {sample}
            </button>
          ))}
        </div>

        {error && (
          <div className="error-banner">
            <div className="error-banner-content">
              <span className="error-banner-icon">⚠️</span>
              <span className="error-banner-text">{error}</span>
            </div>
            <button
              type="button"
              className="error-dismiss-btn"
              onClick={() => setError(null)}
              title="Dismiss error"
              aria-label="Dismiss error"
            >
              ✕
            </button>
          </div>
        )}

        {profileSuggestions && (
          <div className="profile-suggestions-card">
            <h4>📁 Repositories found for @{profileSuggestions.username}:</h4>
            <p>Click any repository below to analyze its health:</p>
            <div className="suggestion-chips">
              {profileSuggestions.repositories.map((repoName) => (
                <button
                  key={repoName}
                  className="chip-btn suggestion-btn"
                  onClick={() => {
                    setProfileSuggestions(null)
                    handleAnalyze(repoName)
                  }}
                >
                  🚀 {repoName}
                </button>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Loading Skeleton */}
      {loading && (
        <div className="loading-box">
          <div className="spinner"></div>
          <h3>Scanning GitHub Repository...</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 8 }}>
            Fetching commit history, pull requests, issue resolution times, and generating AI insights...
          </p>
        </div>
      )}

      {/* Analysis Results View */}
      {!loading && data && (
        <main className="results-container">
          {/* Repository Header Card */}
          <div className="repo-header-card">
            <div className="repo-main-info">
              <div className="repo-title-row">
                <a
                  href={data.repository.html_url}
                  target="_blank"
                  rel="noreferrer"
                  className="repo-link"
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                  </svg>
                  {data.repository.full_name}
                </a>
                <span className="lang-tag">{data.repository.language}</span>
                {data.repository.license_name && (
                  <span className="lang-tag" style={{ borderColor: 'rgba(16, 185, 129, 0.3)', color: '#34d399' }}>
                    {data.repository.license_name}
                  </span>
                )}
              </div>
              <p className="repo-desc">{data.repository.description}</p>
            </div>

            <div className="repo-meta-stats">
              <div className="stat-chip">
                <span>⭐</span>
                <span>Stars: <strong>{data.repository.stars.toLocaleString()}</strong></span>
              </div>
              <div className="stat-chip">
                <span>🍴</span>
                <span>Forks: <strong>{data.repository.forks.toLocaleString()}</strong></span>
              </div>
              <div className="stat-chip">
                <span>👁️</span>
                <span>Watchers: <strong>{data.repository.watchers.toLocaleString()}</strong></span>
              </div>
            </div>
          </div>

          {/* Scores Overview & Pillars */}
          <div className="score-dashboard-grid">
            {/* Overall Score Circle */}
            <div className="overall-score-card">
              <h3 style={{ fontSize: 16, color: 'var(--text-secondary)' }}>Overall Health Index</h3>
              <div className="gauge-wrapper">
                <svg className="gauge-svg" viewBox="0 0 160 160">
                  <circle
                    className="gauge-bg"
                    cx="80"
                    cy="80"
                    r={radius}
                    strokeWidth="12"
                    fill="transparent"
                  />
                  <circle
                    className="gauge-fill"
                    cx="80"
                    cy="80"
                    r={radius}
                    strokeWidth="12"
                    fill="transparent"
                    stroke={data.scores.status_color}
                    strokeDasharray={circumference}
                    strokeDashoffset={strokeDashoffset}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="gauge-text">
                  <span className="gauge-number">{score}</span>
                  <span className="gauge-label">out of 100</span>
                </div>
              </div>

              <div
                className="grade-badge"
                style={{
                  backgroundColor: `${data.scores.status_color}18`,
                  borderColor: `${data.scores.status_color}40`,
                  color: data.scores.status_color,
                  borderWidth: 1,
                  borderStyle: 'solid'
                }}
              >
                Grade {data.scores.grade} • {data.scores.status}
              </div>
            </div>

            {/* 4 Dimension Pillars */}
            <div className="pillars-grid">
              {/* Pillar 1: Activity */}
              <div className="pillar-card">
                <div className="pillar-header">
                  <span className="pillar-title">📈 Maintenance & Activity</span>
                  <span className="pillar-score" style={{ color: '#818cf8' }}>
                    {data.scores.categories.activity.score}/100
                  </span>
                </div>
                <div className="progress-track">
                  <div
                    className="progress-bar"
                    style={{
                      width: `${data.scores.categories.activity.score}%`,
                      background: 'linear-gradient(90deg, #6366f1, #818cf8)'
                    }}
                  ></div>
                </div>
                <div className="pillar-details">
                  <span>Last commit: <strong>{data.scores.categories.activity.days_since_last_commit} days ago</strong></span>
                  <span>Recent commits sampled: <strong>{data.repository.recent_commits_count}</strong></span>
                </div>
              </div>

              {/* Pillar 2: Community & Governance */}
              <div className="pillar-card">
                <div className="pillar-header">
                  <span className="pillar-title">🛡️ Governance & Docs</span>
                  <span className="pillar-score" style={{ color: '#34d399' }}>
                    {data.scores.categories.community.score}/100
                  </span>
                </div>
                <div className="progress-track">
                  <div
                    className="progress-bar"
                    style={{
                      width: `${data.scores.categories.community.score}%`,
                      background: 'linear-gradient(90deg, #10b981, #34d399)'
                    }}
                  ></div>
                </div>
                <div className="checklist-row">
                  <span className={`check-item ${data.scores.categories.community.has_readme ? 'active' : 'missing'}`}>
                    {data.scores.categories.community.has_readme ? '✓ README' : '✕ README'}
                  </span>
                  <span className={`check-item ${data.scores.categories.community.has_license ? 'active' : 'missing'}`}>
                    {data.scores.categories.community.has_license ? '✓ License' : '✕ License'}
                  </span>
                  <span className={`check-item ${data.scores.categories.community.has_contributing ? 'active' : 'missing'}`}>
                    {data.scores.categories.community.has_contributing ? '✓ Contributing' : '✕ Contributing'}
                  </span>
                  <span className={`check-item ${data.scores.categories.community.has_code_of_conduct ? 'active' : 'missing'}`}>
                    {data.scores.categories.community.has_code_of_conduct ? '✓ Code of Conduct' : '✕ Code of Conduct'}
                  </span>
                </div>
              </div>

              {/* Pillar 3: Issues */}
              <div className="pillar-card">
                <div className="pillar-header">
                  <span className="pillar-title">🐛 Issue Resolution</span>
                  <span className="pillar-score" style={{ color: '#fbbf24' }}>
                    {data.scores.categories.issues.score}/100
                  </span>
                </div>
                <div className="progress-track">
                  <div
                    className="progress-bar"
                    style={{
                      width: `${data.scores.categories.issues.score}%`,
                      background: 'linear-gradient(90deg, #f59e0b, #fbbf24)'
                    }}
                  ></div>
                </div>
                <div className="pillar-details">
                  <span>Open Issues: <strong>{data.repository.open_issues_count.toLocaleString()}</strong></span>
                  <span>Closed Issues (Sampled): <strong>{data.repository.closed_issues_count.toLocaleString()}</strong></span>
                </div>
              </div>

              {/* Pillar 4: Pull Requests */}
              <div className="pillar-card">
                <div className="pillar-header">
                  <span className="pillar-title">🔀 PR & Velocity</span>
                  <span className="pillar-score" style={{ color: '#c084fc' }}>
                    {data.scores.categories.pull_requests.score}/100
                  </span>
                </div>
                <div className="progress-track">
                  <div
                    className="progress-bar"
                    style={{
                      width: `${data.scores.categories.pull_requests.score}%`,
                      background: 'linear-gradient(90deg, #a855f7, #c084fc)'
                    }}
                  ></div>
                </div>
                <div className="pillar-details">
                  <span>Sample Merged PRs: <strong>{data.repository.sample_pull_requests.merged} of {data.repository.sample_pull_requests.total_sampled}</strong></span>
                  <span>Merge Rate: <strong>{Math.round(data.scores.categories.pull_requests.merged_ratio * 100)}%</strong></span>
                </div>
              </div>
            </div>
          </div>

          {/* AI Insights & Recommendations */}
          <section className="ai-section">
            <div className="ai-header">
              <span className="ai-badge">AI Diagnostic Report</span>
              <h3 style={{ fontSize: 18, color: '#fff' }}>Repository Health Assessment</h3>
            </div>

            <div className="ai-summary-box">
              {data.insights.summary}
            </div>

            <div className="insights-two-col">
              <div className="insight-list-card strengths-card">
                <h4>✨ Key Strengths</h4>
                <ul className="bullet-list">
                  {data.insights.strengths.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="insight-list-card risks-card">
                <h4>⚠️ Potential Maintenance Risks</h4>
                <ul className="bullet-list">
                  {data.insights.risks.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div>
              <h4 className="rec-section-title">💡 Actionable Improvement Recommendations</h4>
              <div className="rec-grid">
                {data.insights.recommendations.map((rec, index) => (
                  <div key={index} className="rec-item">
                    <span className={`priority-pill priority-${rec.priority}`}>
                      {rec.priority}
                    </span>
                    <div className="rec-content">
                      <h5>{rec.title}</h5>
                      <p>{rec.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </main>
      )}
    </div>
  )
}

export default App
