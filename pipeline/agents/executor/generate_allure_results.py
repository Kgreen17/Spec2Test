"""Convert executor report JSON into Allure result JSON files.

Usage:
  python3 pipeline/agents/executor/generate_allure_results.py --report reports/generated_test_plan_report.json --out-dir allure-results

This will create a result file per step in the report in the Allure results folder. It also copies any referenced screenshots/attachments into the folder.
"""
import argparse
import json
from pathlib import Path
import uuid
import time
import shutil


def status_map(s):
    if s == 'PASS':
        return 'passed'
    if s == 'FAIL':
        return 'failed'
    if s == 'SKIPPED':
        return 'skipped'
    return 'broken'


def make_result(step, out_dir: Path):
    uid = str(uuid.uuid4())
    name = f"step-{step.get('id')} {step.get('action')} {step.get('target')}"
    start = int(time.time() * 1000)
    stop = start + 1
    status = status_map(step.get('status'))

    result = {
        'uid': uid,
        'name': name,
        'fullName': name,
        'status': status,
        'statusDetails': {'message': step.get('reason') or ''},
        'labels': [{'name': 'package', 'value': 'generated_plan'}, {'name': 'testClass', 'value': 'generated_plan'}],
        'links': [],
        'parameters': [],
        'steps': [],
        'attachments': [],
        'start': start,
        'stop': stop,
    }

    # Handle any screenshot attachments referenced in step
    if step.get('screenshot'):
        src = Path(step.get('screenshot'))
        if src.exists():
            dest_name = f"{uid}-attachment{src.suffix}"
            dest = out_dir / dest_name
            try:
                shutil.copy2(src, dest)
                result['attachments'].append({'source': dest_name, 'type': 'image/png', 'name': 'screenshot'})
            except Exception:
                pass

    # Write to file
    fname = out_dir / f"{uid}-result.json"
    fname.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return fname


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    parser.add_argument('--out-dir', default='allure-results')
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    if not report_path.exists():
        print('Report file not found:', report_path)
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(report_path.read_text())
    steps = data.get('results', [])

    created = []
    for s in steps:
        f = make_result(s, out_dir)
        created.append(str(f))

    print(f'Created {len(created)} allure result files in {out_dir}')
    return 0


if __name__ == '__main__':
    main()

