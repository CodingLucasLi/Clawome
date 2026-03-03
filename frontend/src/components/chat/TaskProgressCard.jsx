import { useState } from 'react'

const STATUS_ICON = {
  pending: '-',
  running: '>',
  completed: '+',
  failed: 'x',
  cancelled: '!',
}

const STATUS_COLOR = {
  pending: '#94a3b8',
  running: '#E8663C',
  completed: '#22c55e',
  failed: '#ef4444',
  cancelled: '#94a3b8',
}

export default function TaskProgressCard({ message }) {
  const [expanded, setExpanded] = useState(false)
  const taskRef = message.task_ref
  if (!taskRef) return null

  const isRunning = taskRef.status === 'running'

  return (
    <div className="chat-msg chat-msg-agent">
      <div
        className="chat-task-card"
        style={{ borderLeftColor: STATUS_COLOR[taskRef.status] || '#94a3b8' }}
      >
        <div className="chat-task-header" onClick={() => setExpanded(e => !e)}>
          <span className={`chat-task-icon${isRunning ? ' chat-task-icon-running' : ''}`}>
            {STATUS_ICON[taskRef.status] || '?'}
          </span>
          <span className="chat-task-desc">
            Task {taskRef.task_index}: {taskRef.description}
          </span>
          <span className={`chat-task-status chat-task-status-${taskRef.status}`}>
            {taskRef.status}
          </span>
          {taskRef.result && (
            <span className="chat-task-toggle">{expanded ? '\u25BC' : '\u25B6'}</span>
          )}
        </div>

        {isRunning && taskRef.llm_usage && taskRef.llm_usage.calls > 0 && (
          <div className="chat-task-stats">
            LLM: {taskRef.llm_usage.calls} calls, {(taskRef.llm_usage.total_tokens || 0).toLocaleString()} tokens
          </div>
        )}

        {expanded && taskRef.result && (
          <div className="chat-task-result">
            {taskRef.result.slice(0, 500)}{taskRef.result.length > 500 ? '...' : ''}
          </div>
        )}
      </div>
    </div>
  )
}
