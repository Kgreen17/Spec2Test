#!/usr/bin/env bash
# scripts/run_all.sh
# Starts the Docker Compose stack (backend, celery, redis, frontend), waits for health, submits the docs job,
# polls for completion, and opens the Allure report if generated.

set -euo pipefail
IFS=$'\n\t'

# Config
BACKEND_URL=${BACKEND_URL:-http://localhost:8000}
FRONTEND_URL=${FRONTEND_URL:-http://localhost:3000}
DOCS_SOURCE=${DOCS_SOURCE:-docs}
POLL_INTERVAL=${POLL_INTERVAL:-2}
POLL_RETRIES=${POLL_RETRIES:-120}  # ~4 minutes
# Detect which docker compose command is available: prefer `docker compose`, fall back to `docker-compose`
if [ -n "${DOCKER_COMPOSE_CMD-}" ]; then
  : # user provided DOCKER_COMPOSE_CMD
else
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker-compose"
  else
    echo "Error: neither 'docker compose' nor 'docker-compose' is available on PATH. Please install Docker Compose or use DOCKER_COMPOSE_CMD env var." >&2
    exit 1
  fi
fi

# Split DOCKER_COMPOSE_CMD into array to allow multi-word commands safely (e.g. "docker compose")
IFS=' ' read -r -a DCMD <<< "$DOCKER_COMPOSE_CMD"

usage() {
  cat <<EOF
Usage: $0
Environment variables:
  BACKEND_URL    (default: $BACKEND_URL)
  FRONTEND_URL   (default: $FRONTEND_URL)
  DOCS_SOURCE    (default: $DOCS_SOURCE)
  POLL_INTERVAL  (seconds between status checks, default: $POLL_INTERVAL)
  POLL_RETRIES   (how many polls before timing out, default: $POLL_RETRIES)

This script will:
  - bring up the Docker Compose stack (build + detached)
  - wait for backend and frontend health endpoints
  - POST the docs source to the backend /api/upload
  - poll /api/status/<job_id> until the job completes
  - print job result JSON and open Allure report if present
EOF
}

# helper: wait for HTTP 200 on a URL
wait_for_health() {
  local url=$1
  local name=$2
  local attempts=0
  echo "Waiting for ${name} health at ${url}"
  while [ $attempts -lt $POLL_RETRIES ]; do
    if curl -sSf "$url" >/dev/null 2>&1; then
      echo "${name} healthy after $attempts attempts"
      return 0
    fi
    attempts=$((attempts+1))
    sleep $POLL_INTERVAL
  done
  echo "Timed out waiting for ${name} at ${url}" >&2
  return 1
}

# bring up compose
echo "Bringing up Docker Compose stack (may rebuild images)..."
"${DCMD[@]}" up --build -d

# wait for backend
if ! wait_for_health "$BACKEND_URL/api/health" "backend"; then
  echo "Backend didn't become healthy. Check 'docker compose logs backend'" >&2
  exit 2
fi

# wait for frontend (best-effort)
if wait_for_health "$FRONTEND_URL/api/health" "frontend"; then
  echo "Frontend is healthy"
else
  echo "Frontend health check failed or timed out; continuing (frontend is optional)"
fi

# Submit job
echo "Submitting docs source '${DOCS_SOURCE}' to backend..."
upload_resp=$(curl -sS -X POST -H "Content-Type: application/json" -d "{\"url\": \"${DOCS_SOURCE}\", \"options\": {}}" "$BACKEND_URL/api/upload" || true)
if [ -z "$upload_resp" ]; then
  echo "No response from backend /api/upload" >&2
  exit 3
fi

echo "Upload response: $upload_resp"

# Try to extract job_id using jq, then python, then sed fallback
job_id=""
if command -v jq >/dev/null 2>&1; then
  job_id=$(printf '%s' "$upload_resp" | jq -r '.job_id // empty' 2>/dev/null || true)
fi
if [ -z "$job_id" ]; then
  job_id=$(printf '%s' "$upload_resp" | python3 -c 'import sys,json
try:
  print(json.loads(sys.stdin.read()).get("job_id",""))
except Exception:
  print("")' 2>/dev/null || true)
fi
if [ -z "$job_id" ]; then
  # fallback: crude grep/sed
  job_id=$(printf '%s' "$upload_resp" | tr -d '\n' | sed -E 's/.*"job_id"\s*:\s*"([^"]+)".*/\1/;t;d' 2>/dev/null || true)
fi
if [ -z "$job_id" ]; then
  echo "Failed to extract job_id from response: $upload_resp" >&2
  exit 4
fi

echo "Submitted job_id: $job_id"

# Poll status until completion
jr="reports/job_${job_id}/job_result_${job_id}.json"
for i in $(seq 1 $POLL_RETRIES); do
  status_json=$(curl -sS "$BACKEND_URL/api/status/$job_id" || echo '{}')
  echo "[poll $i] $status_json"
  state=$(printf '%s' "$status_json" | python3 - <<'PY'
import sys, json
try:
  d=json.load(sys.stdin)
  print(d.get('status') or '')
except Exception:
  print('')
PY
)
  case "$state" in
    SUCCESS|COMPLETED|completed|success)
      echo "Job finished with status: $state"
      break
      ;;
    ERROR|FAILURE|FAILED)
      echo "Job failed with status: $state" >&2
      break
      ;;
  esac
  sleep $POLL_INTERVAL
done

# Show job_result (prefer the persisted file if available)
if [ -f "$jr" ]; then
  echo "\n=== job_result file: $jr ==="
  sed -n '1,400p' "$jr"
else
  echo "No job_result file at $jr. Fetching status JSON from backend as fallback:"
  curl -sS "$BACKEND_URL/api/status/$job_id" | python3 -m json.tool || true
fi

# Open Allure report if exists
ar="reports/job_${job_id}/allure-report/index.html"
if [ -f "$ar" ]; then
  echo "Opening Allure report: $ar"
  open "$ar" || echo "Allure report generated at: $ar"
else
  if [ -d "reports/job_${job_id}/allure-results" ]; then
    echo "Allure results available at reports/job_${job_id}/allure-results. If you have Allure CLI installed, generate HTML with:\n  allure generate reports/job_${job_id}/allure-results -o reports/job_${job_id}/allure-report --clean"
  else
    echo "No Allure results found for job ${job_id}"
  fi
fi

echo "Done."

