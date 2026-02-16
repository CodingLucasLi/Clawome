import { Routes, Route, Navigate } from 'react-router-dom'
import Header from './components/Header'
import HomePage from './pages/HomePage'
import ViewerPage from './pages/ViewerPage'
import DocsPage from './pages/DocsPage'
import BenchmarkPage from './pages/BenchmarkPage'
import SettingsPage from './pages/SettingsPage'
import './App.css'

export default function App() {
  return (
    <div className="app">
      <Header />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/playground" element={<ViewerPage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/benchmark" element={<BenchmarkPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
