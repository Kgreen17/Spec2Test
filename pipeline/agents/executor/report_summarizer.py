"""Simple summarizer for executor reports.

Produces a human-friendly markdown summary of the results and lists failed steps with screenshots.
"""
from pathlib import Path
from typing import Dict, Any


def summarize_report(report_path: Path, out_md: Path = None) -> str:
    data = report_path.exists() and report_path.read_text() or None
    if not data:
        return 'Report not found.'
    import json
    r = json.loads(data)
    summary = r.get('summary', {})
    lines = []
    lines.append(f"# Execution Summary\n")
    lines.append(f"Total steps: {summary.get('total')}  ")
    lines.append(f"Passed: {summary.get('pass')}  ")
    lines.append(f"Failed: {summary.get('fail')}  ")
    lines.append(f"Skipped: {summary.get('skipped')}  \n")

    if summary.get('fail'):
        lines.append('## Failed steps')
        for s in r.get('results', []):
            if s.get('status') == 'FAIL':
                lines.append(f"- Step {s.get('id')}: {s.get('action')} {s.get('target')} — {s.get('error')}")
                if s.get('screenshot'):
                    lines.append(f"  - Screenshot: {s.get('screenshot')}")
    if out_md:
        out_md.write_text('\n'.join(lines))
    return '\n'.join(lines)

