import { useState } from 'react'

// Strip ⟨⟩ markers used by the DOM walker for agent consumption
const cleanLabel = (s) => s ? s.replace(/[⟨⟩]/g, '') : ''

const TAG_COLORS = {
  a: '#8b5cf6', button: '#f59e0b', input: '#10b981', textarea: '#10b981',
  select: '#10b981', form: '#6366f1', img: '#ec4899', h1: '#0ea5e9',
  h2: '#0ea5e9', h3: '#0ea5e9', h4: '#0ea5e9', h5: '#0ea5e9', h6: '#0ea5e9',
}

export default function InteractivePanel({ nodes, isOpen, onAction }) {
  const [typeValues, setTypeValues] = useState({})

  if (!isOpen) return <div className="panel-placeholder">Browser is closed.</div>
  if (!nodes || nodes.length === 0) return <div className="panel-placeholder">Navigate to a page to see elements.</div>

  return (
    <div className="interactive-list">
      {nodes.map((n) => {
        const indent = n.depth * 20
        const color = TAG_COLORS[n.tag] || '#64748b'
        const hasClick = n.actions.includes('click')
        const hasType = n.actions.includes('type')
        const hasSelect = n.actions.includes('select')
        const isInteractive = hasClick || hasType || hasSelect

        return (
          <div
            key={n.hid}
            className={`inode ${isInteractive ? 'interactive' : ''}`}
            style={{ paddingLeft: indent + 12 }}
          >
            <span className="inode-hid">{n.hid}</span>
            <span className="inode-tag" style={{ background: color }}>{n.tag}</span>
            {n.label && <span className="inode-label">{cleanLabel(n.label)}</span>}

            {n.state && Object.keys(n.state).length > 0 && (
              <span className="inode-state">
                {Object.entries(n.state).map(([k, v]) => (
                  <span key={k} className="state-badge">
                    {v === 'true' ? k : `${k}=${v}`}
                  </span>
                ))}
              </span>
            )}

            {hasClick && (
              <button
                className="action-btn action-click"
                onClick={() => onAction('click', n.hid)}
              >
                Click
              </button>
            )}

            {hasType && (
              <span className="action-type-group">
                <input
                  className="action-type-input"
                  type="text"
                  placeholder="text…"
                  value={typeValues[n.hid] || ''}
                  onChange={(e) => setTypeValues(prev => ({ ...prev, [n.hid]: e.target.value }))}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      onAction('type', n.hid, typeValues[n.hid] || '')
                    }
                  }}
                />
                <button
                  className="action-btn action-type"
                  onClick={() => onAction('type', n.hid, typeValues[n.hid] || '')}
                >
                  Type
                </button>
              </span>
            )}

            {hasSelect && (
              <button
                className="action-btn action-click"
                onClick={() => onAction('click', n.hid)}
              >
                Select
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
