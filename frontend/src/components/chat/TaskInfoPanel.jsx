import { useTranslation } from 'react-i18next'

const STATUS_ICONS = {
  pending:   { icon: '○', cls: 'tip-status-pending' },
  running:   { icon: '◉', cls: 'tip-status-running' },
  completed: { icon: '✓', cls: 'tip-status-done' },
  failed:    { icon: '✗', cls: 'tip-status-failed' },
  cancelled: { icon: '—', cls: 'tip-status-failed' },
}

const TOOL_ICONS = {
  open_page: '🌐', click_element: '👆', type_input: '⌨️',
  scroll_page: '📜', read_page: '📖', extract_text: '📋',
  go_back: '⬅️', go_forward: '➡️', refresh_page: '🔄',
  get_tabs: '📑', switch_tab: '🔀', close_tab: '✖️',
  open_new_tab: '➕', close_browser: '🚫',
  select_option: '☑️', offer_choices: '🗳️', create_task: '📋',
}

function _hostname(url) {
  try { return new URL(url).hostname } catch { return url?.slice(0, 30) || '' }
}

function _formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function _toolSummary(name, input, description) {
  if (!input) return description || ''
  // For node-based tools, prefer backend-enriched description (element label from DOM)
  if (description && name !== 'open_page' && name !== 'type_input' && name !== 'create_task') {
    return description
  }
  if (name === 'open_page') return input.url ? _hostname(input.url) : ''
  if (name === 'click_element') return description || (input.node_id ? `node ${input.node_id}` : '')
  if (name === 'type_input') {
    const text = input.text || ''
    const target = description ? ` → ${description}` : ''
    return text ? `"${text.slice(0, 20)}${text.length > 20 ? '…' : ''}"${target}` : ''
  }
  if (name === 'scroll_page') return input.direction || ''
  if (name === 'extract_text') return description || (input.node_id ? `node ${input.node_id}` : '')
  if (name === 'select_option') return description || (input.value ? `"${input.value}"` : '')
  if (name === 'create_task') return input.description ? input.description.slice(0, 30) : ''
  return description || ''
}

// ── User Request Card ─────────────────────────────────────────────

function UserRequestCard({ content, t }) {
  if (!content) return null
  return (
    <>
      <div className="tip-section-label">{t('taskInfo.currentRequest', 'Current Request')}</div>
      <div className="tip-user-request">{content}</div>
    </>
  )
}

// ── Activity Feed ─────────────────────────────────────────────────

function ActivityItem({ item, isActive }) {
  const icon = TOOL_ICONS[item.name] || '🔧'
  const summary = _toolSummary(item.name, item.input, item.description)
  return (
    <div className={`tip-activity-item ${isActive ? 'tip-activity-active' : 'tip-activity-done'}`}>
      <span className="tip-activity-icon">{isActive ? icon : '✓'}</span>
      <div className="tip-activity-body">
        <div className="tip-activity-name">
          {item.name.replace(/_/g, ' ')}
          {!isActive && <span className="tip-activity-time">{_formatTime(item.timestamp)}</span>}
        </div>
        {summary && <div className="tip-activity-summary">{summary}</div>}
      </div>
    </div>
  )
}

function ActivityFeed({ activeTool, toolHistory, t }) {
  const hasActivity = activeTool || (toolHistory && toolHistory.length > 0)
  if (!hasActivity) return null

  return (
    <>
      <div className="tip-section-label">{t('taskInfo.activityFeed', 'Activity Feed')}</div>
      <div className="tip-activity-feed">
        {activeTool && (
          <ActivityItem item={activeTool} isActive={true} />
        )}
        {toolHistory && toolHistory.filter(t => t.done).map((item, i) => (
          <ActivityItem key={i} item={item} isActive={false} />
        ))}
      </div>
    </>
  )
}

// ── Browser Tabs ──────────────────────────────────────────────────

function BrowserTabRow({ tab }) {
  return (
    <div className={`tip-tab ${tab.active ? 'tip-tab-active' : ''}`}>
      <span className="tip-tab-icon">{tab.active ? '●' : '○'}</span>
      <div className="tip-tab-info">
        <span className="tip-tab-title">{tab.title?.slice(0, 40) || 'Untitled'}</span>
        <span className="tip-tab-url">{_hostname(tab.url)}</span>
      </div>
    </div>
  )
}

// ── Task Dashboard sub-components ─────────────────────────────────

function SubtaskRow({ subtask, isCurrent }) {
  const s = STATUS_ICONS[subtask.status] || STATUS_ICONS.pending
  return (
    <div className={`tip-subtask ${isCurrent ? 'tip-subtask-current' : ''}`}>
      <span className={`tip-subtask-icon ${s.cls}`}>{s.icon}</span>
      <span className="tip-subtask-step">{subtask.step}.</span>
      <span className="tip-subtask-goal">{subtask.goal}</span>
      {isCurrent && <span className="tip-subtask-now">now</span>}
    </div>
  )
}

