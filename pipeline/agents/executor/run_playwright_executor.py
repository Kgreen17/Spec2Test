"""CLI to run the Playwright executor against a generated plan.

Usage:
  python3 pipeline/agents/executor/run_playwright_executor.py --plan generated_test_plan.json --out reports/generated_test_plan_report.json [--simulate]
"""
from pathlib import Path
import argparse
import json
import sys

from pipeline.agents.executor.playwright_runner import run_steps


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', default='generated_test_plan.json')
    parser.add_argument('--out', default='reports/generated_test_plan_report.json')
    parser.add_argument('--simulate', action='store_true', help='Run in simulate-only mode (no Playwright)')
    parser.add_argument('--headless', action='store_true', help='Run real Playwright in headless mode (if available)')
    args = parser.parse_args(argv)

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print('Plan file not found:', plan_path)
        sys.exit(2)

    data = json.loads(plan_path.read_text())
    # Support both shapes: {"plan": {...}} or top-level plan {...}
    if isinstance(data, dict) and 'plan' in data and isinstance(data['plan'], dict):
        steps = data['plan'].get('steps', [])
    else:
        steps = data.get('steps', [])

    rpt = run_steps(steps, out_report=args.out, headless=args.headless, simulate_only=args.simulate)
    summary = rpt.get('summary', {})
    print(f"Summary: pass={summary.get('pass')} fail={summary.get('fail')} skipped={summary.get('skipped')} total={summary.get('total')}")
    print('Wrote report to', args.out)


if __name__ == '__main__':
    main()

