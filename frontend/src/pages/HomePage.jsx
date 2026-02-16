import { useState } from 'react'
import { Link } from 'react-router-dom'
import './HomePage.css'

export default function HomePage() {
  const [role, setRole] = useState('agent') // 'agent' | 'human' | null

  return (
    <div className="home-page">
      {/* ── Hero ── */}
      <section className="home-hero">
        <img src="/clawome.png" alt="Clawome" className="home-hero-logo" />
        <h1>Clawome</h1>
        <p className="home-hero-tagline">
          Give your agent eyes and hands on any website.
        </p>

        {/* Role selector */}
        <div className="role-selector">
          <button
            className={`role-btn role-btn-agent ${role === 'agent' ? 'role-active' : ''}`}
            onClick={() => setRole(role === 'agent' ? null : 'agent')}
          >
            <span className="role-emoji">🤖</span> I'm an Agent
          </button>
          <button
            className={`role-btn role-btn-human ${role === 'human' ? 'role-active' : ''}`}
            onClick={() => setRole(role === 'human' ? null : 'human')}
          >
            <span className="role-emoji">👤</span> I'm a Human
          </button>
        </div>

        {/* ── Agent onboarding card ── */}
        {role === 'agent' && (
          <div className="onboard-card onboard-agent">
            <div className="onboard-step">
              <span className="onboard-step-num">1</span>
              <div className="onboard-step-body">
                <span className="onboard-step-label">Get the Skill File</span>
                <p>Feed this to your LLM — it contains all API endpoints, parameters, and workflow patterns.</p>
              </div>
              <a href="/skill" className="onboard-action" target="_blank" rel="noopener noreferrer">
                📄 clawome-skill.md
              </a>
            </div>
            <div className="onboard-divider" />
            <div className="onboard-step">
              <span className="onboard-step-num">2</span>
              <div className="onboard-step-body">
                <span className="onboard-step-label">Start browsing</span>
                <code className="onboard-code">POST http://localhost:5001/api/browser/open</code>
              </div>
            </div>
            <div className="onboard-divider" />
            <div className="onboard-step">
              <span className="onboard-step-num">3</span>
              <div className="onboard-step-body">
                <span className="onboard-step-label">Read → Act → Loop</span>
                <code className="onboard-code">GET /dom → POST /click → GET /dom → ...</code>
              </div>
            </div>
          </div>
        )}

        {/* ── Human onboarding card ── */}
        {role === 'human' && (
          <div className="onboard-card onboard-human">
            <div className="onboard-step">
              <span className="onboard-step-num">1</span>
              <div className="onboard-step-body">
                <span className="onboard-step-label">Try the Playground</span>
                <p>Open any website, see the compressed DOM, click nodes — all in a visual interface.</p>
              </div>
              <Link to="/playground" className="onboard-action onboard-action-primary">
                Open Playground →
              </Link>
            </div>
            <div className="onboard-divider" />
            <div className="onboard-step">
              <span className="onboard-step-num">2</span>
              <div className="onboard-step-body">
                <span className="onboard-step-label">Customize Compressors</span>
                <p>Write per-site Python scripts in Settings — auto-selected by URL pattern.</p>
              </div>
              <Link to="/settings" className="onboard-action">
                Settings →
              </Link>
            </div>
            <div className="onboard-divider" />
            <div className="onboard-step">
              <span className="onboard-step-num">3</span>
              <div className="onboard-step-body">
                <span className="onboard-step-label">Read the API Docs</span>
                <p>45 REST endpoints across 12 categories — full reference with examples.</p>
              </div>
              <Link to="/docs" className="onboard-action">
                API Docs →
              </Link>
            </div>
          </div>
        )}
      </section>

      {/* ── Before/After — the "aha" ── */}
      <section className="home-section home-comparison">
        <h2>What your agent actually sees</h2>
        <p className="home-section-sub">Raw HTML is noisy. Clawome gives agents exactly what they need.</p>
        <div className="compare-grid">
          <div className="compare-card compare-before">
            <div className="compare-label">Raw HTML <span className="compare-size">~18,000 tokens</span></div>
            <pre className="compare-code">{`<div class="RNNXgb" jsname="RNNXgb"
  jscontroller="NF..." data-hveid="CAE..."
  data-ved="0ahUKEw..." style="...">
  <div class="SDkEP">
    <div class="a4bIc" jsname="gLFyf"
      aria-owns="..." role="combobox"
      aria-expanded="false"
      aria-haspopup="both" data-...>
      <div class="vNOaBd">
        <textarea class="gLFyf" jsname=...
          maxlength="2048" name="q"
          rows="1" aria-autocomplete="both"
          aria-label="Search"
          title="Search"></textarea>
        <div jsname="LwH6nd"></div>
      </div>
      ...800 more lines...`}</pre>
          </div>
          <div className="compare-arrow">
            <span className="compare-arrow-label">Clawome</span>
            <span className="compare-arrow-icon">{'\u2192'}</span>
          </div>
          <div className="compare-card compare-after">
            <div className="compare-label">Compressed DOM <span className="compare-size">~200 tokens</span></div>
            <pre className="compare-code">{`[1] form(role="search")
  [1.1] textarea(name="q", placeholder="Search")
  [1.2] button: Google Search
  [1.3] button: I'm Feeling Lucky
[2] a(href): About
[3] a(href): Gmail
[4] a(href): Images`}</pre>
          </div>
        </div>
        <p className="compare-caption">Agent reads 7 nodes instead of 800. Every node has a stable ID for instant targeting.</p>
      </section>

      {/* ── How It Works — 3 steps ── */}
      <section className="home-section">
        <h2>Agent integration in 3 calls</h2>
        <p className="home-section-sub">No Selenium. No Puppeteer scripts. Just REST.</p>
        <div className="home-steps">
          <div className="step-card">
            <div className="step-num">1</div>
            <div className="step-body">
              <h3>Open</h3>
              <code className="step-code">POST /open {`{"url":"https://..."}`}</code>
              <p>Launches a real Chromium browser.</p>
            </div>
          </div>
          <div className="step-arrow">{'\u2192'}</div>
          <div className="step-card step-card-highlight">
            <div className="step-num">2</div>
            <div className="step-body">
              <h3>Read DOM</h3>
              <code className="step-code">GET /dom</code>
              <p>Returns <strong>compressed DOM tree</strong> with hierarchical node IDs.</p>
              <span className="step-badge">80–90% compression</span>
            </div>
          </div>
          <div className="step-arrow">{'\u2192'}</div>
          <div className="step-card">
            <div className="step-num">3</div>
            <div className="step-body">
              <h3>Act</h3>
              <code className="step-code">POST /click {`{"node_id":"1.2"}`}</code>
              <p>Click, type, scroll — returns updated DOM. Loop until done.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── 4 Pillars ── */}
      <section className="home-section">
        <h2>Built for agents</h2>
        <div className="home-features">
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F3AF}'}</div>
            <h3>One-shot targeting</h3>
            <p>Hierarchical IDs like <code>3.1.4</code> — click any element on the first try.</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u26A1'}</div>
            <h3>80–90% fewer tokens</h3>
            <p>Strips invisible wrappers, scripts, and noise. Agents see only what matters.</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F9E9}'}</div>
            <h3>Per-site compressors</h3>
            <p>Drop a Python script — auto-activates by URL. Each site gets its own optimizer.</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F504}'}</div>
            <h3>Action → DOM loop</h3>
            <p>Every action returns updated DOM automatically. Agents stay in sync.</p>
          </div>
        </div>
      </section>

      {/* ── Stats bar ── */}
      <section className="home-stats-bar">
        <div className="stat-item">
          <div className="stat-number">45</div>
          <div className="stat-label">REST APIs</div>
        </div>
        <div className="stat-divider" />
        <div className="stat-item">
          <div className="stat-number">12</div>
          <div className="stat-label">Categories</div>
        </div>
        <div className="stat-divider" />
        <div className="stat-item">
          <div className="stat-number">80–90%</div>
          <div className="stat-label">Token savings</div>
        </div>
        <div className="stat-divider" />
        <div className="stat-item">
          <div className="stat-number">&lt;30</div>
          <div className="stat-label">Tokens per action</div>
        </div>
      </section>
    </div>
  )
}
