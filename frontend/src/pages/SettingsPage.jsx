import { useState, useEffect, useCallback } from 'react'
import {
  getConfig, setConfig, resetConfig,
  getCompressors, saveCompressor, deleteCompressor, getCompressorTemplate,
} from '../api'
import './SettingsPage.css'

// ── Navigation sections ──

const SECTIONS = [
  { key: 'general',   label: 'General',    icon: '\u2699' },
  { key: 'timeouts',  label: 'Timeouts',   icon: '\u23F1' },
  { key: 'scripts',   label: 'Scripts',    icon: '\u{1F4DC}' },
  { key: 'rules',     label: 'URL Rules',  icon: '\u{1F517}' },
]

// ── Config group definitions per section ──

const SECTION_GROUPS = {
  general: [
    {
      title: 'Browser',
      items: [
        { key: 'headless', label: 'Headless Mode', unit: '', desc: 'Run browser without visible window (takes effect on next browser open). Note: some websites detect headless browsers and may block or return empty pages.', type: 'boolean' },
      ],
    },
    {
      title: 'DOM Walker',
      items: [
        { key: 'max_nodes', label: 'Max Nodes', unit: '', desc: 'Maximum DOM nodes to parse per page' },
        { key: 'max_depth', label: 'Max Depth', unit: 'levels', desc: 'Maximum tree depth for DOM traversal' },
      ],
    },
    {
      title: 'Keyboard & Scroll',
      items: [
        { key: 'type_delay', label: 'Type Delay', unit: 'ms', desc: 'Delay between keystrokes when typing' },
        { key: 'scroll_pixels', label: 'Scroll Distance', unit: 'px', desc: 'Default scroll distance per step' },
      ],
    },
  ],
  timeouts: [
    {
      title: 'Navigation Timeouts',
      items: [
        { key: 'nav_timeout', label: 'Navigation Timeout', unit: 'ms', desc: 'Timeout for page open / back / forward' },
        { key: 'reload_timeout', label: 'Reload Timeout', unit: 'ms', desc: 'Timeout for page reload' },
      ],
    },
    {
      title: 'Page Load Waits',
      items: [
        { key: 'load_wait', label: 'DOM Content Loaded Wait', unit: 'ms', desc: 'Wait for DOM content loaded after action' },
        { key: 'network_idle_wait', label: 'Network Idle Wait', unit: 'ms', desc: 'Wait for network idle after action' },
      ],
    },
    {
      title: 'Interaction Timeouts',
      items: [
        { key: 'click_timeout', label: 'Click Timeout', unit: 'ms', desc: 'Timeout for click / focus actions' },
        { key: 'input_timeout', label: 'Input Timeout', unit: 'ms', desc: 'Timeout for fill / select / check actions' },
        { key: 'hover_timeout', label: 'Hover Timeout', unit: 'ms', desc: 'Timeout for hover action' },
        { key: 'scroll_timeout', label: 'Scroll Timeout', unit: 'ms', desc: 'Timeout for scroll-to-element' },
        { key: 'wait_for_element_timeout', label: 'Wait for Element', unit: 'ms', desc: 'Timeout for wait-for-element-visible' },
      ],
    },
    {
      title: 'Benchmark',
      items: [
        { key: 'benchmark_timeout', label: 'Benchmark Nav Timeout', unit: 'ms', desc: 'Timeout for benchmark page navigation' },
        { key: 'benchmark_idle_wait', label: 'Benchmark Idle Wait', unit: 'ms', desc: 'Wait for network idle in benchmark' },
      ],
    },
  ],
}

const SECTION_META = {
  general: {
    title: 'General',
    desc: 'DOM parsing limits and keyboard/scroll behavior.',
  },
  timeouts: {
    title: 'Timeouts',
    desc: 'Navigation, page load, and interaction timeout values.',
  },
  scripts: {
    title: 'Compressor Scripts',
    desc: 'Pluggable scripts that filter and simplify raw DOM nodes. Each script defines a process() function. Click a tab to configure.',
  },
  rules: {
    title: 'URL Matching Rules',
    desc: 'Platform-level rules override script-level URL_PATTERNS. First match wins. Unmatched URLs use the default compressor.',
  },
}

