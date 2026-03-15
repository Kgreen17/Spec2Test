#!/usr/bin/env bash
set -euo pipefail

# Diagnostic Docker Compose runner for this repo
# Features:
# - Detect docker / docker-compose (v1 or v2)
# - Validate compose file
# - Optional --dry-run, --no-start, --project-name, --debug
# - Pre-start port conflict checks (best-effort via small Python parser)
# - Start stack, wait for services, open frontend, tail logs
# - On failures collect diagnostics into logs/<timestamp>/

COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml}
BACKEND_URL=${BACKEND_URL:-http://localhost:8000}
FRONTEND_URL=${FRONTEND_URL:-http://localhost:3000}
ALLURE_RESULTS_DIR=${ALLURE_RESULTS_DIR:-./allure-results}
ALLURE_REPORT_DIR=${ALLURE_REPORT_DIR:-./allure-report}
PROJECT_NAME=${PROJECT_NAME:-spec2test}
DRY_RUN=0
NO_START=0
DEBUG=0
GENERATE_ALLURE=0
OPEN_CMD=""
TS=$(date -u +"%Y%m%dT%H%M%SZ")
LOG_DIR="logs/run_all_docker_$TS"
ALLURE_WAIT_TIMEOUT=${ALLURE_WAIT_TIMEOUT:-300}
ALLURE_POLL_INTERVAL=${ALLURE_POLL_INTERVAL:-5}

usage(){
  cat <<USAGE
Usage: $0 [--dry-run] [--no-start] [--project-name NAME] [--debug]

Options:
  --dry-run        Print checks and planned commands but don't start containers
  --no-start       Create resources but do not start containers (non-destructive)
  --project-name   Override docker compose project name (default: ${PROJECT_NAME})
  --generate-allure Generate Allure report if results are present (uses local 'allure' CLI or Docker image fallback)
  --debug          Print more verbose debugging info
  -h, --help       Show this help
USAGE
}

while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift;;
    --no-start) NO_START=1; shift;;
    --project-name) PROJECT_NAME="$2"; shift 2;;
    --generate-allure) GENERATE_ALLURE=1; shift;;
    --debug) DEBUG=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 2;;
  esac
done

if command -v open >/dev/null 2>&1; then
  OPEN_CMD="open"
elif command -v xdg-open >/dev/null 2>&1; then
  OPEN_CMD="xdg-open"
fi

# Detect docker compose command. Use an array to avoid word-splitting when using
# the 'docker compose' subcommand (two words).
DC_CMD_ARRAY=()
DC_CMD_STR=""
if command -v docker-compose >/dev/null 2>&1; then
  DC_CMD_ARRAY=(docker-compose)
  DC_CMD_STR="docker-compose"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DC_CMD_ARRAY=(docker compose)
  DC_CMD_STR="docker compose"
fi

