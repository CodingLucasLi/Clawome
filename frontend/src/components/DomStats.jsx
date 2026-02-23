import { useTranslation } from 'react-i18next'

export default function DomStats({ stats }) {
  const { t } = useTranslation()
  if (!stats) return null
  return (
    <div className="dom-stats">
      {t('domStats.html')}: {stats.raw_html_chars.toLocaleString()} {t('domStats.chars')} (~{stats.raw_html_tokens.toLocaleString()} {t('domStats.tokens')})
      {' → '}{t('domStats.tree')}: {stats.tree_chars.toLocaleString()} {t('domStats.chars')} (~{stats.tree_tokens.toLocaleString()} {t('domStats.tokens')})
      {' | '}{t('domStats.ratio')}: {(stats.compression_ratio * 100).toFixed(1)}%
      {' | '}{t('domStats.nodes')}: {stats.nodes_before_filter}→{stats.nodes_after_filter}
    </div>
  )
}
