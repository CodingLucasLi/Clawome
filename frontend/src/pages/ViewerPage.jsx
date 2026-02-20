import { useState, useEffect, useRef } from 'react'
import {
  openBrowser, closeBrowser, navigate, getStatus, getScreenshotUrl,
  getPageSource, getDomTree, clickNode, typeByNode,
  goBack, goForward, refreshPage, getTabs, switchTab, closeTab, newTab,
} from '../api'
import BrowserTabBar from '../components/BrowserTabBar'
import InteractivePanel from '../components/InteractivePanel'
import DomStats from '../components/DomStats'
import DomChanges from '../components/DomChanges'
import './ViewerPage.css'

export default function ViewerPage() {
  const [isOpen, setIsOpen] = useState(false)
  const [currentUrl, setCurrentUrl] = useState(null)
  const [url, setUrl] = useState('https://www.csair.com')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [pageSource, setPageSource] = useState('')
  const [activeTab, setActiveTab] = useState('dom')
  const [browserTabs, setBrowserTabs] = useState([])
  const [activeTabId, setActiveTabId] = useState(null)
  const [tabDomCache, setTabDomCache] = useState({})
  const [activePageId, setActivePageId] = useState(null)
  const activePageIdRef = useRef(null)
  const [domLoading, setDomLoading] = useState(false)
  const [copiedKey, setCopiedKey] = useState(null)
  const [apiResult, setApiResult] = useState(null)        // last action API response
  const [screenshotLoaded, setScreenshotLoaded] = useState(false)
  const screenshotRef = useRef(null)
  const screenshotInterval = useRef(null)
  const panelInterval = useRef(null)

  const handleCopy = (text, key) => {
    if (!text) return
    navigator.clipboard.writeText(text)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey(null), 1500)
  }

  const activeDom = tabDomCache[activePageId] || {}
  const domTree = activeDom.domTree || ''
  const interactiveNodes = activeDom.interactiveNodes || []
  const domStats = activeDom.domStats || null

  useEffect(() => { activePageIdRef.current = activePageId }, [activePageId])

  const fetchStatus = async () => {
    try {
      const { data } = await getStatus()
      setIsOpen(data.is_open)
      setCurrentUrl(data.current_url)
    } catch {
      setMessage('Failed to fetch status')
    }
  }

  const fetchSource = async () => {
    try {
      const resp = await getPageSource()
      const src = resp.data?.source || resp.data?.html
      if (resp.status === 200 && src) setPageSource(src)
    } catch { /* keep cached */ }
  }

  const fetchUnifiedDom = async () => {
    try {
      const resp = await getDomTree()
      if (resp.status === 200 && resp.data) {
        const pid = activePageIdRef.current
        if (pid) {
          setTabDomCache(prev => ({
            ...prev,
            [pid]: {
              domTree: resp.data.dom || '',
              interactiveNodes: resp.data.interactive || [],
              domStats: resp.data.stats || null,
            }
          }))
        }
      }
    } catch {
      // Keep cached data on error
    }
  }

  const fetchRightPanel = async () => {
    await Promise.all([fetchUnifiedDom(), fetchSource()])
  }

  const handleRefreshDom = async () => {
    setDomLoading(true)
    try {
      await fetchBrowserTabs()
      await fetchRightPanel()
    } catch {}
    setDomLoading(false)
  }

  const updateTabsFromResponse = (data) => {
    if (data?.tabs) {
      setBrowserTabs(data.tabs)
      const active = data.tabs.find(t => t.active)
      if (active) {
        setActiveTabId(active.tab_id)
        setActivePageId(active.page_id)
        if (data.dom !== undefined) {
          setTabDomCache(prev => ({
            ...prev,
            [active.page_id]: {
              domTree: data.dom || '',
              interactiveNodes: data.interactive || [],
              domStats: data.stats || null,
            }
          }))
        }
      }
    }
  }

  const fetchBrowserTabs = async () => {
    try {
      const { data } = await getTabs()
      if (data?.tabs) {
        setBrowserTabs(data.tabs)
        const active = data.tabs.find(t => t.active)
        if (active) {
          setActiveTabId(active.tab_id)
          setActivePageId(active.page_id)
        }
        const validIds = new Set(data.tabs.map(t => t.page_id))
        setTabDomCache(prev => {
          const next = {}
          for (const [pid, d] of Object.entries(prev)) {
            if (validIds.has(pid)) next[pid] = d
          }
          return next
        })
      }
    } catch {}
  }

  const handleSwitchTab = async (tabId) => {
    const targetTab = browserTabs.find(t => t.tab_id === tabId)
    if (targetTab?.page_id) setActivePageId(targetTab.page_id)
    try {
      const { data } = await switchTab(tabId)
      updateTabsFromResponse(data)
      if (screenshotRef.current) screenshotRef.current.src = getScreenshotUrl()
      await fetchRightPanel()
    } catch (err) {
      setMessage(`Switch tab failed: ${err.response?.data?.message || err.message}`)
    }
  }

  const handleCloseTab = async (tabId) => {
    const closedTab = browserTabs.find(t => t.tab_id === tabId)
    const closedPageId = closedTab?.page_id
    try {
      const { data } = await closeTab(tabId)
      if (data?.tabs) {
        setBrowserTabs(data.tabs)
        const active = data.tabs.find(t => t.active)
        if (active) {
          setActiveTabId(active.tab_id)
          setActivePageId(active.page_id)
        }
      }
      if (closedPageId) {
        setTabDomCache(prev => {
          const next = { ...prev }
          delete next[closedPageId]
          return next
        })
      }
      if (screenshotRef.current) screenshotRef.current.src = getScreenshotUrl()
      await fetchRightPanel()
    } catch (err) {
      setMessage(`Close tab failed: ${err.response?.data?.message || err.message}`)
    }
  }

  const handleNewTab = async () => {
    try {
      const { data } = await newTab()
      updateTabsFromResponse(data)
      if (screenshotRef.current) screenshotRef.current.src = getScreenshotUrl()
      await fetchRightPanel()
    } catch (err) {
      setMessage(`New tab failed: ${err.response?.data?.message || err.message}`)
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 3000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (isOpen) {
      const update = () => {
        if (screenshotRef.current) screenshotRef.current.src = getScreenshotUrl()
      }
      update()
      screenshotInterval.current = setInterval(update, 1000)
      fetchBrowserTabs()
      fetchRightPanel()
      panelInterval.current = setInterval(() => {
        fetchBrowserTabs()
        fetchRightPanel()
      }, 5000)
    } else {
      clearInterval(screenshotInterval.current)
      clearInterval(panelInterval.current)
      setPageSource('')
      setTabDomCache({})
      setActivePageId(null)
      setScreenshotLoaded(false)
    }
    return () => {
      clearInterval(screenshotInterval.current)
      clearInterval(panelInterval.current)
    }
  }, [isOpen])

  useEffect(() => {
    if (!message) return
    const t = setTimeout(() => setMessage(''), 4000)
    return () => clearTimeout(t)
  }, [message])

  const handleOpen = async () => {
    setLoading(true)
    try {
      const { data } = await openBrowser()
      setMessage(data.message)
      updateTabsFromResponse(data)
      await fetchStatus()
      await fetchBrowserTabs()
    } catch { setMessage('Failed to open browser') }
    setLoading(false)
  }

  const handleClose = async () => {
    setLoading(true)
    try {
      const { data } = await closeBrowser()
      setMessage(data.message)
      setPageSource('')
      setTabDomCache({})
      setActivePageId(null)
      setBrowserTabs([])
      setActiveTabId(null)
      await fetchStatus()
    } catch { setMessage('Failed to close browser') }
    setLoading(false)
  }

  const handleNavigate = async () => {
    if (!url.trim()) return
    setLoading(true)
    try {
      const { data } = await navigate(url)
      setMessage(data.message)
      updateTabsFromResponse(data)
      await fetchStatus()
      await fetchRightPanel()
    } catch { setMessage('Failed to navigate') }
    setLoading(false)
  }

  const handleBack = async () => {
    setLoading(true)
    try {
      const { data } = await goBack()
      setMessage(data.message)
      updateTabsFromResponse(data)
      await fetchStatus()
      await fetchRightPanel()
    } catch { setMessage('Failed to go back') }
    setLoading(false)
  }

  const handleForward = async () => {
    setLoading(true)
    try {
      const { data } = await goForward()
      setMessage(data.message)
      updateTabsFromResponse(data)
      await fetchStatus()
      await fetchRightPanel()
    } catch { setMessage('Failed to go forward') }
    setLoading(false)
  }

  const handleRefreshPage = async () => {
    setLoading(true)
    try {
      const { data } = await refreshPage()
      setMessage(data.message)
      updateTabsFromResponse(data)
      await fetchStatus()
      await fetchRightPanel()
    } catch { setMessage('Failed to refresh page') }
    setLoading(false)
  }

  const handleAction = async (action, nodeId, text) => {
    setLoading(true)
    try {
      let res
      if (action === 'click') {
        res = await clickNode(nodeId)
      } else if (action === 'type') {
        res = await typeByNode(nodeId, text)
      }
      setMessage(res.data.message)
      updateTabsFromResponse(res.data)
      // Save full API response and switch to result tab
      setApiResult({ action, nodeId, text, ts: Date.now(), data: res.data })
      setActiveTab('result')
      await fetchStatus()
      if (screenshotRef.current) screenshotRef.current.src = getScreenshotUrl()
    } catch (err) {
      setMessage(`Action failed: ${err.response?.data?.message || err.message}`)
      setApiResult({ action, nodeId, text, ts: Date.now(), error: err.response?.data?.message || err.message })
      setActiveTab('result')
    }
    setLoading(false)
  }

  const placeholder = isOpen ? 'Navigate to a page to see content.' : 'Browser is closed.'

  return (
    <div className="viewer">
      <div className="viewer-layout">
        {/* Left Panel */}
        <div className="left-panel">
          <h2 className="viewer-title">Browser Playground</h2>

          <div className="status">
            <span className={`dot ${isOpen ? 'open' : 'closed'}`} />
            <span>{isOpen ? 'Browser is open' : 'Browser is closed'}</span>
          </div>

          {currentUrl && (
            <div className="current-url">
              <code>{currentUrl}</code>
              <button
                className={`copy-btn${copiedKey === 'url' ? ' copied' : ''}`}
                onClick={() => handleCopy(currentUrl, 'url')}
                title="Copy URL"
              >{copiedKey === 'url' ? 'Copied!' : 'Copy'}</button>
            </div>
          )}

          {message && <div className="message">{message}</div>}

          <div className="controls">
            <button onClick={handleOpen} disabled={loading || isOpen}>Open Browser</button>
            <button onClick={handleClose} disabled={loading || !isOpen}>Close Browser</button>
          </div>

          <div className="navigate">
            <div className="nav-buttons">
              <button className="nav-btn" onClick={handleBack} disabled={loading || !isOpen} title="Back">&#9664;</button>
              <button className="nav-btn" onClick={handleForward} disabled={loading || !isOpen} title="Forward">&#9654;</button>
              <button className="nav-btn" onClick={handleRefreshPage} disabled={loading || !isOpen} title="Refresh">&#8635;</button>
            </div>
            <input
              type="text"
              placeholder="Enter URL..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleNavigate()}
              disabled={!isOpen}
            />
            <button onClick={handleNavigate} disabled={loading || !isOpen || !url.trim()}>Go</button>
          </div>

          {isOpen && (
            <>
              <BrowserTabBar
                tabs={browserTabs}
                onSwitch={handleSwitchTab}
                onClose={handleCloseTab}
                onNew={handleNewTab}
              />
              <div className="screenshot-container">
                {!screenshotLoaded && (
                  <div className="screenshot-placeholder">Loading...</div>
                )}
                <img
                  className="screenshot"
                  ref={screenshotRef}
                  alt="Browser screenshot"
                  onError={(e) => { e.target.style.display = 'none'; setScreenshotLoaded(false); fetchBrowserTabs() }}
                  onLoad={(e) => { e.target.style.display = ''; setScreenshotLoaded(true) }}
                />
              </div>
            </>
          )}
        </div>

        {/* Right Panel */}
        <div className="right-panel">
          <div className="tab-bar">
            <button
              className={`tab-btn ${activeTab === 'dom' ? 'active' : ''}`}
              onClick={() => setActiveTab('dom')}
            >DOM List</button>
            <button
              className={`tab-btn ${activeTab === 'interactive' ? 'active' : ''}`}
              onClick={() => setActiveTab('interactive')}
            >Elements</button>
            <button
              className={`tab-btn ${activeTab === 'result' ? 'active' : ''}`}
              onClick={() => setActiveTab('result')}
            >API Result{apiResult ? ' ●' : ''}</button>
            <button
              className={`tab-btn ${activeTab === 'source' ? 'active' : ''}`}
              onClick={() => setActiveTab('source')}
            >Page Source</button>
            <button className="refresh-btn" onClick={handleRefreshDom} disabled={!isOpen || domLoading}>
              {domLoading ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>

          <div className="tab-content" key={activeTab}>
            {activeTab === 'interactive' ? (
              <InteractivePanel
                nodes={interactiveNodes}
                isOpen={isOpen}
                onAction={handleAction}
              />
            ) : activeTab === 'result' ? (
              <DomChanges result={apiResult} />
            ) : (
              <>
                <div className="code-toolbar">
                  {activeTab === 'dom' && <span className="toolbar-hint">For Agent to Read</span>}
                  <button
                    className={`copy-btn${copiedKey === 'code' ? ' copied' : ''}`}
                    onClick={() => {
                      const text = activeTab === 'dom' ? (domTree || '') : (pageSource || '')
                      handleCopy(text, 'code')
                    }}
                    title="Copy to clipboard"
                  >{copiedKey === 'code' ? 'Copied!' : 'Copy'}</button>
                </div>
                <pre className={`source-code${activeTab === 'dom' ? ' dom-view' : ''}`}>
                  <code>
                    {activeTab === 'dom' ? (domTree || placeholder) : (pageSource || placeholder)}
                  </code>
                </pre>
              </>
            )}
          </div>

          {activeTab !== 'source' && domStats && (
            <DomStats stats={domStats} />
          )}
        </div>
      </div>
    </div>
  )
}
