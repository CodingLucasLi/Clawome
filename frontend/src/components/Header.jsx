import { useState, useEffect, useCallback } from 'react'
import { NavLink, Link } from 'react-router-dom'
import { getStatus, getConfig } from '../api'
import './Header.css'

export default function Header() {
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

  const showHeadlessBanner = headless && browserOpen

  return (
    <header className="header">
      <Link to="/" className="header-brand">
        <img src="/clawome.png" alt="" className="header-logo" />
        Clawome
      </Link>
      <nav className="header-nav">
        <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Home
        </NavLink>
        <NavLink to="/playground" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Playground
        </NavLink>
        <NavLink to="/docs" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Docs
        </NavLink>
        <NavLink to="/benchmark" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Benchmark
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Settings
        </NavLink>
      </nav>
      {showHeadlessBanner && (
        <Link to="/playground" className="header-headless-badge">
          <span className="header-headless-dot" />
          Headless browser running
        </Link>
      )}
    </header>
  )
}
