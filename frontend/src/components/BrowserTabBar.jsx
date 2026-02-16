export default function BrowserTabBar({ tabs, onSwitch, onClose, onNew }) {
  if (!tabs || tabs.length === 0) return null
  return (
    <div className="browser-tab-bar">
      {tabs.map((tab) => (
        <div
          key={tab.page_id || tab.tab_id}
          className={`browser-tab ${tab.active ? 'active' : ''}`}
          onClick={() => onSwitch(tab.tab_id)}
          title={tab.url}
        >
          <span className="browser-tab-title">{tab.title || 'New Tab'}</span>
          {tabs.length > 1 && (
            <span
              className="browser-tab-close"
              onClick={(e) => { e.stopPropagation(); onClose(tab.tab_id) }}
            >
              &times;
            </span>
          )}
        </div>
      ))}
      <button className="browser-tab-new" onClick={onNew} title="New Tab">+</button>
    </div>
  )
}
