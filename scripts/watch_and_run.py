"""Simple watcher that detects changes to PDFs in the `docs/` folder and runs the full pipeline.

Usage:
  # default: simulate executor (safe)
  python3 scripts/watch_and_run.py

  # run real executor (Playwright) when changes are detected
  REAL=1 python3 scripts/watch_and_run.py

The script polls every 5 seconds and runs:
  python3 main.py --save out_embeddings.json --generate-tests --run-executor --executor-out reports/generated_test_plan_report_real.json --allure-generate

By default it runs the executor in simulate mode to avoid destructive system operations.
"""
import time
import subprocess
from pathlib import Path
import os
import sys

POLL_INTERVAL = 5
DOCS_DIR = Path(__file__).resolve().parents[1] / 'docs'
MAIN_PY = Path(__file__).resolve().parents[1] / 'main.py'

if not DOCS_DIR.exists():
    print('Docs directory not found:', DOCS_DIR)
    sys.exit(1)

print('Watching', DOCS_DIR, 'for PDF changes...')

# track last modified times for files
def snapshot():
    snaps = {}
    for p in DOCS_DIR.glob('**/*'):
        if p.is_file() and p.suffix.lower() in ('.pdf', '.docx', '.txt'):
            snaps[str(p)] = p.stat().st_mtime
    return snaps

last = snapshot()

while True:
    try:
        time.sleep(POLL_INTERVAL)
        cur = snapshot()
        if cur != last:
            print('Detected change in docs. Running pipeline...')
            # Build command
            simulate = not bool(os.environ.get('REAL'))
            cmd = [sys.executable, str(MAIN_PY), '--save', 'out_embeddings.json', '--generate-tests', '--run-executor', '--executor-out', 'reports/generated_test_plan_report_real.json', '--allure-generate']
            if simulate:
                cmd.append('--simulate-executor')
            print('Running:', ' '.join(cmd))
            subprocess.run(cmd)
            last = cur
        # else continue
    except KeyboardInterrupt:
        print('Watcher stopped by user')
        break
    except Exception as e:
        print('Watcher error:', e)
        time.sleep(POLL_INTERVAL)

