import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import ChatMessageList from '../components/chat/ChatMessageList'
import ChatInput from '../components/chat/ChatInput'
import SessionList from '../components/chat/SessionList'
import TaskInfoPanel from '../components/chat/TaskInfoPanel'
import { sendChatMessage, stopChat, resetChat, listChatSessions, restoreChatSession, deleteChatSession, getTabs } from '../api'
import './ChatPage.css'

export default function ChatPage() {
  const { t } = useTranslation()
  const [messages, setMessages] = useState([])
  const [processing, setProcessing] = useState(false)
  const [activeTool, setActiveTool] = useState(null)  // { name, input } or null
  const [sessionId, setSessionId] = useState(null)
  const [tasks, setTasks] = useState([])
  const [sessions, setSessions] = useState([])
  const [browserTabs, setBrowserTabs] = useState([])
  const [activeTask, setActiveTask] = useState(null)     // {task_id, description, subtasks}
  const [taskDetail, setTaskDetail] = useState(null)      // Full task status for right panel
  const [toolHistory, setToolHistory] = useState([])       // Recent tool calls for activity feed
  const esRef = useRef(null)

  // ── Sessions list ─────────────────────────────────────────────────
  const refreshSessions = useCallback(async () => {
    try {
      const res = await listChatSessions()
      setSessions(res.data.sessions || [])
    } catch { /* ignore */ }
  }, [])

  // ── Browser tabs (direct API, no LLM) ─────────────────────────────
  const refreshBrowserTabs = useCallback(async () => {
    try {
      const res = await getTabs()
      setBrowserTabs(res.data.tabs || [])
    } catch { /* ignore — browser may not be running */ }
  }, [])

  // ── SSE connection ────────────────────────────────────────────────
  useEffect(() => {
    const es = new EventSource('/api/chat/stream')
    esRef.current = es

    // Initial state on connect
    es.addEventListener('init', (e) => {
      const data = JSON.parse(e.data)
      if (data.session_id) {
        setSessionId(data.session_id)
        setMessages(data.messages || [])
        setProcessing(data.status === 'processing')
        if (data.tasks) setTasks(data.tasks)
      }
    })

    // Agent starts a new message
    es.addEventListener('msg_start', (e) => {
      const data = JSON.parse(e.data)
      setMessages(prev => [...prev, {
        id: data.id,
        role: data.role,
        type: data.type,
        content: '',
        timestamp: data.timestamp,
      }])
    })

    // Streaming token — update message content in place
    es.addEventListener('token', (e) => {
      const { id, content } = JSON.parse(e.data)
      setActiveTool(null)
      setMessages(prev => prev.map(m =>
        m.id === id ? { ...m, content } : m
      ))
    })

    // Message type change (thinking/result segmentation)
    es.addEventListener('msg_type', (e) => {
      const { id, type } = JSON.parse(e.data)
      setMessages(prev => prev.map(m =>
        m.id === id ? { ...m, type } : m
      ))
    })

    // Processing complete
    es.addEventListener('done', () => {
      setProcessing(false)
      setActiveTool(null)
      refreshSessions()
    })

    // Error from agent
    es.addEventListener('agent_error', (e) => {
      const { id, content } = JSON.parse(e.data)
      setMessages(prev => [...prev, {
        id,
        role: 'agent',
        type: 'error',
        content,
        timestamp: Date.now() / 1000,
      }])
      setProcessing(false)
    })

    // Processing started
    es.addEventListener('processing', (e) => {
      const { session_id } = JSON.parse(e.data)
      if (session_id) setSessionId(session_id)
      setProcessing(true)
    })

    // Tool call in progress (browser action, etc.)
    es.addEventListener('tool_start', (e) => {
      const { tool, input, description } = JSON.parse(e.data)
      setActiveTool({ name: tool || 'tool', input: input || {}, description: description || '' })
      setToolHistory(prev => [{
        name: tool || 'tool',
        input: input || {},
        description: description || '',
        timestamp: Date.now() / 1000,
      }, ...prev].slice(0, 10))
    })

    // Tool result returned — also refresh browser tabs
    es.addEventListener('tool_end', (e) => {
      const data = JSON.parse(e.data)
      setActiveTool(null)
      setToolHistory(prev => {
        if (prev.length === 0) return prev
        const updated = [...prev]
        updated[0] = { ...updated[0], done: true, outputPreview: data.output_preview }
        return updated
      })
      refreshBrowserTabs()
    })

    // Decision card from agent (offer_choices tool)
    es.addEventListener('decision', (e) => {
      const data = JSON.parse(e.data)
      if (data.decision) {
        setMessages(prev => [...prev, {
          id: data.id || `decision_${Date.now()}`,
          role: 'agent',
          type: 'decision',
          decision: data.decision,
          timestamp: Date.now() / 1000,
        }])
      }
    })

    // ── Task events (from create_task tool) ──────────────────────

    // Task started
    es.addEventListener('task_started', (e) => {
      const data = JSON.parse(e.data)
      setActiveTask({
        task_id: data.task_id,
        description: data.description,
        subtasks: data.subtasks || [],
      })
      // Insert progress card in chat
      setMessages(prev => [...prev, {
        id: `task_started_${data.task_id}`,
        role: 'agent',
        type: 'task_progress',
        content: data.description,
        task_id: data.task_id,
        timestamp: Date.now() / 1000,
      }])
    })

    // Task progress (subtask transitions)
    es.addEventListener('task_progress', (e) => {
      const data = JSON.parse(e.data)
      // Update the existing task_progress card or add new info
      setTaskDetail(prev => prev ? { ...prev, ...data } : data)
    })

    // Task status update (full snapshot, every 2s)
    es.addEventListener('task_status_update', (e) => {
      const data = JSON.parse(e.data)
      setTaskDetail(data)
    })

    // Task completed/failed
    es.addEventListener('task_result', (e) => {
      const data = JSON.parse(e.data)
      setActiveTask(null)
      setTaskDetail(null)
      // Insert result card in chat
      setMessages(prev => [...prev, {
        id: `task_result_${data.task_id}`,
        role: 'agent',
        type: 'task_result',
        content: data.final_result || '',
        taskResult: data,
        timestamp: Date.now() / 1000,
      }])
    })

    // Task injection confirmation
    es.addEventListener('task_injection', (e) => {
      const data = JSON.parse(e.data)
      setMessages(prev => [...prev, {
        id: `injection_${Date.now()}`,
        role: 'system',
        type: 'text',
        content: t('chat.injectionMessage', 'Command sent to task: "{{content}}"', { content: data.content }),
        timestamp: Date.now() / 1000,
      }])
    })

    // Session restored (switching to a different session)
    es.addEventListener('session_restored', (e) => {
      const data = JSON.parse(e.data)
      setSessionId(data.session_id)
      setMessages(data.messages || [])
      setProcessing(false)
      setActiveTool(null)
      setTasks(data.tasks || [])
      setActiveTask(null)
      setTaskDetail(null)
      setToolHistory([])
      refreshSessions()
    })

    // Session reset
    es.addEventListener('reset', () => {
      setMessages([])
      setProcessing(false)
      setSessionId(null)
      setTasks([])
      setActiveTask(null)
      setTaskDetail(null)
      setToolHistory([])
    })

    // Load sessions + browser state on mount
    refreshSessions()
    refreshBrowserTabs()

    return () => {
      es.close()
      esRef.current = null
    }
  }, [refreshSessions, refreshBrowserTabs])

  // ── Handlers ──────────────────────────────────────────────────────
  const handleSend = async (text) => {
    // Add user message locally for instant feedback
    const userMsg = {
      id: 'temp_' + Date.now(),
      role: 'user',
      type: 'text',
      content: text,
      timestamp: Date.now() / 1000,
    }
    setMessages(prev => [...prev, userMsg])

    try {
      await sendChatMessage(text)
      // SSE will push msg_start, token, done events
    } catch (e) {
      setMessages(prev => [...prev, {
        id: 'err_' + Date.now(),
        role: 'agent',
        type: 'error',
        content: e.response?.data?.message || e.message,
        timestamp: Date.now() / 1000,
      }])
    }
  }

  const handleDecision = (decisionId, selectedKey) => {
    // Find the decision message and get the selected option label
    const decisionMsg = messages.find(m => m.decision?.id === decisionId)
    if (!decisionMsg) return
    const option = decisionMsg.decision.options.find(o => o.key === selectedKey)
    const text = option?.label || selectedKey
    // Mark decision as answered
    setMessages(prev => prev.map(m =>
      m.decision?.id === decisionId
        ? { ...m, decision: { ...m.decision, status: 'answered', selected_key: selectedKey } }
        : m
    ))
    // Send the selected option as the next user message
    handleSend(text)
  }

  const handleStop = async () => {
    // Immediate UI update — don't wait for backend response
    setProcessing(false)
    setActiveTask(null)
    setActiveTool(null)
    try {
      await stopChat()
    } catch (e) {
      console.error('Failed to stop:', e)
    }
  }

  const handleNewChat = async () => {
    await resetChat()
    // SSE 'reset' event will clear state
    await refreshSessions()
  }

  const handleSelectSession = async (session) => {
    if (session.id === sessionId) return
    try {
      await restoreChatSession(session.id)
      // SSE 'session_restored' event will update state
    } catch (e) {
      console.error('Failed to restore session:', e)
    }
  }

  const handleDeleteSession = async (sid) => {
    try {
      await deleteChatSession(sid)
      // If deleting current session, reset to new chat
      if (sid === sessionId) {
        setMessages([])
        setSessionId(null)
        setProcessing(false)
        setActiveTask(null)
      }
      await refreshSessions()
    } catch (e) {
      console.error('Failed to delete session:', e)
    }
  }

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className="chat-page-three">
      {/* Left: session list */}
      <SessionList
        sessions={sessions}
        currentId={sessionId}
        onNew={handleNewChat}
        onSelect={handleSelectSession}
        onDelete={handleDeleteSession}
      />

      {/* Middle: conversation */}
      <div className="chat-main">
        <ChatMessageList
          messages={messages}
          processing={processing}
          activeTool={activeTool}
          onDecision={handleDecision}
        />
        <ChatInput
          onSend={handleSend}
          onStop={handleStop}
          disabled={processing && !activeTask}
          processing={processing}
          activeTask={activeTask}
        />
      </div>

      {/* Right: task info */}
      <TaskInfoPanel
        tasks={tasks}
        sessionId={sessionId}
        processing={processing}
        browserTabs={browserTabs}
        activeTask={activeTask}
        taskDetail={taskDetail}
        activeTool={activeTool}
        toolHistory={toolHistory}
        lastUserMessage={messages.filter(m => m.role === 'user').at(-1)?.content}
      />
    </div>
  )
}
