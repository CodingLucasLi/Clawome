import { useState, useEffect, useRef } from 'react'

export default function DecisionCard({ decision, onDecision }) {
  const { id, question, options, default_key, timeout_seconds, status } = decision
  const [timeLeft, setTimeLeft] = useState(timeout_seconds)
  const [selected, setSelected] = useState(null)
  const timerRef = useRef(null)

  const isActive = status === 'pending' && !selected
  const hasTimer = timeout_seconds > 0 && timeout_seconds < 30

  useEffect(() => {
    if (!isActive || !hasTimer) return

    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current)
          onDecision(id, default_key)
          setSelected(default_key)
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timerRef.current)
  }, [isActive, hasTimer, id, default_key, onDecision])

  const handleSelect = (key) => {
    if (!isActive) return
    clearInterval(timerRef.current)
    setSelected(key)
    onDecision(id, key)
  }

  const resolvedKey = selected || decision.selected_key

  return (
    <div className="chat-msg chat-msg-agent">
      <div className={`chat-decision ${isActive ? 'chat-decision-active' : 'chat-decision-resolved'}`}>
        <div className="chat-decision-question">{question}</div>

        {isActive && hasTimer && (
          <div className="chat-decision-timer">
            <div
              className="chat-decision-timer-fill"
              style={{ width: `${(timeLeft / timeout_seconds) * 100}%` }}
            />
            <span className="chat-decision-timer-text">{timeLeft}s</span>
          </div>
        )}

        <div className="chat-decision-options">
          {(options || []).map(opt => (
            <button
              key={opt.key}
              className={`chat-decision-opt
                ${opt.key === default_key ? 'chat-decision-default' : ''}
                ${opt.key === resolvedKey ? 'chat-decision-selected' : ''}
                ${!isActive ? 'chat-decision-disabled' : ''}`}
              onClick={() => handleSelect(opt.key)}
              disabled={!isActive}
            >
              <span className="chat-decision-key">{opt.key}</span>
              <span className="chat-decision-label">{opt.label}</span>
              {opt.key === default_key && isActive && hasTimer && (
                <span className="chat-decision-badge">default</span>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
