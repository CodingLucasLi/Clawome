export default function DomStats({ stats }) {
  if (!stats) return null
  return (
    <div className="dom-stats">
      HTML: {stats.raw_html_chars.toLocaleString()} chars (~{stats.raw_html_tokens.toLocaleString()} tokens)
      {' → '}Tree: {stats.tree_chars.toLocaleString()} chars (~{stats.tree_tokens.toLocaleString()} tokens)
      {' | '}Ratio: {(stats.compression_ratio * 100).toFixed(1)}%
      {' | '}Nodes: {stats.nodes_before_filter}→{stats.nodes_after_filter}
    </div>
  )
}