echo "Using compose file: ${COMPOSE_FILE}"
if [ ${#DC_CMD_ARRAY[@]} -eq 0 ]; then
  echo "ERROR: docker compose not found (neither 'docker compose' nor 'docker-compose'). Install Docker Desktop or docker-compose."
  exit 1
fi

echo "Using compose command: ${DC_CMD_STR}"

echo "Performing basic environment checks..."
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker CLI not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon doesn't appear to be running or cannot be reached. On macOS start Docker Desktop and try again."
  if [ $DRY_RUN -eq 1 ]; then
    echo "(dry-run) would continue after docker is available"
  else
    exit 1
  fi
fi

echo "Validating compose file..."
set +e
"${DC_CMD_ARRAY[@]}" -f "${COMPOSE_FILE}" config >/dev/null 2>&1
cfg_rc=$?
set -e
if [ $cfg_rc -ne 0 ]; then
  echo "ERROR: '${DC_CMD_STR} -f ${COMPOSE_FILE} config' failed. Check your compose file for syntax or missing env variables."
  "${DC_CMD_ARRAY[@]}" -f "${COMPOSE_FILE}" config || true
  exit 2
fi

echo "Compose file looks valid. (Dry-run=${DRY_RUN}, No-start=${NO_START})"

# Pre-start: attempt to detect host ports specified in compose so we can check for conflicts
echo "Detecting host ports defined in ${COMPOSE_FILE} (best-effort)..."
HOST_PORTS=$(python3 - <<'PY'
import sys, yaml, re
fn='docker-compose.yml'
try:
    with open(fn) as f:
        d=yaml.safe_load(f)
except Exception:
    sys.exit(0)
ports=set()
services=d.get('services',{}) if isinstance(d,dict) else {}
for svc, conf in services.items():
    p=conf.get('ports') if conf else None
    if not p: continue
    for entry in p:
        if isinstance(entry,int):
            ports.add(str(entry))
        elif isinstance(entry,str):
            # handle '8000:8000', '127.0.0.1:8000:8000', '8000'
            parts=entry.split(':')
            # take the first numeric part from left
            for part in parts:
                m=re.match(r".*?(\d+)$", part)
                if m:
                    ports.add(m.group(1))
                    break
        elif isinstance(entry,dict):
            published=entry.get('published')
            if published:
                ports.add(str(published))
print('\n'.join(sorted(ports)))
PY
)

if [ -n "${HOST_PORTS}" ]; then
  echo "Found host ports:"
  echo "${HOST_PORTS}" | sed -e 's/^/  /'
  echo "Checking for local processes listening on those ports..."
  for p in ${HOST_PORTS}; do
    if lsof -nP -iTCP:${p} -sTCP:LISTEN >/dev/null 2>&1; then
      echo "Port ${p} appears in use locally by:"
      lsof -nP -iTCP:${p} -sTCP:LISTEN | sed -n '1,5p'
      echo "If this is unexpected stop the process or change the port mapping in ${COMPOSE_FILE}."
    else
      [ $DEBUG -eq 1 ] && echo "Port ${p} seems free on host"
    fi
  done
else
  echo "No host ports detected in ${COMPOSE_FILE} (or parsing failed)."
fi

if [ $DRY_RUN -eq 1 ]; then
  echo "Dry-run: exiting after checks. To actually bring up the stack run without --dry-run."
  exit 0
fi

# Build start command
START_CMD=( "${DC_CMD_ARRAY[@]}" -f "${COMPOSE_FILE}" --project-name "${PROJECT_NAME}" up --build -d )
if [ $NO_START -eq 1 ]; then
  START_CMD=( "${DC_CMD_ARRAY[@]}" -f "${COMPOSE_FILE}" --project-name "${PROJECT_NAME}" create )
fi

echo "Running: ${START_CMD[*]}"
"${START_CMD[@]}"

echo "Gathering runtime status..."
mkdir -p "${LOG_DIR}"
echo "Timestamp: ${TS}" > "${LOG_DIR}/summary.txt"
docker version > "${LOG_DIR}/docker_version.txt" 2>&1 || true
docker info > "${LOG_DIR}/docker_info.txt" 2>&1 || true
"${DC_CMD_ARRAY[@]}" -f "${COMPOSE_FILE}" ps > "${LOG_DIR}/compose_ps.txt" 2>&1 || true
docker ps -a --format '{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}' > "${LOG_DIR}/docker_ps.txt" 2>&1 || true

echo "Collecting logs from compose (tail 500 lines)..."
"${DC_CMD_ARRAY[@]}" -f "${COMPOSE_FILE}" logs --no-color --timestamps --tail=500 > "${LOG_DIR}/compose_logs.txt" 2>&1 || true

echo "Inspecting individual containers and collecting logs..."
container_ids=$(docker ps -aq)
for cid in ${container_ids}; do
  name=$(docker inspect -f '{{.Name}}' ${cid} 2>/dev/null | sed 's#/##') || name=${cid}
  docker inspect ${cid} > "${LOG_DIR}/inspect_${name}.json" 2>&1 || true
  docker logs --timestamps --tail=1000 ${cid} > "${LOG_DIR}/container_${name}_logs.txt" 2>&1 || true
done

echo "Analyzing container statuses..."
exited=$(docker ps -a --filter "status=exited" --format '{{.ID}}\t{{.Names}}\t{{.Status}}' || true)
if [ -n "${exited}" ]; then
  echo "Found exited containers:"
  echo "${exited}"
  echo "Last few lines from each exited container's logs (stored in ${LOG_DIR}):"
  for cid in $(docker ps -a --filter "status=exited" -q); do
    name=$(docker inspect -f '{{.Name}}' ${cid} 2>/dev/null | sed 's#/##') || name=${cid}
    echo "---- ${name} (exit code & brief inspect) ----"
    docker inspect -f 'ExitCode={{.State.ExitCode}} Error={{.State.Error}}' ${cid} || true
    echo "---- last 200 log lines ----"
    tail -n 200 "${LOG_DIR}/container_${name}_logs.txt" || true
  done
fi

restarting=$(docker ps -a --filter "status=running" --format '{{.ID}}\t{{.Names}}\t{{.Status}}' | grep -i restart || true)
if [ -n "${restarting}" ]; then
  echo "Some containers are restarting frequently (see compose logs and individual logs in ${LOG_DIR})."
fi

echo "Diagnostics captured under ${LOG_DIR}"

echo
echo "Quick commands and next steps:"
echo "  Stop everything: ${DC_CMD_STR} -f ${COMPOSE_FILE} --project-name ${PROJECT_NAME} down"
echo "  View live logs: ${DC_CMD_STR} -f ${COMPOSE_FILE} logs -f"
echo "  Show compose status: ${DC_CMD_STR} -f ${COMPOSE_FILE} ps"
echo
echo "Waiting for backend at ${BACKEND_URL} ..."
timeout=120
elapsed=0
interval=2
until curl -sSf "${BACKEND_URL}" >/dev/null 2>&1 || [ $elapsed -ge $timeout ]; do
  sleep $interval
  elapsed=$((elapsed + interval))
  echo -n "."
done
echo
if [ $elapsed -ge $timeout ]; then
  echo "Warning: backend did not respond at ${BACKEND_URL} after ${timeout}s. Check ${LOG_DIR}/compose_logs.txt and container logs."
else
  echo "Backend appears up."
fi

echo "Waiting for frontend at ${FRONTEND_URL} ..."
timeout=60
elapsed=0
until curl -sSf "${FRONTEND_URL}" >/dev/null 2>&1 || [ $elapsed -ge $timeout ]; do
  sleep $interval
  elapsed=$((elapsed + interval))
  echo -n "."
done
echo
if [ $elapsed -ge $timeout ]; then
  echo "Warning: frontend did not respond at ${FRONTEND_URL} after ${timeout}s. Check ${LOG_DIR}/compose_logs.txt and container logs."
else
  echo "Frontend appears up."
  if [ -n "${OPEN_CMD}" ]; then
    echo "Opening frontend in default browser..."
    ${OPEN_CMD} "${FRONTEND_URL}" || true
  else
    echo "Open ${FRONTEND_URL} in your browser."
  fi
fi

echo "Tailing compose logs (CTRL-C to stop) — further instructions below."

# Function: generate Allure report using local CLI if present, otherwise Docker image fallback
generate_allure(){
  if [ ! -d "${ALLURE_RESULTS_DIR}" ]; then
    echo "No allure results directory found at ${ALLURE_RESULTS_DIR}. Skipping Allure generation."
    return 0
  fi
  # check if directory has files
  if [ -z "$(ls -A "${ALLURE_RESULTS_DIR}" 2>/dev/null)" ]; then
    echo "Allure results directory ${ALLURE_RESULTS_DIR} is empty. Skipping Allure generation."
    return 0
  fi

  echo "Generating Allure report from ${ALLURE_RESULTS_DIR} to ${ALLURE_REPORT_DIR}..."
  if command -v allure >/dev/null 2>&1; then
    echo "Using local 'allure' CLI to generate report..."
    allure generate "${ALLURE_RESULTS_DIR}" -o "${ALLURE_REPORT_DIR}" --clean || {
      echo "Allure CLI failed to generate report locally."
      return 1
    }
  elif command -v docker >/dev/null 2>&1; then
    echo "Local 'allure' CLI not found; falling back to Docker image (ghcr.io/allure-framework/allure)..."
    mkdir -p "${ALLURE_REPORT_DIR}"
    pwd_dir=$(pwd)
    docker run --rm -v "${pwd_dir}/${ALLURE_RESULTS_DIR}:/results" -v "${pwd_dir}/${ALLURE_REPORT_DIR}:/report" ghcr.io/allure-framework/allure:2.21.0 generate /results -o /report --clean || {
      echo "Docker-based Allure generation failed. Ensure Docker can run containers and the image exists."
      return 1
    }
  else
    echo "No 'allure' CLI and Docker not available to run a fallback image. Install Allure CLI or enable Docker."
    return 1
  fi

  echo "Allure report generated at ${ALLURE_REPORT_DIR}".
  if [ -n "${OPEN_CMD}" ]; then
    echo "Opening Allure report in default browser..."
    ${OPEN_CMD} "${ALLURE_REPORT_DIR}/index.html" || true
  else
    echo "Open ${ALLURE_REPORT_DIR}/index.html in your browser to view the report."
  fi
}

if [ ${GENERATE_ALLURE} -eq 1 ]; then
  echo "--generate-allure passed: will attempt to generate Allure report once results appear (timeout=${ALLURE_WAIT_TIMEOUT}s)..."
  # If results dir is empty, poll for files for up to ALLURE_WAIT_TIMEOUT seconds
  elapsed=0
  while [ -z "$(ls -A "${ALLURE_RESULTS_DIR}" 2>/dev/null)" ] && [ $elapsed -lt ${ALLURE_WAIT_TIMEOUT} ]; do
    sleep ${ALLURE_POLL_INTERVAL}
    elapsed=$((elapsed + ALLURE_POLL_INTERVAL))
    echo -n "."
  done
  echo
  if [ -z "$(ls -A "${ALLURE_RESULTS_DIR}" 2>/dev/null)" ]; then
    echo "No Allure results found in ${ALLURE_RESULTS_DIR} after ${ALLURE_WAIT_TIMEOUT}s. Skipping generation."
  else
    echo "Allure results detected; generating report now..."
    generate_allure || echo "Allure generation failed; see messages above."
  fi
fi

"${DC_CMD_ARRAY[@]}" -f "${COMPOSE_FILE}" logs -f

