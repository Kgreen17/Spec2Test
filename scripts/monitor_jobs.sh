#!/usr/bin/env bash
# Simple job monitor: poll the local UI /jobs endpoint, stream status and logs,
# and when a job finishes run /open-allure to generate the report.
set -euo pipefail
UI=${UI:-http://127.0.0.1:8000}
POLL_INTERVAL=${POLL_INTERVAL:-3}
SEEN_JOBS_FILE="logs/seen_jobs.txt"
mkdir -p logs
touch "$SEEN_JOBS_FILE"

echo "Starting monitor: polling $UI/jobs every ${POLL_INTERVAL}s"

while true; do
  jobs_json=$(curl -sS "$UI/jobs" || echo "{}")
  # extract job ids
  job_ids=$(python3 - <<'PY'
import sys, json
try:
    d=json.load(sys.stdin)
    print('\n'.join(d.keys()))
except Exception:
    pass
PY
<<<"$jobs_json")

  for jid in $job_ids; do
    if [ -z "$jid" ]; then
      continue
    fi

    if grep -q "^$jid$" "$SEEN_JOBS_FILE" 2>/dev/null; then
      # check current status
      status=$(curl -sS "$UI/jobs" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('$jid',{}).get('status',''))")
      echo "[$(date +'%T')] job $jid status: $status"

      if [[ "$status" == "finished" || "$status" == "failed" ]]; then
        echo "---- Fetching logs for $jid ----"
        curl -sS "$UI/jobs/$jid/logs" || true

        if [[ "$status" == "finished" ]]; then
          echo "Attempting to generate/open Allure report for job $jid..."
          # Call open-allure and save response
          http_code=$(curl -s -o /tmp/_open_allure_resp.json -w "%{http_code}" -X POST "$UI/open-allure" || true)
          if [ -f /tmp/_open_allure_resp.json ]; then
            cat /tmp/_open_allure_resp.json || true
          fi

          # open index if exists
          if [ -f "allure-report/index.html" ]; then
            if which open >/dev/null 2>&1; then
              open "http://127.0.0.1:8000/allure-report/index.html"
            else
              echo "Allure report available at http://127.0.0.1:8000/allure-report/index.html"
            fi
          else
            echo "No allure-report/index.html found yet. Check logs or generate manually."
          fi
        fi

        # mark job processed (append to seen file so we don't repeat)
        if ! grep -q "^$jid$" "$SEEN_JOBS_FILE" 2>/dev/null; then
          echo "$jid" >> "$SEEN_JOBS_FILE"
        fi
      fi
    else
      # new job discovered
      echo "[$(date +'%T')] New job: $jid"
      echo "$jid" >> "$SEEN_JOBS_FILE"
      status=$(curl -sS "$UI/jobs" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('$jid',{}).get('status',''))")
      echo "[$(date +'%T')] job $jid status: $status"
    fi
  done

  sleep $POLL_INTERVAL
done

