#!/bin/bash
# Clawome — one-command start
# Usage: ./start.sh

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "🦞 Starting Clawome..."
echo ""

# ── Load .env if present ──
if [ -f "$ROOT/.env" ]; then
  echo "[env] Loading .env"
  set -a
  source "$ROOT/.env"
  set +a
fi

# ── Backend setup ──
cd "$ROOT/backend"

if [ ! -d "venv" ]; then
  echo "[backend] Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate

# Install dependencies only on first run (or if requirements change)
if [ ! -f "venv/.deps_installed" ] || [ requirements.txt -nt "venv/.deps_installed" ]; then
  echo "[backend] Installing dependencies..."
  pip install -q -r requirements.txt
  # Install Playwright browser
  python -m playwright install chromium 2>/dev/null || echo "[backend] Playwright chromium already installed"
  touch "venv/.deps_installed"
else
  echo "[backend] Dependencies already installed, skipping."
fi

echo "[backend] Starting Flask API on http://localhost:5001"
python app.py &
BACKEND_PID=$!

# ── Frontend setup ──
cd "$ROOT/frontend"

if [ ! -d "node_modules" ]; then
  echo "[frontend] Installing dependencies..."
  npm install
fi

echo "[frontend] Starting dashboard on http://localhost:5173"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo "  Clawome is running!"
echo "  Dashboard:  http://localhost:5173"
echo "  API:        http://localhost:5001"
echo "  Press Ctrl+C to stop"
echo "=========================================="
echo ""

# Graceful shutdown
cleanup() {
  echo ""
  echo "Shutting down..."
  kill $BACKEND_PID 2>/dev/null
  kill $FRONTEND_PID 2>/dev/null
  wait 2>/dev/null
  echo "Stopped."
}
trap cleanup INT TERM

wait
