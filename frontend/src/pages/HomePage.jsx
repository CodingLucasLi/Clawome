import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { DotMatrixBackground } from '../components/DotMatrixBackground'
import '../components/DotMatrixBackground.css'
import './HomePage.css'

export default function HomePage() {
  const { t } = useTranslation()
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
              <h1>{t('home.title')}</h1>
            </div>
            <p className="home-hero-tagline">
              {t('home.tagline1')}<br />
              {t('home.tagline2')}
            </p>
            <div className="hero-actions">
              <Link to="/agent" className="hero-btn hero-btn-primary">
                {t('home.tryAgent')}
              </Link>
              <Link to="/docs" className="hero-btn hero-btn-ghost">
                {t('home.apiDocs')}
              </Link>
            </div>
          </div>

          {/* Right: two path cards */}
          <div className="hero-right">
            {/* API Integration path */}
            <div className="path-card">
              <div className="path-header">
                <span className="path-icon">{'</>'}</span>
                <span className="path-title">{t('home.restApi')}</span>
                <span className="path-tag">{t('home.programmatic')}</span>
              </div>
              <div className="path-steps">
                <div className="path-step">
                  <span className="path-num">1</span>
                  <div>
                    <span className="path-step-label">{t('home.getSkillFile')}</span>
                    <a href="/skill" className="path-link" target="_blank" rel="noopener noreferrer">clawome-skill.md</a>
                  </div>
                </div>
                <div className="path-step">
                  <span className="path-num">2</span>
                  <div>
                    <span className="path-step-label">{t('home.openReadDom')}</span>
                    <code className="path-code">POST /open {'\u2192'} GET /dom</code>
                  </div>
                </div>
                <div className="path-step">
                  <span className="path-num">3</span>
                  <div>
                    <span className="path-step-label">{t('home.actLoop')}</span>
                    <code className="path-code">/click | /type | /scroll {'\u2192'} /dom</code>
                  </div>
                </div>
              </div>
            </div>

            {/* Task Agent path */}
            <div className="path-card path-card-highlight">
              <div className="path-header">
                <span className="path-icon">{'\u{1F9E0}'}</span>
                <span className="path-title">{t('home.taskAgent')}</span>
                <span className="path-tag path-tag-hot">{t('home.autonomous')}</span>
              </div>
              <div className="path-steps">
                <div className="path-step">
                  <span className="path-num">1</span>
                  <div>
                    <span className="path-step-label">{t('home.describeTask')}</span>
                    <span className="path-hint">{t('home.describeHint')}</span>
                  </div>
                </div>
                <div className="path-step">
                  <span className="path-num">2</span>
                  <div>
                    <span className="path-step-label">{t('home.agentPlans')}</span>
                    <span className="path-hint">{t('home.agentHint')}</span>
                  </div>
                </div>
                <div className="path-step">
                  <span className="path-num">3</span>
                  <div>
                    <span className="path-step-label">{t('home.getResults')}</span>
                    <span className="path-hint">{t('home.resultsHint')}</span>
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
          <span className="section-tag">{t('home.howItWorks')}</span>
          <h2>{t('home.fromTask')}</h2>
          <p className="home-section-sub">{t('home.agentAuto')}</p>
        </div>
        <div className="pipeline-demo">
          <div className="pipeline-input">
            <div className="pipeline-prompt-label">{t('home.pipelineTask')}</div>
            <div className="pipeline-prompt">{t('home.pipelineExample')}</div>
          </div>
          <div className="pipeline-flow">
            <div className="pipeline-step">
              <div className="pipeline-step-icon">{'\u{1F9E0}'}</div>
              <div className="pipeline-step-label">{t('home.plan')}</div>
              <div className="pipeline-step-desc">{t('home.planDesc')}</div>
            </div>
            <div className="pipeline-connector"><span>{'\u2192'}</span></div>
            <div className="pipeline-step">
              <div className="pipeline-step-icon">{'\u{1F310}'}</div>
              <div className="pipeline-step-label">{t('home.browse')}</div>
              <div className="pipeline-step-desc">{t('home.browseDesc')}</div>
            </div>
            <div className="pipeline-connector"><span>{'\u2192'}</span></div>
            <div className="pipeline-step">
              <div className="pipeline-step-icon">{'\u{1F50D}'}</div>
              <div className="pipeline-step-label">{t('home.evaluate')}</div>
              <div className="pipeline-step-desc">{t('home.evaluateDesc')}</div>
            </div>
            <div className="pipeline-connector"><span>{'\u2192'}</span></div>
            <div className="pipeline-step pipeline-step-done">
              <div className="pipeline-step-icon">{'\u2705'}</div>
              <div className="pipeline-step-label">{t('home.result')}</div>
              <div className="pipeline-step-desc">{t('home.resultDesc')}</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── DOM Compression ── */}
      <section className="home-section home-comparison">
        <div className="section-header">
          <span className="section-tag">{t('home.domCompression')}</span>
          <h2>{t('home.whatAgentSees')}</h2>
          <p className="home-section-sub">{t('home.rawNoisy')}</p>
        </div>
        <div className="compare-grid">
          <div className="compare-card compare-before">
            <div className="compare-label">{t('home.rawHtml')} <span className="compare-size">{t('home.rawTokens')}</span></div>
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
            <div className="compare-label">{t('home.compressedDom')} <span className="compare-size">{t('home.compressedTokens')}</span></div>
            <pre className="compare-code">{`[1] form(role="search")
  [1.1] textarea(name="q", placeholder="Search")
  [1.2] button: Google Search
  [1.3] button: I'm Feeling Lucky
[2] a(href): About
[3] a(href): Gmail
[4] a(href): Images`}</pre>
          </div>
        </div>
        <p className="compare-caption">{t('home.compareCaption')}</p>
      </section>

      {/* ── Features ── */}
      <section className="home-section home-features-section">
        <div className="section-header">
          <h2>{t('home.builtForAgents')}</h2>
        </div>
        <div className="home-features">
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F9E0}'}</div>
            <h3>{t('home.feat1Title')}</h3>
            <p>{t('home.feat1Desc')}</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u26A1'}</div>
            <h3>{t('home.feat2Title')}</h3>
            <p>{t('home.feat2Desc')}</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F3AF}'}</div>
            <h3>{t('home.feat3Title')}</h3>
            <p>{t('home.feat3Desc')}</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F6E1}'}</div>
            <h3>{t('home.feat4Title')}</h3>
            <p>{t('home.feat4Desc')}</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F9E9}'}</div>
            <h3>{t('home.feat5Title')}</h3>
            <p>{t('home.feat5Desc')}</p>
          </div>
          <div className="home-feature-card">
            <div className="feature-icon">{'\u{1F4CA}'}</div>
            <h3>{t('home.feat6Title')}</h3>
            <p>{t('home.feat6Desc')}</p>
          </div>
        </div>
      </section>

      {/* ── Stats ── */}
      <section className="home-stats-bar">
        <div className="stat-item">
          <div className="stat-number">45+</div>
          <div className="stat-label">{t('home.statApis')}</div>
        </div>
        <div className="stat-divider" />
        <div className="stat-item">
          <div className="stat-number">8</div>
          <div className="stat-label">{t('home.statActions')}</div>
        </div>
        <div className="stat-divider" />
        <div className="stat-item">
          <div className="stat-number">90%</div>
          <div className="stat-label">{t('home.statSaving')}</div>
        </div>
        <div className="stat-divider" />
        <div className="stat-item">
          <div className="stat-number">Auto</div>
          <div className="stat-label">{t('home.statPlanning')}</div>
        </div>
      </section>
    </div>
  )
}
