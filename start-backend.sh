#!/bin/bash
cd "$(dirname "$0")/backend"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt
python -m playwright install chromium 2>/dev/null || true

echo "Starting Flask backend on http://localhost:5001 ..."
python app.py
