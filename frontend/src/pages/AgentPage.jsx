import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { startAgent, getAgentStatus, stopAgent } from '../api'
import './AgentPage.css'

/** Turn plain text with URLs into React nodes with clickable links. */
function Linkify({ children }) {
  if (typeof children !== 'string') return children
  const URL_RE = /(https?:\/\/[^\s),，。）]+)/g
  const parts = children.split(URL_RE)
  if (parts.length === 1) return children
  return parts.map((part, i) =>
    /^https?:\/\//.test(part)
      ? <a key={i} href={part} target="_blank" rel="noopener noreferrer" className="agent-link">{part}</a>
      : part
  )
}

const STATUS_ICONS = {
  completed: '+',
  failed: 'x',
  running: '>',
  pending: '-',
}

function useActionLabels() {
  const { t } = useTranslation()
  return useMemo(() => ({
    goto: t('agent.goto'), click: t('agent.click'), input: t('agent.input'),
    select: t('agent.select'), get_text: t('agent.text'), switch_tab: t('agent.tab'),
    wait: t('agent.wait'), done: t('agent.done'), llm: t('agent.thinking'),
  }), [t])
}

function useLlmNodeLabels() {
  const { t } = useTranslation()
  return useMemo(() => ({
    step_exec: t('agent.decidingAction'), main_planner: t('agent.planningTask'),
    planner: t('agent.planningTask'), evaluate: t('agent.evaluatingProgress'),
    final_check: t('agent.reviewingResults'), replan: t('agent.replanning'),
    supervisor: t('agent.supervising'), global_check: t('agent.progressCheck'),
    page_doctor: t('agent.diagnosingPage'),
  }), [t])
}

function useBrowserActionLabels() {
  const { t } = useTranslation()
  return useMemo(() => ({
    goto: t('agent.navigating'), click: t('agent.clicking'), input: t('agent.typing'),
    select: t('agent.selecting'), get_text: t('agent.readingText'),
    switch_tab: t('agent.switchingTab'), wait: t('agent.waiting'), done: t('agent.finishing'),
  }), [t])
}

function useErrorHints() {
  const { t } = useTranslation()
  return useMemo(() => ({
    config_missing: { text: t('agent.configMissing'), link: '/settings' },
    auth_error: { text: t('agent.authError'), link: '/settings' },
    config_error: { text: t('agent.configError'), link: '/settings' },
    model_error: { text: t('agent.modelError'), link: '/settings' },
    connection_error: { text: t('agent.connectionError'), link: '/settings' },
    rate_limit: { text: t('agent.rateLimit'), link: null },
    browser_error: { text: t('agent.browserError'), link: null },
    task_running: { text: t('agent.taskRunning'), link: null },
  }), [t])
}

function stepDescription(step, llmNodeLabels) {
  const action = step.action || {}
  const type = action.action || '?'
  const reason = action.reason || ''
  if (type === 'llm') {
    const node = action.node || ''
    const label = llmNodeLabels[node] || node
    const dur = step.duration_ms
    if (step.status === 'running') return `${label}…`
    if (dur) return `${label} (${dur >= 1000 ? (dur / 1000).toFixed(1) + 's' : dur + 'ms'})`
    return label
  }
  if (type === 'goto') return action.url ? `${action.url.slice(0, 60)}${action.url.length > 60 ? '...' : ''}` : reason
  if (type === 'click') return reason || `node ${action.node_id || '?'}`
  if (type === 'input') return reason || `"${(action.text || '').slice(0, 40)}"`
  if (type === 'done') return action.result ? action.result.slice(0, 80) : reason
  return reason || step.summary?.slice(0, 60) || ''
}

