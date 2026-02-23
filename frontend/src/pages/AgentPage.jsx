import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { startAgent, getAgentStatus, stopAgent } from '../api'
import './AgentPage.css'

/** Turn plain text with URLs into React nodes with clickable links. */
function Linkify({ children }) {
  if (typeof children !== 'string') return children
  const URL_RE = /(https?:\/\/[^\s),，。）]+)/g
  const parts = children.split(URL_RE)
  if (parts.length === 1) return children
  return parts.map((part, i) =>
    URL_RE.test(part)
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

const ACTION_LABELS = {
  goto: 'goto',
  click: 'click',
  input: 'input',
  select: 'select',
  get_text: 'text',
  switch_tab: 'tab',
  wait: 'wait',
  done: 'done',
  llm: 'thinking',
}

const LLM_NODE_LABELS = {
  step_exec: 'Deciding next action',
  main_planner: 'Planning task',
  planner: 'Planning task',
  evaluate: 'Evaluating progress',
  final_check: 'Reviewing results',
  replan: 'Replanning',
  supervisor: 'Supervising execution',
  global_check: 'Progress check',
  page_doctor: 'Diagnosing page',
}

/* Map error_code to a helpful hint shown below the error message */
const ERROR_HINTS = {
  config_missing: { text: 'Go to Settings > Agent to configure', link: '/settings' },
  auth_error:     { text: 'Check your API Key in Settings > Agent', link: '/settings' },
  config_error:   { text: 'Check API Base URL in Settings > Agent', link: '/settings' },
  model_error:    { text: 'Check Model Name in Settings > Agent', link: '/settings' },
  connection_error: { text: 'Check API Base URL in Settings > Agent', link: '/settings' },
  rate_limit:     { text: 'Please wait a moment and try again', link: null },
  browser_error:  { text: 'Make sure the backend server is running', link: null },
  task_running:   { text: 'Wait for the current task to finish or stop it', link: null },
}

function stepDescription(step) {
  const action = step.action || {}
  const type = action.action || '?'
  const reason = action.reason || ''
  if (type === 'llm') {
    const node = action.node || ''
    const label = LLM_NODE_LABELS[node] || node
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
  const [expanded, setExpanded] = useState(defaultExpanded)

  // Auto-expand when running, auto-collapse when done
  useEffect(() => {
    setExpanded(defaultExpanded)
  }, [defaultExpanded])

  const hasSteps = steps.length > 0

  return (
    <div className={`agent-card agent-card-${st.status}`}>
      <div className="agent-card-header" onClick={() => hasSteps && setExpanded(e => !e)} style={hasSteps ? { cursor: 'pointer' } : undefined}>
        <span className="agent-step-num">{STATUS_ICONS[st.status] || '?'}</span>
        <span className="agent-card-step">Step {st.step}</span>
        <span className="agent-card-goal">{st.goal}</span>
        <span className={`agent-tag agent-tag-${st.status}`}>{st.status}</span>
        {hasSteps && (
          <span className="agent-card-toggle">{expanded ? '\u25BC' : '\u25B6'} {steps.length}</span>
        )}
      </div>
      {st.result && (
        <div className="agent-card-result">
          {st.result.length > 100 ? st.result.slice(0, 100) + '…' : st.result}
        </div>
      )}
      {expanded && hasSteps && (
        <div className="agent-steps">
          {steps.map(step => {
            const isLLM = step.action?.action === 'llm'
            const isRunning = step.status === 'running'

            /* LLM steps: lightweight label row (no index, no badge) */
            if (isLLM) {
              return (
                <div
                  key={step.index}
                  className={`agent-step-llm-label${isRunning ? ' agent-step-llm-active' : ''}`}
                >
                  <span className="agent-step-llm-label-text">{stepDescription(step)}</span>
                </div>
              )
            }

            /* Browser action steps: normal rendering */
            return (
              <div
                key={step.index}
                className={`agent-step-row${step.status === 'failed' ? ' agent-step-failed' : ''}`}
              >
                <span className="agent-step-idx">{step.index}</span>
                <span className={`agent-step-action agent-step-action-${step.action?.action || 'unknown'}`}>
                  {ACTION_LABELS[step.action?.action] || step.action?.action || '?'}
                </span>
                <span className="agent-step-desc">{stepDescription(step)}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

const BROWSER_ACTION_LABELS = {
  goto: 'Navigating',
  click: 'Clicking',
  input: 'Typing',
  select: 'Selecting',
  get_text: 'Reading text',
  switch_tab: 'Switching tab',
  wait: 'Waiting',
  done: 'Finishing',
}

function getCurrentActivity(steps, taskStatus) {
  if (!taskStatus || !['starting', 'running'].includes(taskStatus)) return null
  // Scan from end to find the latest running step
  for (let i = steps.length - 1; i >= 0; i--) {
    const s = steps[i]
    if (s.status !== 'running') continue
    const act = s.action?.action
    if (act === 'llm') {
      const node = s.action?.node || ''
      return LLM_NODE_LABELS[node] || 'Thinking'
    }
    return BROWSER_ACTION_LABELS[act] || 'Working'
  }
  // No running step found but task is running
  if (taskStatus === 'starting') return 'Starting up'
  return 'Processing'
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
            <span className="agent-global-label">{stepDescription(step)}</span>
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
  if (!message) return null
  const hint = ERROR_HINTS[errorCode]

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
  const [task, setTask] = useState('')
  const [status, setStatus] = useState(null)
  const [polling, setPolling] = useState(false)
  const [startError, setStartError] = useState(null) // { message, error_code }
  const intervalRef = useRef(null)

  const poll = useCallback(async () => {
    try {
      const res = await getAgentStatus()
      const data = res.data
      setStatus(data)
      // Stop polling when done
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
      poll() // one final poll
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

  // Cleanup on unmount + check for existing running task
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
  const currentActivity = getCurrentActivity(allSteps, status?.status)

  // Group steps by subtask_step
  const stepsBySubtask = {}
  for (const step of allSteps) {
    const key = step.subtask_step
    if (!stepsBySubtask[key]) stepsBySubtask[key] = []
    stepsBySubtask[key].push(step)
  }

  return (
    <div className="agent-page">
      <h1>Task Agent</h1>
      <p className="agent-desc">
        Enter a task description. The AI agent will autonomously browse the web,
        plan subtasks, execute actions, and deliver results.
      </p>

      {/* Task Input */}
      <div className="agent-input-section">
        <textarea
          className="agent-textarea"
          placeholder="e.g. Search for NYU MS Electrical Engineering admission requirements"
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
            {polling ? 'Running...' : 'Start Task'}
          </button>
          {polling && (
            <button className="agent-stop-btn" onClick={handleStop}>
              Stop
            </button>
          )}
        </div>
        {/* Start-time error (config missing, etc.) */}
        {startError && (
          <ErrorDisplay message={startError.message} errorCode={startError.error_code} />
        )}
      </div>

      {/* Status Display */}
      {status && status.status !== 'idle' && (
        <div className="agent-result-section">
          {/* Overall Status Badge */}
          <div className="agent-status-row">
            <span className={`agent-badge agent-badge-${status.status}`}>
              {status.status?.toUpperCase()}
            </span>
            {total > 0 && (
              <span className="agent-progress-text">
                {completed} / {total} subtasks
              </span>
            )}
          </div>

          {/* Live Activity Indicator */}
          <ActivityLine activity={currentActivity} />

          {/* Progress Bar */}
          {total > 0 && (
            <div className="agent-progress-bar">
              <div className="agent-progress-fill" style={{ width: `${pct}%` }} />
            </div>
          )}

          {/* Global Steps (planner, evaluate, etc.) before subtasks */}
          {(stepsBySubtask[0] || []).length > 0 && (
            <GlobalSteps steps={stepsBySubtask[0]} />
          )}

          {/* Subtask Cards — only the last subtask auto-expands */}
          {subtasks.map((st, i) => (
            <SubtaskCard
              key={st.step}
              st={st}
              steps={stepsBySubtask[st.step] || []}
              defaultExpanded={i === subtasks.length - 1 && st.status === 'running'}
            />
          ))}

          {/* Final Result */}
          {status.final_result && (
            <div className="agent-final">
              <h3>Result</h3>
              <div className="agent-final-text"><Linkify>{status.final_result}</Linkify></div>
            </div>
          )}

          {/* Stats: elapsed time + LLM usage */}
          {(status.elapsed_seconds > 0 || (status.llm_usage && status.llm_usage.calls > 0)) && (
            <div className="agent-stats">
              {status.elapsed_seconds > 0 && (
                <div className="agent-stats-row">
                  <span className="agent-stats-label">用时</span>
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
                    {status.llm_usage.calls}次
                    <span className="agent-stats-detail">
                      {' '}{(status.llm_usage.total_tokens || 0).toLocaleString()} tokens (↑{(status.llm_usage.input_tokens || 0).toLocaleString()} ↓{(status.llm_usage.output_tokens || 0).toLocaleString()})
                    </span>
                  </span>
                </div>
                <div className="agent-stats-row">
                  <span className="agent-stats-label">费用</span>
                  <span className="agent-stats-value">¥{status.llm_usage.cost?.toFixed(4)}</span>
                </div>
              </>)}
            </div>
          )}

          {/* Runtime error (failed task) */}
          {status.status === 'failed' && status.error && (
            <ErrorDisplay message={status.error} errorCode={status.error_code} />
          )}

          {/* Cancelled notice */}
          {status.status === 'cancelled' && status.error && (
            <div className="agent-cancelled-box">{status.error}</div>
          )}
        </div>
      )}
    </div>
  )
}
