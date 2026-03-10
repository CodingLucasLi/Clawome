import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  getConfig, setConfig, resetConfig,
  getCompressors, saveCompressor, deleteCompressor, getCompressorTemplate,
} from '../api'
import './SettingsPage.css'

// ── LLM Provider presets ──

const LLM_PROVIDER_PRESETS = [
  { key: 'dashscope', label: 'DashScope (Qwen)',
    apiBase: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen3.5-plus', 'qwen-plus', 'qwen-max', 'qwen-turbo'], needsApiBase: true },
  { key: 'openai', label: 'OpenAI',
    apiBase: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'o1-mini', 'gpt-4-turbo'], needsApiBase: true },
  { key: 'anthropic', label: 'Anthropic (Claude)',
    apiBase: '',
    models: ['claude-sonnet-4-20250514', 'claude-3-5-haiku-20241022'], needsApiBase: false },
  { key: 'google', label: 'Google (Gemini)',
    apiBase: '',
    models: ['gemini-2.0-flash', 'gemini-2.5-pro'], needsApiBase: false },
  { key: 'deepseek', label: 'DeepSeek',
    apiBase: '',
    models: ['deepseek-chat', 'deepseek-reasoner'], needsApiBase: false },
  { key: 'moonshot', label: 'Moonshot (Kimi)',
    apiBase: '',
    models: ['moonshot-v1-128k', 'moonshot-v1-32k', 'moonshot-v1-8k'], needsApiBase: false },
  { key: 'zhipu', label: 'Zhipu (GLM)',
    apiBase: '',
    models: ['glm-4.7', 'glm-4.5'], needsApiBase: false },
  { key: 'volcengine', label: 'Volcengine (Doubao)',
    apiBase: 'https://ark.cn-beijing.volces.com/api/v3',
    models: ['doubao-seed-1.6-250615', 'doubao-1.5-pro-256k-250115', 'doubao-pro-32k-241215', 'deepseek-r1-250120', 'deepseek-v3-250324'], needsApiBase: true },
  { key: 'minimax', label: 'MiniMax',
    apiBase: '',
    models: ['minimax-text-01'], needsApiBase: false },
  { key: 'mistral', label: 'Mistral',
    apiBase: '',
    models: ['mistral-large-latest', 'codestral-latest'], needsApiBase: false },
  { key: 'groq', label: 'Groq',
    apiBase: '',
    models: ['llama-3.3-70b-versatile', 'mixtral-8x7b-32768'], needsApiBase: false },
  { key: 'xai', label: 'xAI (Grok)',
    apiBase: '',
    models: ['grok-2', 'grok-3-mini'], needsApiBase: false },
  { key: 'custom', label: 'Custom',
    apiBase: '', models: [], needsApiBase: true },
]

// ── Navigation sections ──

const SECTIONS = [
  { key: 'general',   label: 'settings.general',    icon: '\u2699' },
  { key: 'timeouts',  label: 'settings.timeouts',   icon: '\u23F1' },
  { key: 'agent',     label: 'settings.agentTab',   icon: '\u{1F916}' },
  { key: 'scripts',   label: 'settings.scripts',    icon: '\u{1F4DC}' },
  { key: 'rules',     label: 'settings.urlRules',   icon: '\u{1F517}' },
]

// ── Config group definitions per section ──

