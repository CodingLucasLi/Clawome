import { useState, useEffect, useCallback } from 'react'
import { NavLink, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { getStatus, getConfig } from '../api'
import './Header.css'

export default function Header() {
  const { t, i18n } = useTranslation()
  const [browserOpen, setBrowserOpen] = useState(false)
  const [headless, setHeadless] = useState(false)

  const poll = useCallback(async () => {
    try {
      const [statusRes, configRes] = await Promise.all([getStatus(), getConfig()])
      setBrowserOpen(!!statusRes.data.is_open)
      setHeadless(!!configRes.data.config.headless)
    } catch {
      setBrowserOpen(false)
    }
  }, [])

  useEffect(() => {
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [poll])

  const toggleLang = () => {
    const next = i18n.language === 'zh' ? 'en' : 'zh'
    i18n.changeLanguage(next)
    localStorage.setItem('lang', next)
  }

  const showHeadlessBanner = headless && browserOpen

  return (
    <header className="header">
      <Link to="/" className="header-brand">
        <img src="/clawome.png" alt="" className="header-logo" />
        Clawome
      </Link>
      <nav className="header-nav">
        <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          {t('header.home')}
        </NavLink>
        <NavLink to="/playground" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          {t('header.playground')}
        </NavLink>
        <NavLink to="/docs" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          {t('header.docs')}
        </NavLink>
        <NavLink to="/benchmark" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          {t('header.benchmark')}
        </NavLink>
        <NavLink to="/agent" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          {t('header.agent')}
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          {t('header.settings')}
        </NavLink>
      </nav>
      {showHeadlessBanner && (
        <Link to="/playground" className="header-headless-badge">
          <span className="header-headless-dot" />
          {t('header.headlessBanner')}
        </Link>
      )}
      <button className="header-lang-btn" onClick={toggleLang} title="Switch language">
        {i18n.language === 'zh' ? 'EN' : '中'}
      </button>
    </header>
  )
}
