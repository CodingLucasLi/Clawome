import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { cleanMarkdown, MD_COMPONENTS } from './ResultMessage'
import { useTranslation } from 'react-i18next'
import UserMessage from './UserMessage'
import AgentThinking from './AgentThinking'
import ResultMessage from './ResultMessage'
import TaskProgressCard from './TaskProgressCard'
import TaskResultCard from './TaskResultCard'
import DecisionCard from './DecisionCard'

const AVATAR = '/clawome.png'

/* Tool display labels & icons */
const TOOL_LABELS = {
  open_page:      { icon: '🌐', label: (i) => `Opening ${_short(i?.url)}` },
  read_page:      { icon: '📄', label: () => 'Reading page…' },
  click_element:  { icon: '👆', label: (i, d) => d ? `Clicking ${d}` : `Clicking element ${i?.node_id || ''}` },
  type_input:     { icon: '⌨️', label: (i, d) => d ? `Typing in ${d}` : `Typing into ${i?.node_id || ''}` },
  extract_text:   { icon: '📋', label: (i, d) => d ? `Reading ${d}` : `Extracting text ${i?.node_id || ''}` },
  get_tabs:       { icon: '📑', label: () => 'Listing tabs…' },
  switch_tab:     { icon: '↗️', label: (i) => `Switching to tab ${i?.tab_id || ''}` },
  go_back:        { icon: '◀️', label: () => 'Going back…' },
  go_forward:     { icon: '▶️', label: () => 'Going forward…' },
  refresh_page:   { icon: '🔄', label: () => 'Refreshing…' },
  scroll_page:    { icon: '📜', label: (i) => `Scrolling ${i?.direction || 'down'}…` },
  select_option:  { icon: '📋', label: (i, d) => d ? `Selecting in ${d}` : `Selecting ${i?.value || ''}…` },
  open_new_tab:   { icon: '➕', label: (i) => `New tab ${_short(i?.url)}` },
  close_tab:      { icon: '✖️', label: () => 'Closing tab…' },
  close_browser:  { icon: '🔒', label: () => 'Closing browser…' },
  create_task:    { icon: '🚀', label: () => `Starting task…` },
}

function _short(url) {
  if (!url) return '…'
  try { return new URL(url).hostname } catch { return url.slice(0, 40) }
}

// Tools that should NOT show an activity indicator
const SILENT_TOOLS = new Set(['offer_choices'])

function getToolDisplay(activeTool) {
  if (!activeTool) return null
  if (SILENT_TOOLS.has(activeTool.name)) return null
  const entry = TOOL_LABELS[activeTool.name]
  if (entry) return { icon: entry.icon, text: entry.label(activeTool.input, activeTool.description) }
  return { icon: '⚙️', text: `${activeTool.name}…` }
}

export default function ChatMessageList({ messages, onDecision, processing, activeTool }) {
  const { t } = useTranslation()
  const endRef = useRef(null)
  const containerRef = useRef(null)

  // Scroll on new messages
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  // Auto-scroll during streaming (throttled)
  useEffect(() => {
    if (!processing) return
    const tick = () => {
      const el = containerRef.current
      if (!el) return
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
      if (nearBottom) endRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
    const id = setInterval(tick, 400)
    return () => clearInterval(id)
  }, [processing])

  // Detect if agent is currently streaming text
  const lastMsg = messages[messages.length - 1]
  const isAgentStreaming = processing && lastMsg?.role === 'agent' &&
    (lastMsg?.type === 'text' || lastMsg?.type === 'result')

  const toolDisplay = getToolDisplay(activeTool)

  return (
    <div className="chat-messages" ref={containerRef}>
      {/* Empty state */}
      {messages.length === 0 && !processing && (
        <div className="chat-empty-state">
          <img className="chat-empty-logo" src={AVATAR} alt="" />
          <p className="chat-empty-title">{t('chat.emptyTitle', 'How can I help you?')}</p>
          <p className="chat-empty-hint">{t('chat.emptyHint', 'Chat freely, or describe a web task')}</p>
        </div>
      )}

      {messages.map((msg, idx) => {
        const isLast = idx === messages.length - 1

        switch (msg.type) {
          case 'text':
            if (msg.role === 'user') return <UserMessage key={msg.id} message={msg} />

            // Empty agent message during streaming → show cursor placeholder
            if (!msg.content) {
              return (
                <div key={msg.id} className="chat-msg chat-msg-agent">
                  <img className="chat-agent-avatar" src={AVATAR} alt="" />
                  <div className="chat-msg-bubble chat-bubble-agent">
                    <span className="chat-bubble-dots"><span /><span /><span /></span>
                  </div>
                </div>
              )
            }

            return (
              <div key={msg.id} className="chat-msg chat-msg-agent chat-msg-fade-in">
                <img className="chat-agent-avatar" src={AVATAR} alt="" />
                <div className="chat-msg-bubble chat-bubble-agent">
                  <div className={`chat-markdown${isLast && isAgentStreaming ? ' chat-streaming' : ''}`}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkBreaks]}
                      components={MD_COMPONENTS}
                    >
                      {cleanMarkdown(msg.content)}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            )

          case 'thinking':
            return <AgentThinking key={msg.id} message={msg} />

          case 'task_progress':
            return <TaskProgressCard key={msg.id} message={msg} />

          case 'task_result':
            return <TaskResultCard key={msg.id} message={msg} />

          case 'decision':
            return msg.decision
              ? <DecisionCard key={msg.id} decision={msg.decision} onDecision={onDecision} />
              : null

          case 'result':
            // Empty result during streaming start → show bouncing dots
            if (!msg.content) {
              return (
                <div key={msg.id} className="chat-msg chat-msg-agent">
                  <img className="chat-agent-avatar" src={AVATAR} alt="" />
                  <div className="chat-msg-bubble chat-bubble-agent">
                    <span className="chat-bubble-dots"><span /><span /><span /></span>
                  </div>
                </div>
              )
            }
            return <ResultMessage key={msg.id} message={msg} />

          case 'error':
            return (
              <div key={msg.id} className="chat-msg chat-msg-agent">
                <img className="chat-agent-avatar" src={AVATAR} alt="" />
                <div className="chat-msg-bubble chat-bubble-error">{msg.content}</div>
              </div>
            )

          default:
            return null
        }
      })}

      {/* Tool activity indicator */}
      {toolDisplay && (
        <div className="chat-msg chat-msg-agent">
          <img className="chat-agent-avatar" src={AVATAR} alt="" />
          <div className="chat-tool-indicator">
            <span className="chat-tool-icon">{toolDisplay.icon}</span>
            <span className="chat-tool-label">{toolDisplay.text}</span>
          </div>
        </div>
      )}

      {/* Typing indicator — only when not streaming and no active tool */}
      {processing && !toolDisplay && !isAgentStreaming && (
        <div className="chat-msg chat-msg-agent">
          <img className="chat-agent-avatar" src={AVATAR} alt="" />
          <div className="chat-typing-indicator">
            <span /><span /><span />
          </div>
        </div>
      )}

      <div ref={endRef} />
    </div>
  )
}
