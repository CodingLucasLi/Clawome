import BenchmarkTable from '../components/BenchmarkTable'
import './BenchmarkPage.css'

export default function BenchmarkPage() {
  return (
    <div className="benchmark-page">
      <h1>Benchmark</h1>
      <p className="benchmark-desc">
        DOM compression performance across different websites. Raw HTML tokens vs.
        compressed DOM tree tokens — measuring how much we can reduce while retaining
        page semantics and interactive elements.
      </p>

      <BenchmarkTable />

      <div className="benchmark-notes">
        <h3>Methodology</h3>
        <ul>
          <li><strong>Raw Tokens</strong> — character count of full page <code>outerHTML</code> ÷ 4</li>
          <li><strong>Compressed</strong> — character count of the filtered DOM tree output ÷ 4</li>
          <li><strong>Token Saving</strong> — <code>(1 - compressed/raw) × 100%</code>, truncated to 2 decimals</li>
          <li><strong>Completeness</strong> — percentage of <strong>visible-only</strong> text lines found in compressed output (hidden / collapsed / <code>aria-hidden</code> content excluded from denominator)</li>
        </ul>

        <h3>Web Agent Friendly</h3>
        <p className="benchmark-rating-desc">
          How well the original page supports autonomous web agent browsing (1–5 ★). This is a property of the page itself, not our algorithm. Scoring dimensions:
        </p>
        <ul>
          <li><strong>Semantic HTML</strong> — use of <code>nav</code>, <code>main</code>, <code>article</code>, <code>form</code>, <code>aria-*</code></li>
          <li><strong>Interactive discoverability</strong> — buttons, links, inputs with clear labels</li>
          <li><strong>Anti-bot barriers</strong> — captcha, fingerprinting, obfuscation</li>
          <li><strong>HTML redundancy</strong> — excessive div nesting, inline styles, bloated markup that wastes agent tokens</li>
        </ul>

        <h3>Notes</h3>
        <ul>
          <li>Walker node cap set to 20,000 — sufficient for all tested pages</li>
          <li>Google Search blocks automated browsers with captcha — rated ★☆☆☆☆</li>
          <li>Click ▶ to re-run any individual benchmark via the <code>/api/benchmark</code> endpoint</li>
          <li>Enter any URL in the input box below the table to test a new page</li>
        </ul>

        <h3>API</h3>
        <p className="benchmark-rating-desc">
          Benchmark is available as a standalone REST API:
        </p>
        <ul>
          <li><code>POST /api/benchmark</code> — score a single page: <code>{`{"url": "https://..."}`}</code></li>
          <li><code>POST /api/benchmark/batch</code> — score multiple pages: <code>{`{"urls": [...]}`}</code></li>
          <li>Returns: compression stats, completeness %, token saving %, visible line counts</li>
        </ul>
      </div>
    </div>
  )
}
