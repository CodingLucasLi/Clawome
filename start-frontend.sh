#!/bin/bash
cd "$(dirname "$0")/frontend"

if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install
fi

echo "Starting Vite dev server on http://localhost:5173 ..."
npm run dev
