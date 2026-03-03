import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'

/**
 * Normalize LLM markdown output:
 *  1. HTML <br> tags → plain newlines (react-markdown doesn't render raw HTML)
 *  2. • / ・/ · bullet chars (Qwen-style sub-items) → markdown "- " list markers
 *     so they render as real nested lists instead of <br>-separated plain text
 */
export function cleanMarkdown(text) {
  if (!text) return ''
  return text
    .trim()
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/^(\s*)[•·・▪▸➢]\s*/gm, '$1- ')
}

// Strip <p> wrappers inside <li> — defensive fix for loose list rendering
export const MD_COMPONENTS = {
  li({ children, ...props }) {
    const flat = Array.isArray(children)
      ? children.map(c => (c?.type === 'p' ? c.props.children : c))
      : (children?.type === 'p' ? children.props.children : children)
    return <li {...props}>{flat}</li>
  },
}

export default function ResultMessage({ message }) {
  return (
    <div className="chat-msg chat-msg-agent">
      <img className="chat-agent-avatar" src="/clawome.png" alt="" />
      <div className="chat-msg-bubble chat-bubble-agent chat-result-bubble">
        <div className="chat-markdown">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkBreaks]}
            components={MD_COMPONENTS}
          >
            {cleanMarkdown(message.content)}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
