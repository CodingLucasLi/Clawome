import { useState, useCallback } from 'react'
import { runBenchmark } from '../api'

const INITIAL_BENCHMARKS = [
  {
    page: 'Google Homepage',
    url: 'https://google.com',
    rawTokens: 51155,
    compressedTokens: 238,
    ratio: 0.005,
    completeness: '100.0%',
    agentFriendly: 5,
  },
  {
    page: 'Wikipedia Article',
    url: 'https://en.wikipedia.org/wiki/Silicon_Valley',
    rawTokens: 225525,
    compressedTokens: 40444,
    ratio: 0.179,
    completeness: '99.7%',
    agentFriendly: 4,
  },
  {
    page: 'Harvard Alumni',
    url: 'https://alumni.harvard.edu/programs-events',
    rawTokens: 177793,
    compressedTokens: 31658,
    ratio: 0.178,
    completeness: '99.7%',
    agentFriendly: 4,
  },
  {
    page: 'Google Search "python"',
    url: 'https://google.com/search?q=python+programming',
    rawTokens: 298262,
    compressedTokens: 2866,
    ratio: 0.010,
    completeness: '100.0%',
    agentFriendly: 2,
  },
  {
    page: 'Baidu Homepage',
    url: 'https://baidu.com',
    rawTokens: 192945,
    compressedTokens: 457,
    ratio: 0.002,
    completeness: '100.0%',
    agentFriendly: 3,
  },
  {
    page: 'Baidu Search "python"',
    url: 'https://baidu.com/s?wd=python',
    rawTokens: 390249,
    compressedTokens: 4960,
    ratio: 0.013,
    completeness: '100.0%',
    agentFriendly: 3,
  },
]

function Stars({ count }) {
  return (
    <span className="bench-stars" title={`${count}/5`}>
      {'★'.repeat(count)}{'☆'.repeat(5 - count)}
    </span>
  )
}

/** Truncate to 1 decimal place (no rounding), display as savings % */
function compressionStr(ratio) {
  if (ratio == null) return '—'
  const savings = (1 - ratio) * 100
  const truncated = Math.floor(savings * 10) / 10
  return `${truncated.toFixed(1)}%`
}

export default function BenchmarkTable() {
  const [benchmarks, setBenchmarks] = useState(INITIAL_BENCHMARKS)
  const [running, setRunning] = useState(null)
  const [customUrl, setCustomUrl] = useState('')

  const runSingle = useCallback(async (index) => {
    const b = benchmarks[index]
    setRunning(index)
    try {
      const res = await runBenchmark(b.url)
      const d = res.data
      setBenchmarks(prev => {
        const next = [...prev]
        next[index] = {
          ...next[index],
          rawTokens: d.stats.raw_html_tokens,
          compressedTokens: d.stats.tree_tokens,
          ratio: d.stats.compression_ratio,
          completeness: d.completeness_pct,
        }
        return next
      })
    } catch (err) {
      alert('Benchmark failed: ' + (err.response?.data?.message || err.message))
    } finally {
      setRunning(null)
    }
  }, [benchmarks])

  const runCustom = useCallback(async () => {
    if (!customUrl.trim()) return
    const url = customUrl.trim()
    setRunning(-1)
    try {
      const res = await runBenchmark(url)
      const d = res.data
      setBenchmarks(prev => [
        ...prev,
        {
          page: d.title || url,
          url: d.url || url,
          rawTokens: d.stats.raw_html_tokens,
          compressedTokens: d.stats.tree_tokens,
          ratio: d.stats.compression_ratio,
          completeness: d.completeness_pct,
          agentFriendly: 3,
        },
      ])
      setCustomUrl('')
    } catch (err) {
      alert('Benchmark failed: ' + (err.response?.data?.message || err.message))
    } finally {
      setRunning(null)
    }
  }, [customUrl])

  return (
    <div className="benchmark-table-wrap">
      <div className="benchmark-header">
        <span className="benchmark-title">DOM Compression Benchmarks</span>
        <span className="benchmark-count">{benchmarks.length} pages tested</span>
      </div>
      <table className="benchmark-table">
        <thead>
          <tr>
            <th className="bench-page">Page</th>
            <th className="bench-stars-cell">Web Agent Friendly</th>
            <th className="bench-num">Raw Tokens</th>
            <th className="bench-num bench-result-th">After Compressed</th>
            <th className="bench-num bench-result-th">Token Saving</th>
            <th className="bench-status bench-result-th">Completeness</th>
            <th className="bench-action">Test</th>
          </tr>
        </thead>
        <tbody>
          {benchmarks.map((b, i) => {
            const isRunning = running === i
            return (
              <tr key={i} className={b.ratio === null ? 'bench-row-disabled' : ''}>
                <td className="bench-page">
                  <a href={b.url} target="_blank" rel="noopener noreferrer">{b.page}</a>
                </td>
                <td className="bench-stars-cell"><Stars count={b.agentFriendly} /></td>
                <td className="bench-num">{b.rawTokens ? b.rawTokens.toLocaleString() : '—'}</td>
                <td className="bench-num bench-result-cell">{b.compressedTokens ? b.compressedTokens.toLocaleString() : '—'}</td>
                <td className="bench-num bench-ratio bench-result-cell">{compressionStr(b.ratio)}</td>
                <td className="bench-status bench-result-cell">{b.completeness}</td>
                <td className="bench-action">
                  <button
                    className="bench-run-btn"
                    onClick={() => runSingle(i)}
                    disabled={running !== null}
                  >
                    {isRunning ? '⏳' : '▶'}
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {/* Custom URL test */}
      <div className="bench-custom">
        <input
          type="text"
          className="bench-custom-input"
          placeholder="Enter URL to benchmark..."
          value={customUrl}
          onChange={e => setCustomUrl(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && runCustom()}
          disabled={running !== null}
        />
        <button
          className="bench-custom-btn"
          onClick={runCustom}
          disabled={running !== null || !customUrl.trim()}
        >
          {running === -1 ? 'Testing...' : 'Run Benchmark'}
        </button>
      </div>
    </div>
  )
}
