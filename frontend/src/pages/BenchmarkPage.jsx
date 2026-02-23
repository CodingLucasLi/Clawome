import { useTranslation } from 'react-i18next'
import BenchmarkTable from '../components/BenchmarkTable'
import './BenchmarkPage.css'

export default function BenchmarkPage() {
  const { t } = useTranslation()
  return (
    <div className="benchmark-page">
      <h1>{t('benchmark.title')}</h1>
      <p className="benchmark-desc">
        {t('benchmark.desc')}
      </p>

      <BenchmarkTable />

      <div className="benchmark-notes">
        <h3>{t('benchmark.methodology')}</h3>
        <ul>
          <li><strong>{t('benchmark.rawTokens')}</strong> — {t('benchmark.rawTokensDesc')}</li>
          <li><strong>{t('benchmark.compressed')}</strong> — {t('benchmark.compressedDesc')}</li>
          <li><strong>{t('benchmark.tokenSaving')}</strong> — {t('benchmark.tokenSavingDesc')}</li>
          <li><strong>{t('benchmark.completeness')}</strong> — {t('benchmark.completenessDesc')}</li>
        </ul>

        <h3>{t('benchmark.webAgentFriendly')}</h3>
        <p className="benchmark-rating-desc">
          {t('benchmark.webAgentDesc')}
        </p>
        <ul>
          <li><strong>{t('benchmark.semanticHtml')}</strong> — {t('benchmark.semanticDesc')}</li>
          <li><strong>{t('benchmark.interactiveDisc')}</strong> — {t('benchmark.interactiveDesc')}</li>
          <li><strong>{t('benchmark.antiBotBarriers')}</strong> — {t('benchmark.antiBotDesc')}</li>
          <li><strong>{t('benchmark.htmlRedundancy')}</strong> — {t('benchmark.htmlRedundancyDesc')}</li>
        </ul>

        <h3>{t('benchmark.notes')}</h3>
        <ul>
          <li>{t('benchmark.note1')}</li>
          <li>{t('benchmark.note2')}</li>
          <li>{t('benchmark.note3')}</li>
          <li>{t('benchmark.note4')}</li>
        </ul>

        <h3>{t('benchmark.api')}</h3>
        <p className="benchmark-rating-desc">
          {t('benchmark.apiDesc')}
        </p>
        <ul>
          <li><code>POST /api/benchmark</code> — {t('benchmark.apiSingle')}</li>
          <li><code>POST /api/benchmark/batch</code> — {t('benchmark.apiBatch')}</li>
          <li>{t('benchmark.apiReturns')}</li>
        </ul>
      </div>
    </div>
  )
}
