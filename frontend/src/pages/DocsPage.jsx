import { useState, useEffect, useRef } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { categories, docs } from '../data/apiDocs'
import './DocsPage.css'

// Group categories for sidebar navigation
const navGroups = [
  { label: null, ids: ['overview', 'skill-docs', 'quickstart'] },
  { label: 'Customization', ids: ['compressors', 'configuration'] },
  { label: 'Browser APIs', ids: ['navigation', 'dom-reading', 'interaction', 'scrolling', 'keyboard', 'tabs', 'screenshot', 'file-download', 'page-state', 'control'] },
]

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState('overview')
  const contentRef = useRef(null)
  const sectionRefs = useRef({})

  useEffect(() => {
    const container = contentRef.current
    if (!container) return

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.dataset.section)
            break
          }
        }
      },
      { root: container, rootMargin: '-10% 0px -80% 0px', threshold: 0 }
    )

    for (const el of Object.values(sectionRefs.current)) {
      if (el) observer.observe(el)
    }

    return () => observer.disconnect()
  }, [])

  const scrollToSection = (id) => {
    const el = sectionRefs.current[id]
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  const catMap = Object.fromEntries(categories.map(c => [c.id, c]))

  // Custom link renderer — /skill links open in new tab (raw text served by backend)
  const mdComponents = {
    a: ({ href, children, ...props }) => {
      if (href && href.startsWith('/skill')) {
        return <a href={href} target="_blank" rel="noopener noreferrer" className="docs-skill-link">{children}</a>
      }
      return <a href={href} {...props}>{children}</a>
    },
  }

  return (
    <div className="docs">
      <aside className="docs-sidebar">
        <nav className="docs-nav">
          {navGroups.map((group, gi) => (
            <div key={gi} className="docs-nav-group">
              {group.label && <div className="docs-nav-group-label">{group.label}</div>}
              {group.ids.map(id => {
                const cat = catMap[id]
                if (!cat) return null
                return (
                  <button
                    key={cat.id}
                    className={`docs-nav-item ${activeSection === cat.id ? 'active' : ''}`}
                    onClick={() => scrollToSection(cat.id)}
                  >
                    {cat.label}
                  </button>
                )
              })}
            </div>
          ))}
        </nav>
        <div className="docs-sidebar-footer">
          <a
            href="/api-reference.md"
            download
            className="docs-download"
          >
            Download api-reference.md
          </a>
          <span className="docs-download-hint">For LLM agents</span>
        </div>
      </aside>

      <div className="docs-content" ref={contentRef}>
        {categories.map((cat) => (
          <section
            key={cat.id}
            data-section={cat.id}
            ref={(el) => { sectionRefs.current[cat.id] = el }}
            className="docs-section"
          >
            <Markdown remarkPlugins={[remarkGfm]} components={mdComponents}>
              {docs[cat.id]}
            </Markdown>
          </section>
        ))}
      </div>
    </div>
  )
}
