#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p logs
echo "Starting UI at http://localhost:8000"
nohup python3 -m uvicorn web.app:app --host 0.0.0.0 --port 8000 > logs/ui.log 2>&1 &
PID=$!
sleep 1
if which open >/dev/null 2>&1; then
  open "http://localhost:8000"
else
  echo "Open your browser to http://localhost:8000"
fi
echo "UI started (pid=$PID). To stop: kill $PID"

