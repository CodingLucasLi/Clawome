import { useTranslation } from 'react-i18next'

function formatTime(ts) {
  if (!ts) return ''
  // ts can be "YYYY-MM-DD HH:MM:SS" string or Unix timestamp number
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts.replace(' ', 'T'))
  const now = new Date()
  const diffMs = now - d
  const diffDays = Math.floor(diffMs / 86400000)
  const hhmm = d.toTimeString().slice(0, 5)
  if (diffDays === 0) return hhmm
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return d.toISOString().slice(0, 10)
}

export default function SessionList({ sessions, currentId, onNew, onSelect, onDelete }) {
  const { t } = useTranslation()

  const handleDelete = (e, sessionId) => {
    e.stopPropagation()
    if (onDelete) onDelete(sessionId)
  }

  return (
    <div className="chat-sessions-panel">
      <div className="chat-sessions-header">
        <span className="chat-sessions-title">{t('chat.conversations', 'Conversations')}</span>
        <button className="chat-new-session-btn" onClick={onNew} title={t('chat.newChat', 'New Chat')}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
          </svg>
        </button>
      </div>

      <div className="chat-sessions-list">
        {sessions.length === 0 && (
          <div className="chat-sessions-empty">
            {t('chat.noSessions', 'No past conversations')}
          </div>
        )}
        {sessions.map(s => (
          <div
            key={s.id}
            className={`chat-session-item${s.id === currentId ? ' chat-session-active' : ''}`}
            onClick={() => onSelect(s)}
            role="button"
            tabIndex={0}
          >
            <div className="chat-session-preview">
              {s.preview || t('chat.emptySession', '(empty)')}
            </div>
            <div className="chat-session-meta">
              <span className="chat-session-count">
                {s.message_count} msg{s.message_count !== 1 ? 's' : ''}
                {s.task_count > 0 && ` · ${s.task_count} task${s.task_count !== 1 ? 's' : ''}`}
              </span>
              <span className="chat-session-meta-right">
                <span className="chat-session-time">{formatTime(s.updated_at || s.created_at)}</span>
                <button
                  className="chat-session-delete-btn"
                  onClick={(e) => handleDelete(e, s.id)}
                  title={t('delete', 'Delete')}
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M2 3h8M4.5 3V2a.5.5 0 0 1 .5-.5h2a.5.5 0 0 1 .5.5v1M5 5.5v3M7 5.5v3M3 3l.5 6.5a1 1 0 0 0 1 .9h3a1 1 0 0 0 1-.9L9 3" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
