import { Link } from 'react-router-dom'
import { DotMatrixBackground } from '../components/DotMatrixBackground'
import '../components/DotMatrixBackground.css'
import './HomePage.css'

export default function HomePage() {
  return (
    <div className="home-page">
      {/* ── Hero: left intro + right two paths ── */}
      <section className="home-hero">
        <DotMatrixBackground color="lobster" vibrant />
        <div className="hero-layout">
          {/* Left: brand + intro */}
          <div className="hero-left">
            <div className="hero-brand">
              <img src="/clawome.png" alt="Clawome" className="home-hero-logo" />
              <h1>Clawome</h1>
            </div>
            <p className="home-hero-tagline">
              Browser automation for AI agents.<br />
              From REST APIs to fully autonomous task execution.
            </p>
            <div className="hero-actions">
              <Link to="/agent" className="hero-btn hero-btn-primary">
                Try Task Agent {'\u2192'}
              </Link>
              <Link to="/docs" className="hero-btn hero-btn-ghost">
                API Docs
              </Link>
            </div>
          </div>

          {/* Right: two path cards */}
          <div className="hero-right">
            {/* API Integration path */}
            <div className="path-card">
              <div className="path-header">
                <span className="path-icon">{'</>'}</span>
                <span className="path-title">REST API</span>
                <span className="path-tag">Programmatic</span>
              </div>
              <div className="path-steps">
                <div className="path-step">
                  <span className="path-num">1</span>
                  <div>
                    <span className="path-step-label">Get skill file</span>
                    <a href="/skill" className="path-link" target="_blank" rel="noopener noreferrer">clawome-skill.md</a>
                  </div>
                </div>
                <div className="path-step">
                  <span className="path-num">2</span>
                  <div>
                    <span className="path-step-label">Open & read DOM</span>
                    <code className="path-code">POST /open {'\u2192'} GET /dom</code>
                  </div>
                </div>
                <div className="path-step">
                  <span className="path-num">3</span>
                  <div>
                    <span className="path-step-label">Act & loop</span>
                    <code className="path-code">/click | /type | /scroll {'\u2192'} /dom</code>
                  </div>
                </div>
              </div>
            </div>

            {/* Task Agent path */}
            <div className="path-card path-card-highlight">
              <div className="path-header">
                <span className="path-icon">{'\u{1F9E0}'}</span>
                <span className="path-title">Task Agent</span>
                <span className="path-tag path-tag-hot">Autonomous</span>
              </div>
              <div className="path-steps">
                <div className="path-step">
                  <span className="path-num">1</span>
                  <div>
                    <span className="path-step-label">Describe your task</span>
                    <span className="path-hint">Natural language input</span>
                  </div>
                </div>
                <div className="path-step">
                  <span className="path-num">2</span>
                  <div>
                    <span className="path-step-label">Agent plans & browses</span>
                    <span className="path-hint">Auto subtasks, navigation, decisions</span>
                  </div>
                </div>
                <div className="path-step">
                  <span className="path-num">3</span>
                  <div>
                    <span className="path-step-label">Get structured results</span>
                    <span className="path-hint">Findings, links, completion status</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Pipeline visualization ── */}
      <section className="home-section home-pipeline">
        <div className="section-header">
          <span className="section-tag">How it works</span>
          <h2>From task to result in one command</h2>
          <p className="home-section-sub">The agent autonomously plans, navigates, and delivers.</p>
        </div>
        <div className="pipeline-demo">
          <div className="pipeline-input">
            <div className="pipeline-prompt-label">Task</div>
            <div className="pipeline-prompt">"Search Hacker News for the latest AI news and summarize the top 3 stories"</div>
          </div>
          <div className="pipeline-flow">
            <div className="pipeline-step">
              <div className="pipeline-step-icon">{'\u{1F9E0}'}</div>
              <div className="pipeline-step-label">Plan</div>
              <div className="pipeline-step-desc">Break into subtasks</div>
            </div>
            <div className="pipeline-connector"><span>{'\u2192'}</span></div>
            <div className="pipeline-step">
              <div className="pipeline-step-icon">{'\u{1F310}'}</div>
              <div className="pipeline-step-label">Browse</div>
              <div className="pipeline-step-desc">Navigate & interact</div>
            </div>
            <div className="pipeline-connector"><span>{'\u2192'}</span></div>
            <div className="pipeline-step">
              <div className="pipeline-step-icon">{'\u{1F50D}'}</div>
              <div className="pipeline-step-label">Evaluate</div>
              <div className="pipeline-step-desc">Check & adapt plan</div>
            </div>
            <div className="pipeline-connector"><span>{'\u2192'}</span></div>
            <div className="pipeline-step pipeline-step-done">
              <div className="pipeline-step-icon">{'\u2705'}</div>
              <div className="pipeline-step-label">Result</div>
              <div className="pipeline-step-desc">Structured output</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── DOM Compression ── */}
      <section className="home-section home-comparison">
        <div className="section-header">
          <span className="section-tag">DOM Compression</span>
          <h2>What your agent actually sees</h2>
          <p className="home-section-sub">Raw HTML is noisy. Clawome compresses it to what matters.</p>
        </div>
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
        <p className="compare-caption">7 nodes instead of 800. Every node gets a stable hierarchical ID.</p>
      </section>

      {/* ── Features ── */}
      <section className="home-section home-features-section">
        <div className="section-header">
          <h2>Built for agents</h2>
        </div>
        <div className="home-features">
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F9E0}'}</div>
            <h3>Autonomous execution</h3>
            <p>LLM-powered agent plans subtasks, browses pages, and adapts in real-time.</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u26A1'}</div>
            <h3>80–90% fewer tokens</h3>
            <p>Strips wrappers, scripts, and noise. Agents see only what matters.</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F3AF}'}</div>
            <h3>One-shot targeting</h3>
            <p>Hierarchical IDs like <code>3.1.4</code> — click any element on the first try.</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F6E1}'}</div>
            <h3>Supervisor & recovery</h3>
            <p>Detects infinite loops, recovers from errors, replans when stuck.</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F9E9}'}</div>
            <h3>Per-site compressors</h3>
            <p>Python scripts auto-activate by URL. Each site gets its own optimizer.</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F4CA}'}</div>
            <h3>Real-time observability</h3>
            <p>Live progress, step visualization, token usage, and cost tracking.</p>
          </div>
        </div>
      </section>

      {/* ── Stats ── */}
      <section className="home-stats-bar">
        <div className="stat-item">
          <div className="stat-number">45+</div>
          <div className="stat-label">REST APIs</div>
        </div>
        <div className="stat-divider" />
        <div className="stat-item">
          <div className="stat-number">8</div>
          <div className="stat-label">Action types</div>
        </div>
        <div className="stat-divider" />
        <div className="stat-item">
          <div className="stat-number">90%</div>
          <div className="stat-label">Token savings</div>
        </div>
        <div className="stat-divider" />
        <div className="stat-item">
          <div className="stat-number">Auto</div>
          <div className="stat-label">Task planning</div>
        </div>
      </section>
    </div>
  )
}
