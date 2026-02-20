// Strip ⟨⟩ markers used by the DOM walker for agent consumption
const clean = (s) => s ? s.replace(/[⟨⟩]/g, '') : ''

/**
 * DomChanges — displays the API result from click/type actions,
 * including the dom_changes diff (added / removed / changed nodes).
 */
export default function DomChanges({ result }) {
  if (!result) {
    return <div className="panel-placeholder">Execute a Click or Type action to see results here.</div>
  }

  const { action, nodeId, text, ts, data, error } = result

  // Action header
  const actionLabel = action === 'click' ? `Click [${nodeId}]`
    : action === 'type' ? `Type "${text}" → [${nodeId}]`
    : `${action} [${nodeId}]`
  const time = new Date(ts).toLocaleTimeString()

  if (error) {
    return (
      <div className="dom-changes">
        <div className="dc-header">
          <span className="dc-action">{actionLabel}</span>
          <span className="dc-time">{time}</span>
        </div>
        <div className="dc-error">Error: {error}</div>
      </div>
    )
  }

  const changes = data?.dom_changes
  const message = data?.message || ''

  return (
    <div className="dom-changes">
      {/* Action header */}
      <div className="dc-header">
        <span className="dc-action">{actionLabel}</span>
        <span className="dc-status">{message}</span>
        <span className="dc-time">{time}</span>
      </div>

      {/* DOM Changes summary */}
      {changes ? (
        <>
          <div className={`dc-summary ${changes.has_changes ? 'has-changes' : 'no-changes'}`}>
            {changes.summary}
          </div>

          {/* Added nodes */}
          {changes.added?.length > 0 && (
            <div className="dc-section">
              <div className="dc-section-title added">+ Added ({changes.added.length})</div>
              {changes.added.map((n, i) => (
                <div key={i} className="dc-node added">
                  <span className="dc-hid">{n.hid}</span>
                  <span className="dc-tag">{n.tag}</span>
                  {n.actions?.length > 0 && <span className="dc-actions">[{n.actions.join('/')}]</span>}
                  <span className="dc-label">{clean(n.label)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Removed nodes */}
          {changes.removed?.length > 0 && (
            <div className="dc-section">
              <div className="dc-section-title removed">− Removed ({changes.removed.length})</div>
              {changes.removed.map((n, i) => (
                <div key={i} className="dc-node removed">
                  <span className="dc-hid">{n.hid}</span>
                  <span className="dc-tag">{n.tag}</span>
                  <span className="dc-label">{clean(n.label)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Changed nodes */}
          {changes.changed?.length > 0 && (
            <div className="dc-section">
              <div className="dc-section-title changed">△ Changed ({changes.changed.length})</div>
              {changes.changed.map((n, i) => (
                <div key={i} className="dc-node changed">
                  <span className="dc-hid">{n.hid}</span>
                  <span className="dc-tag">{n.tag}</span>
                  <span className="dc-field">{n.field}</span>
                  <span className="dc-diff">
                    <span className="dc-before">{n.before || '(empty)'}</span>
                    <span className="dc-arrow">→</span>
                    <span className="dc-after">{n.after || '(empty)'}</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="dc-summary no-changes">No dom_changes in response (action may not support diff yet)</div>
      )}
    </div>
  )
}
