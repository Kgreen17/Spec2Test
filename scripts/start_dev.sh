#!/usr/bin/env zsh
# start_dev.sh - start the dev stack for Spec2Test
# Usage: ./scripts/start_dev.sh [local|docker]
# Environment overrides:
#   SKIP_PIP=1  -> skip `pip install -r requirements.txt`
#   NO_FRONTEND=1 -> don't start the frontend
#   NO_CELERY=1 -> don't start celery worker
#   NO_REDIS=1 -> don't start redis (assume external redis)

set -euo pipefail
REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
VENV_DIR="$REPO_ROOT/.venv"
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"
mkdir -p "$REPO_ROOT/uploads" "$REPO_ROOT/reports"

MODE=${1:-local}
SKIP_PIP=${SKIP_PIP:-0}
NO_FRONTEND=${NO_FRONTEND:-0}
NO_CELERY=${NO_CELERY:-0}
NO_REDIS=${NO_REDIS:-0}
REDIS_CONTAINER_NAME="spec2test-redis"

function info() { echo "[INFO]" "$@" }
function warn() { echo "[WARN]" "$@" }
function err() { echo "[ERROR]" "$@" >&2 }

if [[ "$MODE" == "docker" ]]; then
  info "Starting stack with docker-compose..."
  cd "$REPO_ROOT"
  docker-compose up --build
  exit $?
fi

# Local mode
info "Starting local dev stack in: $REPO_ROOT"

# 1) Ensure virtualenv
if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating venv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

if [[ "$SKIP_PIP" != "1" ]]; then
  info "Installing Python requirements (may take a while)"
  pip install --upgrade pip
  if [[ -f "$REPO_ROOT/requirements.txt" ]]; then
    pip install -r "$REPO_ROOT/requirements.txt"
  else
    warn "requirements.txt not found; skipping pip install"
  fi
else
  info "SKIP_PIP=1; not installing python packages"
fi

# 2) Redis (if needed)
if [[ "$NO_REDIS" != "1" ]]; then
  if command -v redis-server >/dev/null 2>&1; then
    info "redis-server found; attempting to start (daemon mode)"
    # Try to start redis in background if not already running
    if ! nc -z localhost 6379 >/dev/null 2>&1; then
      # Try to start via brew services if available
      if command -v brew >/dev/null 2>&1 && brew services list | grep redis | grep started >/dev/null 2>&1; then
        info "Redis already started by brew"
      else
        if [[ "$(uname)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
          info "Starting redis via brew services"
          brew services start redis || warn "brew services start failed; trying redis-server --daemonize yes"
        fi
        if ! nc -z localhost 6379 >/dev/null 2>&1; then
          info "Starting redis-server --daemonize yes"
          redis-server --daemonize yes || warn "redis-server daemonize failed"
        fi
      fi
    else
      info "Redis already listening on localhost:6379"
    fi
  else
    # Fallback to docker container
    if command -v docker >/dev/null 2>&1; then
      if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER_NAME}$"; then
        info "Redis container $REDIS_CONTAINER_NAME already running"
      else
        if docker ps -a --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER_NAME}$"; then
          info "Starting existing redis container"
          docker start "$REDIS_CONTAINER_NAME"
        else
          info "Starting redis in Docker ($REDIS_CONTAINER_NAME)"
          docker run -d --name "$REDIS_CONTAINER_NAME" -p 6379:6379 redis:7.2
        fi
      fi
    else
      warn "Docker not available; cannot start Redis fallback container. Please install Redis or set NO_REDIS=1 to skip starting Redis."
    fi
  fi
else
  info "NO_REDIS=1 set; assuming Redis is managed externally"
fi

# Helper to launch background process and record pid/log
function start_bg() {
  local name=$1
  shift
  local cmd=("$@")
  local logfile="$LOG_DIR/${name}.log"
  info "Starting $name -> log: $logfile"
  nohup "${cmd[@]}" > "$logfile" 2>&1 &
  local pid=$!
  echo $pid > "$LOG_DIR/${name}.pid"
  info "$name started with PID $pid"
}

# 3) Start uvicorn backend
UVICORN_LOG="$LOG_DIR/uvicorn.log"
if pgrep -f "uvicorn backend.app" >/dev/null 2>&1; then
  info "uvicorn seems already running"
else
  start_bg uvicorn python3 -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
fi

# 4) Start Celery worker (if not disabled)
if [[ "$NO_CELERY" != "1" ]]; then
  if command -v celery >/dev/null 2>&1; then
    if pgrep -f "celery -A backend.celery_app" >/dev/null 2>&1; then
      info "Celery worker already running"
    else
      start_bg celery celery -A backend.celery_app.celery_app worker --loglevel=info
    fi
  else
    warn "Celery command not found. Install celery to run workers or set NO_CELERY=1 to skip."
  fi
else
  info "NO_CELERY=1 set; skipping worker startup"
fi

# 5) Start frontend unless disabled
if [[ "$NO_FRONTEND" != "1" ]]; then
  if command -v npm >/dev/null 2>&1; then
    if pgrep -f "next dev" >/dev/null 2>&1; then
      info "Frontend dev server seems already running"
    else
      info "Starting frontend (Next.js dev server)"
      pushd "$REPO_ROOT/frontend" >/dev/null
      if [[ ! -d node_modules ]]; then
        info "Installing frontend npm deps (first run)"
        npm install
      fi
      start_bg frontend npm run dev
      popd >/dev/null
    fi
  else
    warn "npm not found; skipping frontend start"
  fi
else
  info "NO_FRONTEND=1 set; skipping frontend startup"
fi

info "Started services. Logs are in: $LOG_DIR"
info "To stop: kill \\$(cat $LOG_DIR/uvicorn.pid || echo 'pid') \\$(cat $LOG_DIR/celery.pid || echo 'pid') \\$(cat $LOG_DIR/frontend.pid || echo 'pid')"
info "Or run: pkill -f 'uvicorn backend.app' ; pkill -f 'celery -A backend.celery_app' ; pkill -f 'next dev'"

# Keep the script running to show tail of logs if desired
if [[ "${TAIL_LOGS:-1}" == "1" ]]; then
  echo
  echo "Tailing uvicorn log (Ctrl-C to exit, services continue running)..."
  tail -n +1 -f "$LOG_DIR/uvicorn.log"
fi

