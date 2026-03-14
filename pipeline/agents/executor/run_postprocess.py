"""Run selector suggester, plan->playwright converter, and report summarizer for a generated plan.

Usage:
  python3 pipeline/agents/executor/run_postprocess.py --plan generated_test_plan.json --embeddings out_embeddings.json
"""
import argparse
from pathlib import Path
import json
import sys


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', default='generated_test_plan.json')
    parser.add_argument('--embeddings', default='out_embeddings.json')
    parser.add_argument('--out-script', default='generated_playwright_test.py')
    parser.add_argument('--out-summary', default='reports/execution_summary.md')
    args = parser.parse_args(argv)

    plan_p = Path(args.plan)
    emb_p = Path(args.embeddings)
    if not plan_p.exists():
        print('Plan not found:', plan_p)
        sys.exit(2)
    if not emb_p.exists():
        print('Embeddings file not found:', emb_p)
        sys.exit(2)

    plan = json.loads(plan_p.read_text())
    emb = json.loads(emb_p.read_text())
    chunks = emb.get('chunks', [])

    # Selector suggestions
    try:
        from pipeline.agents.executor.selector_suggester import suggest_selectors
        suggestions = suggest_selectors(plan.get('plan', plan), chunks)
        print('Selector suggestions (step -> candidates):')
        for k,v in suggestions.items():
            print(k, '->', v)
    except Exception as e:
        print('Selector suggester failed:', e)

    # Convert to playwright script
    try:
        from pipeline.agents.executor.plan_to_playwright import generate_playwright_script
        out = Path(args.out_script)
        generate_playwright_script(plan.get('plan', plan), out)
        print('Generated Playwright script at', out)
    except Exception as e:
        print('Plan->Playwright conversion failed:', e)

    # Summarize the latest real report if present
    try:
        from pipeline.agents.executor.report_summarizer import summarize_report
        real_report = Path('reports/generated_test_plan_report_real.json')
        out_md = Path(args.out_summary)
        summary = summarize_report(real_report, out_md)
        print('Wrote summary to', out_md)
        print(summary)
    except Exception as e:
        print('Report summarizer failed:', e)

if __name__ == '__main__':
    main()