function FindingsSection({ findings, t }) {
  if (!findings || findings.length === 0) return null
  return (
    <div className="tip-findings">
      <div className="tip-section-label">{t('taskInfo.findings', 'Findings')}</div>
      {findings.map((f, i) => (
        <div key={i} className="tip-finding-row">
          <span className="tip-finding-bullet">•</span>
          <span className="tip-finding-text">{f}</span>
        </div>
      ))}
    </div>
  )
}

function PagesSection({ pages, t }) {
  if (!pages || pages.length === 0) return null
  return (
    <div className="tip-pages">
      <div className="tip-section-label">{t('taskInfo.pagesVisited', 'Pages Visited')}</div>
      {pages.map((p, i) => (
        <div key={i} className="tip-page-row">
          <span className="tip-page-host">{_hostname(p.url)}</span>
          {p.visited_count > 1 && <span className="tip-page-count">({p.visited_count}x)</span>}
          {p.title && <span className="tip-page-title">{p.title.slice(0, 30)}</span>}
        </div>
      ))}
    </div>
  )
}

function InjectionsSection({ injections, t }) {
  if (!injections || injections.length === 0) return null
  const userInjections = injections.filter(inj => inj.content)
  if (userInjections.length === 0) return null
  return (
    <div className="tip-injections">
      <div className="tip-section-label">{t('taskInfo.userInjections', 'User Injections')}</div>
      {userInjections.map((inj, i) => (
        <div key={i} className="tip-injection-row">
          <span className="tip-injection-icon">{inj.consumed ? '✓' : '…'}</span>
          <span className="tip-injection-text">"{inj.content}"</span>
        </div>
      ))}
    </div>
  )
}

function formatElapsed(s) {
  if (!s) return '0s'
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

// ── Task Dashboard (active task mode) ──────────────────────────────

function TaskDashboard({ activeTask, taskDetail, t }) {
  const detail = taskDetail || {}
  const subtasks = detail.subtasks || activeTask?.subtasks?.map((s, i) => ({
    step: i + 1, goal: s, status: 'pending'
  })) || []
  const currentStep = subtasks.find(st => st.status === 'running')?.step || 0
  const memory = detail.memory || {}
  const elapsed = detail.elapsed_seconds || 0
  const steps = detail.steps || []
  const llmSteps = steps.filter(s => s.action?.action === 'llm')
  const status = detail.status || 'running'

  return (
    <div className="tip-dashboard">
      <div className="tip-dash-header">
        <span className={`tip-dash-status ${status === 'running' ? 'tip-dash-running' : ''}`}>
          {status === 'running' ? '🔄' : status === 'completed' ? '✅' : '⚠️'}
        </span>
        <span className="tip-dash-desc">{detail.description || activeTask?.description || 'Task'}</span>
      </div>

      <div className="tip-dash-stats">
        <span>⏱ {formatElapsed(elapsed)}</span>
        <span>Steps: {steps.length}</span>
        {llmSteps.length > 0 && <span>🧠 {llmSteps.length}</span>}
      </div>

      <div className="tip-section-label">{t('taskInfo.subtasks', 'Subtasks')}</div>
      <div className="tip-subtask-list">
        {subtasks.map((st, i) => (
          <SubtaskRow key={i} subtask={st} isCurrent={st.step === currentStep} />
        ))}
      </div>

      <FindingsSection findings={memory.findings} t={t} />
      <PagesSection pages={memory.pages} t={t} />
      <InjectionsSection injections={detail.user_injections} t={t} />
    </div>
  )
}

// ── Main Panel ────────────────────────────────────────────────────

export default function TaskInfoPanel({
  tasks, sessionId, processing, browserTabs = [],
  activeTask = null, taskDetail = null,
  activeTool = null, toolHistory = [], lastUserMessage = '',
}) {
  const { t } = useTranslation()
  const hasActiveTask = activeTask !== null

  return (
    <div className="chat-info-panel">
      <div className="tip-header">
        <span className="tip-title">
          {hasActiveTask ? t('taskInfo.taskDashboard', 'Task Dashboard') : t('taskInfo.agentActivity', 'Agent Activity')}
        </span>
        {(processing || hasActiveTask) && <span className="tip-live-badge">LIVE</span>}
      </div>

      {hasActiveTask ? (
        <TaskDashboard activeTask={activeTask} taskDetail={taskDetail} t={t} />
      ) : (
        <div className="tip-scroll">
          <UserRequestCard content={lastUserMessage} t={t} />
          <ActivityFeed activeTool={activeTool} toolHistory={toolHistory} t={t} />

          <div className="tip-section-label">{t('taskInfo.browser', 'Browser')}</div>
          {browserTabs.length === 0 ? (
            <div className="tip-empty">{t('taskInfo.noTabs', 'No browser tabs')}</div>
          ) : (
            <div className="tip-tabs-list">
              {browserTabs.map(tab => (
                <BrowserTabRow key={tab.tab_id} tab={tab} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