const SECTION_GROUPS = {
  general: [
    {
      title: 'settings.browser',
      items: [
        { key: 'headless', label: 'Headless Mode', unit: '', desc: 'settings.headlessDesc', type: 'boolean' },
        { key: 'screen_refresh_interval', label: 'Screen Refresh', unit: 'ms', desc: 'settings.screenRefreshDesc' },
        { key: 'browser_window_x', label: 'Window X', unit: 'px', desc: 'settings.windowXDesc' },
        { key: 'browser_window_y', label: 'Window Y', unit: 'px', desc: 'settings.windowYDesc' },
        { key: 'browser_window_width', label: 'Window Width', unit: 'px', desc: 'settings.windowWidthDesc' },
        { key: 'browser_window_height', label: 'Window Height', unit: 'px', desc: 'settings.windowHeightDesc' },
      ],
    },
    {
      title: 'settings.domWalker',
      items: [
        { key: 'max_nodes', label: 'Max Nodes', unit: '', desc: 'settings.maxNodesDesc' },
        { key: 'max_depth', label: 'Max Depth', unit: 'levels', desc: 'settings.maxDepthDesc' },
      ],
    },
    {
      title: 'settings.domLite',
      items: [
        { key: 'lite_text_max', label: 'Truncate Threshold', unit: 'chars', desc: 'settings.truncateDesc' },
        { key: 'lite_text_head', label: 'Keep Head Length', unit: 'chars', desc: 'settings.keepHeadDesc' },
      ],
    },
    {
      title: 'settings.keyboardScroll',
      items: [
        { key: 'type_delay', label: 'Type Delay', unit: 'ms', desc: 'settings.typeDelayDesc' },
        { key: 'scroll_pixels', label: 'Scroll Distance', unit: 'px', desc: 'settings.scrollDistDesc' },
      ],
    },
  ],
  agent: [
    {
      title: 'settings.llmProvider',
      custom: 'llm_provider',  // rendered by custom code
      items: [],
    },
    {
      title: 'settings.llmParams',
      items: [
        { key: 'llm_temperature', label: 'Temperature', unit: '', desc: 'settings.temperatureDesc' },
        { key: 'llm_max_tokens', label: 'Max Tokens', unit: 'tokens', desc: 'settings.maxTokensDesc' },
      ],
    },
    {
      title: 'settings.agentBehavior',
      items: [
        { key: 'agent_max_steps', label: 'Max Steps per Subtask', unit: 'steps', desc: 'settings.maxStepsDesc' },
        { key: 'agent_max_history', label: 'Chat History Length', unit: 'msgs', desc: 'settings.maxHistoryDesc' },
        { key: 'agent_start_url', label: 'Start URL', unit: '', desc: 'settings.startUrlDesc', type: 'text', placeholder: 'https://www.baidu.com' },
      ],
    },
  ],
  timeouts: [
    {
      title: 'settings.navTimeouts',
      items: [
        { key: 'nav_timeout', label: 'Navigation Timeout', unit: 'ms', desc: 'settings.navTimeoutDesc' },
        { key: 'reload_timeout', label: 'Reload Timeout', unit: 'ms', desc: 'settings.reloadTimeoutDesc' },
      ],
    },
    {
      title: 'settings.pageLoadWaits',
      items: [
        { key: 'load_wait', label: 'DOM Content Loaded Wait', unit: 'ms', desc: 'settings.loadWaitDesc' },
        { key: 'network_idle_wait', label: 'Network Idle Wait', unit: 'ms', desc: 'settings.networkIdleDesc' },
      ],
    },
    {
      title: 'settings.interactionTimeouts',
      items: [
        { key: 'click_timeout', label: 'Click Timeout', unit: 'ms', desc: 'settings.clickTimeoutDesc' },
        { key: 'input_timeout', label: 'Input Timeout', unit: 'ms', desc: 'settings.inputTimeoutDesc' },
        { key: 'hover_timeout', label: 'Hover Timeout', unit: 'ms', desc: 'settings.hoverTimeoutDesc' },
        { key: 'scroll_timeout', label: 'Scroll Timeout', unit: 'ms', desc: 'settings.scrollTimeoutDesc' },
        { key: 'wait_for_element_timeout', label: 'Wait for Element', unit: 'ms', desc: 'settings.waitElementDesc' },
      ],
    },
    {
      title: 'settings.benchmarkGroup',
      items: [
        { key: 'benchmark_timeout', label: 'Benchmark Nav Timeout', unit: 'ms', desc: 'settings.benchNavDesc' },
        { key: 'benchmark_idle_wait', label: 'Benchmark Idle Wait', unit: 'ms', desc: 'settings.benchIdleDesc' },
      ],
    },
  ],
}

const SECTION_META = {
  general: {
    title: 'settings.general',
    desc: 'settings.generalDesc',
  },
  agent: {
    title: 'settings.agentTab',
    desc: 'settings.agentDesc',
  },
  timeouts: {
    title: 'settings.timeouts',
    desc: 'settings.timeoutsDesc',
  },
  scripts: {
    title: 'settings.scripts',
    desc: 'settings.scriptsDesc',
  },
  rules: {
    title: 'settings.urlRules',
    desc: 'settings.rulesDesc',
  },
}

