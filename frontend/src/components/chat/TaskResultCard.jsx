import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { cleanMarkdown, MD_COMPONENTS } from './ResultMessage'

const AVATAR = '/clawome.png'

export default function TaskResultCard({ message }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(true)
  const { taskResult } = message
  if (!taskResult) return null

  const { status, description, subtasks = [], elapsed_seconds = 0, llm_usage = {} } = taskResult
  const isSuccess = status === 'completed'

  const formatTime = (s) => {
    if (s < 60) return `${s}s`
    return `${Math.floor(s / 60)}m ${s % 60}s`
  }

  return (
    <div className="chat-msg chat-msg-agent chat-msg-fade-in">
      <img className="chat-agent-avatar" src={AVATAR} alt="" />
      <div className="chat-msg-bubble chat-bubble-agent">
        {/* Header */}
        <div
          className="task-result-header"
          onClick={() => setExpanded(!expanded)}
          style={{ cursor: 'pointer' }}
        >
          <span className={`task-result-badge ${isSuccess ? 'task-result-success' : 'task-result-failed'}`}>
            {isSuccess ? '✓' : '✗'} {status === 'completed' ? t('taskResult.completed', 'Task Completed') : status === 'failed' ? t('taskResult.failed', 'Task Failed') : t('taskResult.cancelled', 'Cancelled')}
          </span>
          <span className="task-result-desc">{description}</span>
          <span className="task-result-toggle">{expanded ? '▾' : '▸'}</span>
        </div>

        {/* Stats bar */}
        <div className="task-result-stats">
          <span>⏱ {formatTime(elapsed_seconds)}</span>
          <span>📋 {t('taskResult.subtasks', '{{count}} subtasks', { count: subtasks.length })}</span>
          {llm_usage.calls > 0 && <span>🧠 {t('taskResult.llmCalls', '{{count}} LLM calls', { count: llm_usage.calls })}</span>}
          {llm_usage.total_tokens > 0 && <span>📊 {(llm_usage.total_tokens / 1000).toFixed(1)}K tokens</span>}
        </div>

        {/* Expandable result content */}
        {expanded && message.content && (
          <div className="task-result-content chat-markdown">
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkBreaks]}
              components={MD_COMPONENTS}
            >
              {cleanMarkdown(message.content)}
            </ReactMarkdown>
          </div>
        )}

        {/* Subtask summary */}
        {expanded && subtasks.length > 0 && (
          <div className="task-result-subtasks">
            {subtasks.map((st, i) => (
              <div key={i} className="task-result-subtask-row">
                <span className={`task-result-subtask-icon ${st.status === 'completed' ? 'completed' : st.status === 'failed' ? 'failed' : ''}`}>
                  {st.status === 'completed' ? '✓' : st.status === 'failed' ? '✗' : '○'}
                </span>
                <span className="task-result-subtask-goal">{st.goal}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