function SubtaskCard({ st, steps, defaultExpanded }) {
  const { t } = useTranslation()
  const actionLabels = useActionLabels()
  const llmNodeLabels = useLlmNodeLabels()
  const [expanded, setExpanded] = useState(defaultExpanded)

  useEffect(() => {
    setExpanded(defaultExpanded)
  }, [defaultExpanded])

  const hasSteps = steps.length > 0

  return (
    <div className={`agent-card agent-card-${st.status}`}>
      <div className="agent-card-header" onClick={() => hasSteps && setExpanded(e => !e)} style={hasSteps ? { cursor: 'pointer' } : undefined}>
        <span className="agent-step-num">{STATUS_ICONS[st.status] || '?'}</span>
        <span className="agent-card-step">{t('agent.step')} {st.step}</span>
        <span className="agent-card-goal">{st.goal}</span>
        <span className={`agent-tag agent-tag-${st.status}`}>{st.status}</span>
        {hasSteps && (
          <span className="agent-card-toggle">{expanded ? '\u25BC' : '\u25B6'} {steps.length}</span>
        )}
      </div>
      {st.result && (
        <div className="agent-card-result">
          <Linkify>{st.result}</Linkify>
        </div>
      )}
      {expanded && hasSteps && (
        <div className="agent-steps">
          {steps.map(step => {
            const isLLM = step.action?.action === 'llm'
            const isRunning = step.status === 'running'

            if (isLLM) {
              return (
                <div
                  key={step.index}
                  className={`agent-step-llm-label${isRunning ? ' agent-step-llm-active' : ''}`}
                >
                  <span className="agent-step-llm-label-text">{stepDescription(step, llmNodeLabels)}</span>
                </div>
              )
            }

            return (
              <div
                key={step.index}
                className={`agent-step-row${step.status === 'failed' ? ' agent-step-failed' : ''}`}
              >
                <span className="agent-step-idx">{step.index}</span>
                <span className={`agent-step-action agent-step-action-${step.action?.action || 'unknown'}`}>
                  {actionLabels[step.action?.action] || step.action?.action || '?'}
                </span>
                <span className="agent-step-desc">{stepDescription(step, llmNodeLabels)}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function getCurrentActivity(steps, taskStatus, browserActionLabels, llmNodeLabels, t) {
  if (!taskStatus || !['starting', 'running'].includes(taskStatus)) return null
  for (let i = steps.length - 1; i >= 0; i--) {
    const s = steps[i]
    if (s.status !== 'running') continue
    const act = s.action?.action
    if (act === 'llm') {
      const node = s.action?.node || ''
      return llmNodeLabels[node] || t('agent.thinking')
    }
    return browserActionLabels[act] || t('agent.processing')
  }
  if (taskStatus === 'starting') return t('agent.startingUp')
  return t('agent.processing')
}

function ActivityLine({ activity }) {
  if (!activity) return null
  return (
    <div className="agent-activity-line">
      <span className="agent-activity-dot" />
      <span className="agent-activity-text">{activity}…</span>
    </div>
  )
}

function GlobalSteps({ steps }) {
  const llmNodeLabels = useLlmNodeLabels()
  if (!steps || steps.length === 0) return null
  return (
    <div className="agent-global-steps">
      {steps.map(step => {
        const isRunning = step.status === 'running'
        return (
          <div
            key={step.index}
            className={`agent-global-step ${isRunning ? 'agent-global-step-active' : ''}`}
          >
            <span className="agent-global-dot" />
            <span className="agent-global-label">{stepDescription(step, llmNodeLabels)}</span>
            {step.started_at && (
              <span className="agent-global-time">{step.started_at}</span>
            )}
          </div>
        )
      })}
    </div>
  )
}

function ErrorDisplay({ message, errorCode }) {
  const errorHints = useErrorHints()
  if (!message) return null
  const hint = errorHints[errorCode]

  return (
    <div className="agent-error-box">
      <div className="agent-error-message">{message}</div>
      {hint && (
        <div className="agent-error-hint">
          {hint.link ? (
            <Link to={hint.link} className="agent-error-link">{hint.text}</Link>
          ) : (
            <span>{hint.text}</span>
          )}
        </div>
      )}
    </div>
  )
}

export default function AgentPage() {
  const { t } = useTranslation()
  const browserActionLabels = useBrowserActionLabels()
  const llmNodeLabels = useLlmNodeLabels()
  const [task, setTask] = useState('')
  const [status, setStatus] = useState(null)
  const [polling, setPolling] = useState(false)
  const [startError, setStartError] = useState(null)
  const intervalRef = useRef(null)

  const poll = useCallback(async () => {
    try {
      const res = await getAgentStatus()
      const data = res.data
      setStatus(data)
      if (data.status && !['starting', 'running'].includes(data.status)) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
        setPolling(false)
      }
    } catch {
      // ignore poll errors
    }
  }, [])

  const handleStart = async () => {
    if (!task.trim()) return
    setStartError(null)
    try {
      const res = await startAgent(task.trim())
      if (res.data.status === 'error') {
        setStartError({ message: res.data.message, error_code: res.data.error_code })
        return
      }
      setStatus({
        task_id: res.data.task_id,
        task: task.trim(),
        status: 'starting',
        subtasks: [],
        error: '',
        error_code: '',
      })
      setPolling(true)
      intervalRef.current = setInterval(poll, 2000)
    } catch (e) {
      const data = e.response?.data
      setStartError({
        message: data?.message || e.message,
        error_code: data?.error_code || 'unknown',
      })
    }
  }

  const handleStop = async () => {
    try {
      await stopAgent()
      clearInterval(intervalRef.current)
      intervalRef.current = null
      setPolling(false)
      poll()
    } catch {
      // ignore
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !polling) {
      e.preventDefault()
      handleStart()
    }
  }

  useEffect(() => {
    getAgentStatus().then(res => {
      const data = res.data
      if (data.status && ['starting', 'running'].includes(data.status)) {
        setStatus(data)
        setTask(data.task || '')
        setPolling(true)
        intervalRef.current = setInterval(poll, 2000)
      } else if (data.status && data.status !== 'idle') {
        setStatus(data)
      }
    }).catch(() => {})

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [poll])

  const subtasks = status?.subtasks || []
  const allSteps = status?.steps || []
  const completed = subtasks.filter(s => s.status === 'completed').length
  const total = subtasks.length
  const pct = total ? Math.round(completed / total * 100) : 0
  const currentActivity = getCurrentActivity(allSteps, status?.status, browserActionLabels, llmNodeLabels, t)

  const stepsBySubtask = {}
  for (const step of allSteps) {
    const key = step.subtask_step
    if (!stepsBySubtask[key]) stepsBySubtask[key] = []
    stepsBySubtask[key].push(step)
  }

  return (
    <div className="agent-page">
      <h1>{t('agent.title')}</h1>
      <p className="agent-desc">{t('agent.desc')}</p>

      {/* Task Input */}
      <div className="agent-input-section">
        <textarea
          className="agent-textarea"
          placeholder={t('agent.placeholder')}
          value={task}
          onChange={e => setTask(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={3}
          disabled={polling}
        />
        <div className="agent-input-actions">
          <button
            className="agent-start-btn"
            onClick={handleStart}
            disabled={polling || !task.trim()}
          >
            {polling ? t('agent.running') : t('agent.startTask')}
          </button>
          {polling && (
            <button className="agent-stop-btn" onClick={handleStop}>
              {t('agent.stop')}
            </button>
          )}
        </div>
        {startError && (
          <ErrorDisplay message={startError.message} errorCode={startError.error_code} />
        )}
      </div>

      {/* Status Display */}
      {status && status.status !== 'idle' && (
        <div className="agent-result-section">
          <div className="agent-status-row">
            <span className={`agent-badge agent-badge-${status.status}`}>
              {status.status?.toUpperCase()}
            </span>
            {total > 0 && (
              <span className="agent-progress-text">
                {completed} / {total} {t('agent.subtasks')}
              </span>
            )}
          </div>

          <ActivityLine activity={currentActivity} />

          {total > 0 && (
            <div className="agent-progress-bar">
              <div className="agent-progress-fill" style={{ width: `${pct}%` }} />
            </div>
          )}

          {(stepsBySubtask[0] || []).length > 0 && (
            <GlobalSteps steps={stepsBySubtask[0]} />
          )}

          {subtasks.map((st, i) => (
            <SubtaskCard
              key={st.step}
              st={st}
              steps={stepsBySubtask[st.step] || []}
              defaultExpanded={i === subtasks.length - 1 && st.status === 'running'}
            />
          ))}

          {status.final_result && (
            <div className="agent-final">
              <h3>{t('agent.result')}</h3>
              <div className="agent-final-text"><Linkify>{status.final_result}</Linkify></div>
            </div>
          )}

          {(status.elapsed_seconds > 0 || (status.llm_usage && status.llm_usage.calls > 0)) && (
            <div className="agent-stats">
              {status.elapsed_seconds > 0 && (
                <div className="agent-stats-row">
                  <span className="agent-stats-label">{t('agent.elapsed')}</span>
                  <span className="agent-stats-value">
                    {status.elapsed_seconds >= 60
                      ? `${Math.floor(status.elapsed_seconds / 60)}m ${status.elapsed_seconds % 60}s`
                      : `${status.elapsed_seconds}s`}
                  </span>
                </div>
              )}
              {status.llm_usage && status.llm_usage.calls > 0 && (<>
                <div className="agent-stats-row">
                  <span className="agent-stats-label">LLM</span>
                  <span className="agent-stats-value">
                    {status.llm_usage.calls}{t('agent.calls')}
                    <span className="agent-stats-detail">
                      {' '}{(status.llm_usage.total_tokens || 0).toLocaleString()} tokens (↑{(status.llm_usage.input_tokens || 0).toLocaleString()} ↓{(status.llm_usage.output_tokens || 0).toLocaleString()})
                    </span>
                  </span>
                </div>
                <div className="agent-stats-row">
                  <span className="agent-stats-label">{t('agent.cost')}</span>
                  <span className="agent-stats-value">¥{status.llm_usage.cost?.toFixed(4)}</span>
                </div>
              </>)}
            </div>
          )}

          {status.status === 'failed' && status.error && (
            <ErrorDisplay message={status.error} errorCode={status.error_code} />
          )}

          {status.status === 'cancelled' && status.error && (
            <div className="agent-cancelled-box">{status.error}</div>
          )}
        </div>
      )}
    </div>
  )
}