export default function SettingsPage() {
  const [section, setSection] = useState('general')

  // Config state
  const [values, setValues] = useState({})
  const [defaults, setDefaults] = useState({})
  const [overrides, setOverrides] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Compressor state
  const [scripts, setScripts] = useState([])
  const [selectedScript, setSelectedScript] = useState(null)
  const [editCode, setEditCode] = useState('')
  const [codeModified, setCodeModified] = useState(false)
  const [rules, setRules] = useState([])
  const [scriptSaving, setScriptSaving] = useState(false)
  const [disabledCompressors, setDisabledCompressors] = useState([])
  const [compressorSettings, setCompressorSettings] = useState({})
  const [scriptSubTab, setScriptSubTab] = useState('settings') // 'settings' | 'source'

  const load = useCallback(async () => {
    try {
      const [configRes, compRes] = await Promise.all([getConfig(), getCompressors()])
      setValues(configRes.data.config)
      setDefaults(configRes.data.defaults)
      setOverrides(configRes.data.overrides)
      setRules(configRes.data.config.compressor_rules || [])
      setDisabledCompressors(configRes.data.config.disabled_compressors || [])
      setCompressorSettings(configRes.data.config.compressor_settings || {})
      setScripts(compRes.data.scripts)
      if (compRes.data.scripts.length > 0) {
        const def = compRes.data.scripts.find(s => s.name === 'default') || compRes.data.scripts[0]
        setSelectedScript(def.name)
        setEditCode(def.code)
      }
    } catch (err) {
      console.error('Failed to load:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // --- Config handlers ---

  const handleChange = (key, val) => {
    setValues(prev => ({ ...prev, [key]: val }))
    setSaved(false)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = {
        ...values,
        compressor_rules: rules,
        disabled_compressors: disabledCompressors,
        compressor_settings: compressorSettings,
      }
      const res = await setConfig(payload)
      setValues(res.data.config)
      setOverrides(
        Object.fromEntries(
          Object.entries(res.data.config).filter(([k, v]) => v !== defaults[k])
        )
      )
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      alert('Save failed: ' + (err.response?.data?.message || err.message))
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!window.confirm('Reset all settings to defaults? This cannot be undone.')) return
    setSaving(true)
    try {
      const res = await resetConfig()
      setValues(res.data.config)
      setOverrides({})
      setRules([])
      setDisabledCompressors(res.data.config.disabled_compressors || [])
      setCompressorSettings({})
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      alert('Reset failed: ' + (err.response?.data?.message || err.message))
    } finally {
      setSaving(false)
    }
  }

  // --- Compressor toggle handler ---

  const toggleCompressor = async (name) => {
    const isCurrentlyDisabled = disabledCompressors.includes(name)
    const newDisabled = isCurrentlyDisabled
      ? disabledCompressors.filter(n => n !== name)
      : [...disabledCompressors, name]
    setDisabledCompressors(newDisabled)
    try {
      await setConfig({ disabled_compressors: newDisabled })
      const compRes = await getCompressors()
      setScripts(compRes.data.scripts)
    } catch (err) {
      setDisabledCompressors(disabledCompressors)
      alert('Toggle failed: ' + (err.response?.data?.message || err.message))
    }
  }

  // --- Per-script setting change ---

  const handleScriptSetting = async (scriptName, key, value) => {
    const newSettings = { ...compressorSettings }
    if (!newSettings[scriptName]) newSettings[scriptName] = {}
    newSettings[scriptName] = { ...newSettings[scriptName], [key]: value }
    setCompressorSettings(newSettings)
    try {
      await setConfig({ compressor_settings: newSettings })
      const compRes = await getCompressors()
      setScripts(compRes.data.scripts)
    } catch (err) {
      alert('Setting update failed: ' + (err.response?.data?.message || err.message))
    }
  }

  const resetScriptSetting = async (scriptName, key) => {
    const newSettings = { ...compressorSettings }
    if (newSettings[scriptName]) {
      const updated = { ...newSettings[scriptName] }
      delete updated[key]
      if (Object.keys(updated).length === 0) {
        delete newSettings[scriptName]
      } else {
        newSettings[scriptName] = updated
      }
    }
    setCompressorSettings(newSettings)
    try {
      await setConfig({ compressor_settings: newSettings })
      const compRes = await getCompressors()
      setScripts(compRes.data.scripts)
    } catch (err) {
      alert('Reset failed: ' + (err.response?.data?.message || err.message))
    }
  }

  // --- Compressor handlers ---

  const selectScript = (name) => {
    const s = scripts.find(sc => sc.name === name)
    if (s) {
      setSelectedScript(name)
      setEditCode(s.code)
      setCodeModified(false)
      // Auto-select appropriate sub-tab
      const hasSettings = s.settings && s.settings.length > 0
      setScriptSubTab(hasSettings ? 'settings' : 'source')
    }
  }

  const handleNewScript = async () => {
    const name = prompt('Script name (lowercase, no spaces):')
    if (!name || !name.trim()) return
    const clean = name.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_')
    if (scripts.find(s => s.name === clean)) {
      alert(`Script "${clean}" already exists`)
      return
    }
    try {
      const res = await getCompressorTemplate()
      const code = res.data.code
      await saveCompressor(clean, code)
      const updated = await getCompressors()
      setScripts(updated.data.scripts)
      setSelectedScript(clean)
      setEditCode(code)
      setCodeModified(false)
    } catch (err) {
      alert('Create failed: ' + (err.response?.data?.message || err.message))
    }
  }

  const handleSaveScript = async () => {
    if (!selectedScript || selectedScript === 'default') return
    const s = scripts.find(sc => sc.name === selectedScript)
    if (s?.official) return
    setScriptSaving(true)
    try {
      await saveCompressor(selectedScript, editCode)
      const updated = await getCompressors()
      setScripts(updated.data.scripts)
      setCodeModified(false)
    } catch (err) {
      alert('Save failed: ' + (err.response?.data?.message || err.message))
    } finally {
      setScriptSaving(false)
    }
  }

  const handleDeleteScript = async () => {
    if (!selectedScript || selectedScript === 'default') return
    const s = scripts.find(sc => sc.name === selectedScript)
    if (s?.official) return
    if (!window.confirm(`Delete script "${selectedScript}"?`)) return
    try {
      await deleteCompressor(selectedScript)
      setRules(prev => prev.filter(r => r.script !== selectedScript))
      const updated = await getCompressors()
      setScripts(updated.data.scripts)
      selectScript('default')
    } catch (err) {
      alert('Delete failed: ' + (err.response?.data?.message || err.message))
    }
  }

  // --- Rules handlers ---

  const addRule = () => {
    setRules(prev => [...prev, { pattern: '', script: '' }])
  }

  const updateRule = (index, field, value) => {
    setRules(prev => {
      const next = [...prev]
      next[index] = { ...next[index], [field]: value }
      return next
    })
  }

  const removeRule = (index) => {
    setRules(prev => prev.filter((_, i) => i !== index))
  }

  if (loading) {
    return (
      <div className="settings-page">
        <div className="settings-sidebar" />
        <div className="settings-panel">
          <div className="settings-empty">Loading...</div>
        </div>
      </div>
    )
  }

  const currentScript = scripts.find(s => s.name === selectedScript)
  const isReadonly = currentScript?.builtin || currentScript?.official
  const meta = SECTION_META[section]

  // ── Render config groups (General / Timeouts) ──
  const renderConfigSection = (sectionKey) => {
    const groups = SECTION_GROUPS[sectionKey] || []
    return (
      <>
        <div className="settings-groups">
          {groups.map(group => (
            <div key={group.title} className="settings-group">
              <h3 className="settings-group-title">{group.title}</h3>
              <div className="settings-items">
                {group.items.map(item => {
                  const isOverridden = item.key in overrides
                  const defaultVal = defaults[item.key]
                  const isBool = item.type === 'boolean'
                  return (
                    <div key={item.key} className="settings-item">
                      <div className="settings-item-info">
                        <label className="settings-label">
                          {item.label}
                          {isOverridden && <span className="settings-modified">modified</span>}
                        </label>
                        <span className="settings-desc-text">{item.desc}</span>
                      </div>
                      <div className="settings-item-input">
                        {isBool ? (
                          <label className="settings-toggle">
                            <input
                              type="checkbox"
                              checked={!!values[item.key]}
                              onChange={e => handleChange(item.key, e.target.checked)}
                            />
                            <span className="settings-toggle-slider" />
                            <span className="settings-toggle-label">
                              {values[item.key] ? 'On' : 'Off'}
                            </span>
                          </label>
                        ) : (
                          <>
                            <input
                              type="number"
                              className={`settings-input ${isOverridden ? 'settings-input-modified' : ''}`}
                              value={values[item.key] ?? ''}
                              onChange={e => handleChange(item.key, Number(e.target.value))}
                            />
                            {item.unit && <span className="settings-unit">{item.unit}</span>}
                            <span
                              className="settings-default"
                              title="Reset to default"
                              onClick={() => handleChange(item.key, defaultVal)}
                            >
                              default: {defaultVal}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
        <div className="settings-actions">
          <button className="settings-save" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : saved ? 'Saved' : 'Save Changes'}
          </button>
          <button className="settings-reset" onClick={handleReset} disabled={saving}>
            Reset All to Defaults
          </button>
        </div>
      </>
    )
  }

  // ── Render Scripts section — split layout: left list + right detail ──
  const renderScriptsSection = () => {
    const enabled = currentScript && !disabledCompressors.includes(currentScript.name)
    const hasSettings = currentScript?.settings?.length > 0
    const isCustom = currentScript && !currentScript.builtin && !currentScript.official

    return (
      <div className="scripts-layout">
        {/* ── Left: script list ── */}
        <div className="scripts-list">
          <div className="scripts-list-header">
            <span className="scripts-list-title">Scripts</span>
            <button className="scripts-list-add" onClick={handleNewScript} title="New script">+</button>
          </div>
          <div className="scripts-list-items">
            {scripts.map(s => {
              const isDisabled = disabledCompressors.includes(s.name)
              const isActive = selectedScript === s.name
              return (
                <button
                  key={s.name}
                  className={`scripts-list-item ${isActive ? 'scripts-list-item-active' : ''} ${!s.builtin && isDisabled ? 'scripts-list-item-disabled' : ''}`}
                  onClick={() => selectScript(s.name)}
                >
                  <span className="scripts-list-item-name">{s.name}</span>
                  {s.builtin && <span className="scripts-list-item-badge">core</span>}
                  {s.official && !s.builtin && <span className="scripts-list-item-badge">official</span>}
                  {!s.builtin && !s.official && <span className="scripts-list-item-badge scripts-list-item-badge-custom">custom</span>}
                </button>
              )
            })}
          </div>
        </div>

        {/* ── Right: script detail ── */}
        <div className="scripts-detail">
          {currentScript ? (
            <>
              {/* Header bar: name + badges + toggle */}
              <div className="script-panel-header">
                <div className="script-panel-info">
                  <div className="script-panel-title-row">
                    <span className="script-panel-name">{currentScript.name}.py</span>
                    {currentScript.version && <span className="script-panel-version">v{currentScript.version}</span>}
                    {currentScript.id_conflict && <span className="script-panel-conflict">ID conflict</span>}
                  </div>
                  {currentScript.description && (
                    <span className="script-panel-desc">{currentScript.description}</span>
                  )}
                  {currentScript.url_patterns?.length > 0 && (
                    <span className="script-panel-patterns">
                      {currentScript.url_patterns.join('  |  ')}
                    </span>
                  )}
                </div>
                {!currentScript.builtin && (
                  <div className="script-panel-toggle">
                    <label className="settings-toggle">
                      <input
                        type="checkbox"
                        checked={enabled}
                        onChange={() => toggleCompressor(currentScript.name)}
                      />
                      <span className="settings-toggle-slider" />
                      <span className="settings-toggle-label">
                        {enabled ? 'On' : 'Off'}
                      </span>
                    </label>
                  </div>
                )}
              </div>

              {/* Sub-tabs: Settings | Source */}
              <div className="script-subtabs">
                {hasSettings && (
                  <button
                    className={`script-subtab ${scriptSubTab === 'settings' ? 'script-subtab-active' : ''}`}
                    onClick={() => setScriptSubTab('settings')}
                  >
                    Settings
                  </button>
                )}
                <button
                  className={`script-subtab ${scriptSubTab === 'source' ? 'script-subtab-active' : ''}`}
                  onClick={() => setScriptSubTab('source')}
                >
                  Source Code
                  {isCustom && codeModified && <span className="script-subtab-dot" />}
                </button>
                {isCustom && (
                  <button className="script-subtab script-subtab-danger" onClick={handleDeleteScript}>
                    Delete
                  </button>
                )}
              </div>

              {/* Sub-tab content */}
              <div className="script-subtab-content">
                {/* Settings tab */}
                {scriptSubTab === 'settings' && hasSettings && (
                  <div className="script-settings-body">
                    <div className="settings-items">
                      {currentScript.settings.map(item => {
                        const val = currentScript.settings_values?.[item.key] ?? item.default
                        const isBool = item.type === 'boolean'
                        const isOverridden = compressorSettings[currentScript.name]?.[item.key] !== undefined
                        return (
                          <div key={item.key} className="settings-item">
                            <div className="settings-item-info">
                              <label className="settings-label">
                                {item.label}
                                {isOverridden && <span className="settings-modified">modified</span>}
                              </label>
                              <span className="settings-desc-text">{item.desc}</span>
                            </div>
                            <div className="settings-item-input">
                              {isBool ? (
                                <label className="settings-toggle">
                                  <input
                                    type="checkbox"
                                    checked={!!val}
                                    onChange={e => handleScriptSetting(currentScript.name, item.key, e.target.checked)}
                                  />
                                  <span className="settings-toggle-slider" />
                                  <span className="settings-toggle-label">
                                    {val ? 'On' : 'Off'}
                                  </span>
                                </label>
                              ) : (
                                <>
                                  <input
                                    type="number"
                                    className={`settings-input ${isOverridden ? 'settings-input-modified' : ''}`}
                                    value={val ?? ''}
                                    onChange={e => handleScriptSetting(currentScript.name, item.key, Number(e.target.value))}
                                  />
                                  <span
                                    className="settings-default"
                                    title="Reset to default"
                                    onClick={() => resetScriptSetting(currentScript.name, item.key)}
                                  >
                                    default: {item.default}
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Source code tab */}
                {scriptSubTab === 'source' && (
                  <div className="script-source-body">
                    <textarea
                      className="script-code"
                      value={editCode}
                      readOnly={isReadonly}
                      onChange={e => { setEditCode(e.target.value); setCodeModified(true) }}
                      spellCheck={false}
                    />
                    {isCustom && (
                      <div className="script-actions">
                        <button
                          className="script-save"
                          onClick={handleSaveScript}
                          disabled={scriptSaving || !codeModified}
                        >
                          {scriptSaving ? 'Saving...' : 'Save Script'}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="scripts-detail-empty">Select a script to view its configuration.</div>
          )}
        </div>
      </div>
    )
  }

  // ── Render URL Rules section ──
  const scriptLevelRules = scripts
    .filter(s => s.url_patterns && s.url_patterns.length > 0)
    .flatMap(s => s.url_patterns.map(p => ({ pattern: p, script: s.name, enabled: s.enabled })))

  const renderRulesSection = () => (
    <>
      {/* Tier 1: Platform-level rules */}
      <div className="rules-section">
        <div className="settings-group">
          <h3 className="settings-group-title">Platform Rules (Priority 1)</h3>
          <div style={{ padding: '12px 16px' }}>
            <table className="rules-table">
              <thead>
                <tr>
                  <th>URL Pattern</th>
                  <th>Script</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule, i) => (
                  <tr key={i}>
                    <td>
                      <input
                        type="text"
                        className="rule-pattern"
                        placeholder="*google.com/search*"
                        value={rule.pattern}
                        onChange={e => updateRule(i, 'pattern', e.target.value)}
                      />
                    </td>
                    <td>
                      <select
                        className="rule-script"
                        value={rule.script}
                        onChange={e => updateRule(i, 'script', e.target.value)}
                      >
                        <option value="">-- select --</option>
                        {scripts.filter(s => !s.builtin).map(s => (
                          <option key={s.name} value={s.name}>{s.name}</option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <button className="rule-remove" onClick={() => removeRule(i)}>x</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button className="rule-add" onClick={addRule}>+ Add Rule</button>
          </div>
        </div>
      </div>

      {/* Tier 2: Script-level URL_PATTERNS (read-only) */}
      <div className="rules-section">
        <div className="settings-group">
          <h3 className="settings-group-title">Script-Bundled Rules (Priority 2)</h3>
          <div style={{ padding: '12px 16px' }}>
            {scriptLevelRules.length > 0 ? (
              <table className="rules-table">
                <thead>
                  <tr>
                    <th>URL Pattern</th>
                    <th>Script</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {scriptLevelRules.map((rule, i) => (
                    <tr key={i} className={`rule-readonly ${!rule.enabled ? 'rule-disabled' : ''}`}>
                      <td>
                        <code className="rule-pattern-readonly">{rule.pattern}</code>
                      </td>
                      <td>
                        <span className="rule-script-readonly">{rule.script}</span>
                      </td>
                      <td>
                        {rule.enabled
                          ? <span className="rule-source-badge">active</span>
                          : <span className="rule-source-badge rule-source-badge-off">off</span>
                        }
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="rules-empty">No scripts have declared URL_PATTERNS yet.</div>
            )}
            <div className="rules-hint">
              Toggle scripts in the Scripts tab. Edit URL_PATTERNS in the script source code to add custom rules.
            </div>
          </div>
        </div>
      </div>

      <div className="rules-fallback">Fallback: URLs not matching any rule use the default compressor.</div>

      <div className="settings-actions">
        <button className="settings-save" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : saved ? 'Saved' : 'Save Rules'}
        </button>
      </div>
    </>
  )

  return (
    <div className="settings-page">
      {/* ── Sidebar ── */}
      <aside className="settings-sidebar">
        <h4 className="settings-sidebar-title">Settings</h4>
        <nav className="settings-nav">
          {SECTIONS.map(s => (
            <button
              key={s.key}
              className={`settings-nav-item ${section === s.key ? 'active' : ''}`}
              onClick={() => setSection(s.key)}
            >
              <span className="settings-nav-icon">{s.icon}</span>
              {s.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* ── Panel ── */}
      <div className={`settings-panel ${section === 'scripts' ? 'settings-panel-wide' : ''}`}>
        <div className="settings-panel-header">
          <h1 className="settings-panel-title">{meta.title}</h1>
          <p className="settings-panel-desc">{meta.desc}</p>
        </div>

        {section === 'general' && renderConfigSection('general')}
        {section === 'timeouts' && renderConfigSection('timeouts')}
        {section === 'scripts' && renderScriptsSection()}
        {section === 'rules' && renderRulesSection()}
      </div>
    </div>
  )
}
