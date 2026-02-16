import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'

// Generate a zoomed-in favicon so the crab fills the browser tab icon
;(function setFavicon() {
  const img = new Image()
  img.src = '/clawome.png'
  img.onload = () => {
    const size = 64
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    const ctx = canvas.getContext('2d')
    // Crop the center 70% of the image to zoom into the crab
    const crop = 0.15
    const sx = img.width * crop
    const sy = img.height * crop
    const sw = img.width * (1 - crop * 2)
    const sh = img.height * (1 - crop * 2)
    ctx.drawImage(img, sx, sy, sw, sh, 0, 0, size, size)
    const link = document.querySelector("link[rel*='icon']") || document.createElement('link')
    link.rel = 'icon'
    link.type = 'image/png'
    link.href = canvas.toDataURL('image/png')
    document.head.appendChild(link)
  }
})()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
