#!/usr/bin/env bash
# Start the FastAPI backend (with auto-reload) and the Vite dev server
# together for local development. Ctrl+C stops both.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv in $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
fi

PYTHON="$VENV_DIR/bin/python"

if ! "$PYTHON" -c "import fastapi" >/dev/null 2>&1; then
  echo "Installing backend dependencies..."
  "$PYTHON" -m pip install -q -e .
fi

if [ ! -d "web/node_modules" ]; then
  echo "Installing frontend dependencies..."
  (cd web && npm install)
fi

cleanup() {
  echo
  echo "Stopping dev servers..."
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend  -> http://localhost:8000"
"$PYTHON" -m uvicorn server.main:app --reload --port 8000 &
BACKEND_PID=$!

echo "Starting frontend -> http://localhost:5173"
(cd web && npm run dev) &
FRONTEND_PID=$!

wait "$BACKEND_PID" "$FRONTEND_PID"
