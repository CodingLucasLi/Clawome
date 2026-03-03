import { useState } from 'react'

export default function AgentThinking({ message }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="chat-msg chat-msg-agent">
      <div
        className="chat-thinking"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="chat-thinking-dot" />
        <span className="chat-thinking-text">
          {expanded ? message.content : (message.content.slice(0, 60) + (message.content.length > 60 ? '...' : ''))}
        </span>
        {message.content.length > 60 && (
          <span className="chat-thinking-toggle">{expanded ? '\u25B2' : '\u25BC'}</span>
        )}
      </div>
    </div>
  )
}
