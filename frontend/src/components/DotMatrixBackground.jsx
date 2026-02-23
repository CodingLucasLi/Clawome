import { useEffect, useRef } from 'react'

const COLOR_THEMES = {
  red:     { bg: '#1a0a0a', from: [239, 68, 68],  to: [209, 118, 48] },
  blue:    { bg: '#0a0a1a', from: [59, 130, 246], to: [99, 179, 237] },
  green:   { bg: '#0a1a0a', from: [34, 197, 94],  to: [16, 185, 129] },
  purple:  { bg: '#0f0a1a', from: [168, 85, 247], to: [139, 92, 246] },
  lobster: { bg: '#1a1014', from: [224, 82, 82],  to: [240, 112, 112] },
}

export function DotMatrixBackground({ className = '', vibrant = false, color = 'purple' }) {
  const canvasRef = useRef(null)
  const timeRef = useRef(0)
  const animationRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const DOT_SPACING = vibrant ? 10 : 14
    const DOT_SIZE = vibrant ? 1.8 : 1.2

    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    }

    const drawEffect = () => {
      const theme = COLOR_THEMES[color]
      ctx.fillStyle = vibrant ? theme.bg : '#0a0a0a'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      for (let x = 0; x < canvas.width + DOT_SPACING; x += DOT_SPACING) {
        for (let y = 0; y < canvas.height + DOT_SPACING; y += DOT_SPACING) {
          const wave1 = Math.sin((x * 0.008) + (timeRef.current * 0.01)) * 40
          const wave2 = Math.sin((y * 0.006) + (timeRef.current * 0.008) + Math.PI / 3) * 30
          const wave3 = Math.sin(((x + y) * 0.004) + (timeRef.current * 0.012) + Math.PI / 2) * 25

          const centerX = canvas.width * 0.7
          const centerY = canvas.height * 0.5
          const distance = Math.sqrt(Math.pow(x - centerX, 2) + Math.pow(y - centerY, 2))
          const radialWave = Math.sin((distance * 0.01) + (timeRef.current * 0.02)) * 20

          const totalWave = wave1 + wave2 + wave3 + radialWave

          const intensity = Math.abs(totalWave) / 95
          const size = DOT_SIZE + (intensity * (vibrant ? 3 : 2))
          const opacity = Math.min(1, (vibrant ? 0.3 : 0.12) + (intensity * (vibrant ? 0.7 : 0.5)))

          const edgeFadeX = Math.min(x / 80, (canvas.width - x) / 80, 1)
          const edgeFadeY = Math.min(y / 80, (canvas.height - y) / 80, 1)
          const edgeFade = edgeFadeX * edgeFadeY

          const finalOpacity = opacity * edgeFade

          if (finalOpacity > 0.05) {
            ctx.save()
            ctx.globalAlpha = finalOpacity

            const colorRatio = x / canvas.width
            const r = Math.floor(theme.from[0] + (theme.to[0] - theme.from[0]) * colorRatio)
            const g = Math.floor(theme.from[1] + (theme.to[1] - theme.from[1]) * colorRatio)
            const b = Math.floor(theme.from[2] + (theme.to[2] - theme.from[2]) * colorRatio)
            ctx.fillStyle = `rgb(${r}, ${g}, ${b})`

            if (intensity > 0.4) {
              ctx.shadowBlur = size * 3
              ctx.shadowColor = `rgba(${r}, ${g}, ${b}, 0.8)`
            }

            ctx.beginPath()
            ctx.arc(x, y, size, 0, Math.PI * 2)
            ctx.fill()
            ctx.restore()
          }
        }
      }
    }

    const animate = () => {
      timeRef.current += 1
      drawEffect()
      animationRef.current = requestAnimationFrame(animate)
    }

    resizeCanvas()
    animate()

    window.addEventListener('resize', resizeCanvas)

    return () => {
      window.removeEventListener('resize', resizeCanvas)
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [vibrant, color])

  return (
    <canvas
      ref={canvasRef}
      className={`dot-matrix-canvas ${className}`}
    />
  )
}