export default function SettingsPage() {
  const { t } = useTranslation()
  const [section, setSection] = useState('general')

  // Config state
  const [values, setValues] = useState({})
  const [defaults, setDefaults] = useState({})
  const [overrides, setOverrides] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)
  // provider → api_key cache (persisted in localStorage)
  const [providerKeys, setProviderKeys] = useState(() => {
    try { return JSON.parse(localStorage.getItem('clawome_provider_keys') || '{}') }
    catch { return {} }
  })


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
      const cfg = configRes.data.config
      setValues(cfg)
      setDefaults(configRes.data.defaults)
      setOverrides(configRes.data.overrides)
      // Backend is the source of truth — always overwrite cache for current provider
      const p = cfg.llm_provider || 'dashscope'
      setProviderKeys(prev => {
        const updated = { ...prev, [p]: cfg.llm_api_key || '' }
        try { localStorage.setItem('clawome_provider_keys', JSON.stringify(updated)) } catch {}
        return updated
      })
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
      // Persist current provider's key to localStorage cache
      const provider = res.data.config.llm_provider || 'dashscope'
      const apiKey = res.data.config.llm_api_key || ''
      if (apiKey) {
        const updated = { ...providerKeys, [provider]: apiKey }
        setProviderKeys(updated)
        try { localStorage.setItem('clawome_provider_keys', JSON.stringify(updated)) } catch {}
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      alert('Save failed: ' + (err.response?.data?.message || err.message))
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!window.confirm(t('settings.confirmReset'))) return
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
    const name = prompt(t('settings.scriptName'))
    if (!name || !name.trim()) return
    const clean = name.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_')
    if (scripts.find(s => s.name === clean)) {
      alert(t('settings.scriptExists', { name: clean }))
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
    if (!window.confirm(t('settings.confirmDelete', { name: selectedScript }))) return
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
          <div className="settings-empty">{t('settings.loading')}</div>
        </div>
      </div>
    )
  }

  const currentScript = scripts.find(s => s.name === selectedScript)
  const isReadonly = currentScript?.builtin || currentScript?.official
  const meta = SECTION_META[section]

  // ── Provider change handler (auto-fill api_base + model) ──
  const handleProviderChange = (providerKey) => {
    const oldProvider = values.llm_provider || 'dashscope'
    const preset = LLM_PROVIDER_PRESETS.find(p => p.key === providerKey) || LLM_PROVIDER_PRESETS[0]
    const newValues = { ...values, llm_provider: providerKey }
    // Save current provider's API key to cache, restore new provider's cached key
    const updated = { ...providerKeys, [oldProvider]: values.llm_api_key || '' }
    setProviderKeys(updated)
    try { localStorage.setItem('clawome_provider_keys', JSON.stringify(updated)) } catch {}
    newValues.llm_api_key = updated[providerKey] ?? ''
    // Auto-fill api_base
    if (preset.apiBase) {
      newValues.llm_api_base = preset.apiBase
    } else if (!preset.needsApiBase) {
      newValues.llm_api_base = ''
    }
    // Auto-fill default model
    if (preset.models.length > 0) {
      newValues.llm_model = preset.models[0]
    } else {
      newValues.llm_model = ''
    }
    setValues(newValues)
    setSaved(false)
  }

  // ── Render LLM Provider custom group ──
  const renderLLMProviderGroup = () => {
    const currentProvider = values.llm_provider || 'dashscope'
    const preset = LLM_PROVIDER_PRESETS.find(p => p.key === currentProvider) || LLM_PROVIDER_PRESETS[0]
    const showApiBase = preset.needsApiBase || currentProvider === 'custom'

    return (
      <div className="settings-items">
        {/* Provider dropdown */}
        <div className="settings-item">
          <div className="settings-item-info">
            <label className="settings-label">{t('settings.provider')}</label>
            <span className="settings-desc-text">{t('settings.providerDesc')}</span>
          </div>
          <div className="settings-item-input">
            <select
              className="settings-input settings-input-text"
              value={currentProvider}
              onChange={e => handleProviderChange(e.target.value)}
            >
              {LLM_PROVIDER_PRESETS.map(p => (
                <option key={p.key} value={p.key}>{p.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* API Key */}
        <div className="settings-item">
          <div className="settings-item-info">
            <label className="settings-label">API Key</label>
            <span className="settings-desc-text">{t('settings.apiKeyDesc')}</span>
          </div>
          <div className="settings-item-input">
            <div style={{ position: 'relative', display: 'inline-block' }}>
              <input
                type={showApiKey ? 'text' : 'password'}
                className={`settings-input settings-input-text ${'llm_api_key' in overrides ? 'settings-input-modified' : ''}`}
                value={values.llm_api_key ?? ''}
                placeholder="sk-..."
                onChange={e => handleChange('llm_api_key', e.target.value)}
                style={{ paddingRight: 30 }}
              />
              <svg
                className="settings-eye-toggle"
                onClick={() => setShowApiKey(v => !v)}
                width="16" height="16" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round"
              >
                {showApiKey ? (
                  <>
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </>
                ) : (
                  <>
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </>
                )}
              </svg>
            </div>
          </div>
        </div>

        {/* API Base URL — only for providers that need it */}
        {showApiBase && (
          <div className="settings-item">
            <div className="settings-item-info">
              <label className="settings-label">API Base URL</label>
              <span className="settings-desc-text">{t('settings.apiBaseDesc')}</span>
            </div>
            <div className="settings-item-input">
              <input
                type="text"
                className={`settings-input settings-input-text ${'llm_api_base' in overrides ? 'settings-input-modified' : ''}`}
                value={values.llm_api_base ?? ''}
                placeholder={preset.apiBase || 'https://...'}
                onChange={e => handleChange('llm_api_base', e.target.value)}
              />
            </div>
          </div>
        )}

        {/* Model — plain text input */}
        <div className="settings-item">
          <div className="settings-item-info">
            <label className="settings-label">{t('settings.modelName')}</label>
            <span className="settings-desc-text">{t('settings.modelNameDesc')}</span>
          </div>
          <div className="settings-item-input">
            <input
              type="text"
              className={`settings-input settings-input-text ${'llm_model' in overrides ? 'settings-input-modified' : ''}`}
              value={values.llm_model ?? ''}
              placeholder={preset.models[0] || 'model-name'}
              onChange={e => handleChange('llm_model', e.target.value)}
            />
          </div>
        </div>
      </div>
    )
  }

  // ── Render config groups (General / Timeouts / Agent) ──
  const renderConfigSection = (sectionKey) => {
    const groups = SECTION_GROUPS[sectionKey] || []
    return (
      <>
        <div className="settings-groups">
          {groups.map(group => (
            <div key={group.title} className="settings-group">
              <h3 className="settings-group-title">{t(group.title)}</h3>
              {group.custom === 'llm_provider' ? renderLLMProviderGroup() : (
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
                          {isOverridden && <span className="settings-modified">{t('settings.modified')}</span>}
                        </label>
                        <span className="settings-desc-text">{t(item.desc)}</span>
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
                              {values[item.key] ? t('settings.on') : t('settings.off')}
                            </span>
                          </label>
                        ) : item.type === 'text' || item.type === 'password' ? (
                          <input
                            type={item.type}
                            className={`settings-input settings-input-text ${isOverridden ? 'settings-input-modified' : ''}`}
                            value={values[item.key] ?? ''}
                            placeholder={item.placeholder || (item.type === 'password' ? '(not set)' : '')}
                            onChange={e => handleChange(item.key, e.target.value)}
                          />
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
                              {t('settings.default')}: {defaultVal}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
              )}
            </div>
          ))}
        </div>
        <div className="settings-actions">
          <button className="settings-save" onClick={handleSave} disabled={saving}>
            {saving ? t('settings.saving') : saved ? t('settings.saved') : t('settings.saveChanges')}
          </button>
          <button className="settings-reset" onClick={handleReset} disabled={saving}>
            {t('settings.resetAll')}
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
            <span className="scripts-list-title">{t('settings.scripts')}</span>
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
                  {s.builtin && <span className="scripts-list-item-badge">{t('settings.core')}</span>}
                  {s.official && !s.builtin && <span className="scripts-list-item-badge">{t('settings.official')}</span>}
                  {!s.builtin && !s.official && <span className="scripts-list-item-badge scripts-list-item-badge-custom">{t('settings.custom')}</span>}
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
                        {enabled ? t('settings.on') : t('settings.off')}
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
                    {t('settings.settingsTab')}
                  </button>
                )}
                <button
                  className={`script-subtab ${scriptSubTab === 'source' ? 'script-subtab-active' : ''}`}
                  onClick={() => setScriptSubTab('source')}
                >
                  {t('settings.sourceCode')}
                  {isCustom && codeModified && <span className="script-subtab-dot" />}
                </button>
                {isCustom && (
                  <button className="script-subtab script-subtab-danger" onClick={handleDeleteScript}>
                    {t('settings.delete')}
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
                                {isOverridden && <span className="settings-modified">{t('settings.modified')}</span>}
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
                                    {val ? t('settings.on') : t('settings.off')}
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
                                    {t('settings.default')}: {item.default}
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
                          {scriptSaving ? t('settings.savingScript') : t('settings.saveScript')}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="scripts-detail-empty">{t('settings.selectScript')}</div>
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
          <h3 className="settings-group-title">{t('settings.platformRules')}</h3>
          <div style={{ padding: '12px 16px' }}>
            <table className="rules-table">
              <thead>
                <tr>
                  <th>{t('settings.urlPattern')}</th>
                  <th>{t('settings.script')}</th>
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
                        <option value="">{t('settings.selectPlaceholder')}</option>
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
            <button className="rule-add" onClick={addRule}>{t('settings.addRule')}</button>
          </div>
        </div>
      </div>

      {/* Tier 2: Script-level URL_PATTERNS (read-only) */}
      <div className="rules-section">
        <div className="settings-group">
          <h3 className="settings-group-title">{t('settings.scriptRules')}</h3>
          <div style={{ padding: '12px 16px' }}>
            {scriptLevelRules.length > 0 ? (
              <table className="rules-table">
                <thead>
                  <tr>
                    <th>{t('settings.urlPattern')}</th>
                    <th>{t('settings.script')}</th>
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
                          ? <span className="rule-source-badge">{t('settings.active')}</span>
                          : <span className="rule-source-badge rule-source-badge-off">{t('settings.off')}</span>
                        }
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="rules-empty">{t('settings.noPatterns')}</div>
            )}
            <div className="rules-hint">
              {t('settings.rulesHint')}
            </div>
          </div>
        </div>
      </div>

      <div className="rules-fallback">{t('settings.rulesFallback')}</div>

      <div className="settings-actions">
        <button className="settings-save" onClick={handleSave} disabled={saving}>
          {saving ? t('settings.saving') : saved ? t('settings.saved') : t('settings.saveRules')}
        </button>
      </div>
    </>
  )

  return (
    <div className="settings-page">
      {/* ── Sidebar ── */}
      <aside className="settings-sidebar">
        <h4 className="settings-sidebar-title">{t('settings.title')}</h4>
        <nav className="settings-nav">
          {SECTIONS.map(s => (
            <button
              key={s.key}
              className={`settings-nav-item ${section === s.key ? 'active' : ''}`}
              onClick={() => setSection(s.key)}
            >
              <span className="settings-nav-icon">{s.icon}</span>
              {t(s.label)}
            </button>
          ))}
        </nav>
      </aside>

      {/* ── Panel ── */}
      <div className={`settings-panel ${section === 'scripts' ? 'settings-panel-wide' : ''}`}>
        <div className="settings-panel-header">
          <h1 className="settings-panel-title">{t(meta.title)}</h1>
          <p className="settings-panel-desc">{t(meta.desc)}</p>
        </div>

        {section === 'general' && renderConfigSection('general')}
        {section === 'agent' && renderConfigSection('agent')}
        {section === 'timeouts' && renderConfigSection('timeouts')}
        {section === 'scripts' && renderScriptsSection()}
        {section === 'rules' && renderRulesSection()}
      </div>
    </div>
  )
}
