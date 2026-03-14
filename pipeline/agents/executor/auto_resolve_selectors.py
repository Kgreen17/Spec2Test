"""Auto-resolve DESCRIBE_TARGET placeholders using Playwright.

This script will:
- Load a generated test plan JSON
- Launch a headless browser and follow navigate steps to reach pages
- For steps with placeholder targets or underspecified selectors, attempt to find matching elements
  using metadata.note, expected/text, or value via text-match, id/class heuristics
- Produce a resolved plan JSON and an updated Playwright script

Usage:
  PYTHONPATH=. python3 pipeline/agents/executor/auto_resolve_selectors.py --plan generated_test_plan.json --out-plan generated_test_plan_resolved.json --out-script generated_playwright_test_resolved.py

Note: system actions are NOT executed. This only performs safe DOM queries and navigations.
"""
import argparse
import json
from pathlib import Path
import re
import time


def _shorten(s: str, n: int = 80):
    return (s[:n] + '...') if len(s) > n else s


def suggest_on_page(page, text_candidates):
    """Try to find selectors on the given Playwright page for any of the text_candidates.
    Returns the first found selector string, or None.
    """
    for cand in text_candidates:
        if not cand or len(cand.strip()) < 3:
            continue
        cand = cand.strip()
        # try exact text locator
        try:
            locator = page.locator(f"text=\"{cand}\"")
            if locator.count() > 0:
                return f"text={cand}"
        except Exception:
            pass
        # try substring text search (case-insensitive) by querying body text
        try:
            body = page.text_content('body') or ''
            if cand.lower() in (body or '').lower():
                # return a text= locator with a short snippet
                snippet = cand if len(cand) < 80 else cand[:80]
                return f"text={snippet}"
        except Exception:
            pass
        # try id/class heuristics
        try:
            ids = page.eval_on_selector_all('[id]', 'nodes => nodes.map(n => n.id)')
            for _id in ids:
                if not _id:
                    continue
                if cand.lower() in _id.lower() or any(tok.lower() in _id.lower() for tok in cand.split() if len(tok)>3):
                    return f"#{_id}"
        except Exception:
            pass
        try:
            classes = page.eval_on_selector_all('[class]', 'nodes => nodes.flatMap(n => (n.className||\"\").split(/\\s+/))')
            for cl in classes:
                if not cl:
                    continue
                if cand.lower() in cl.lower() or any(tok.lower() in cl.lower() for tok in cand.split() if len(tok)>3):
                    return f".{cl}"
        except Exception:
            pass
    return None


def resolve_selectors(plan: dict, out_plan: Path, out_script: Path, timeout: int = 10000) -> dict:
    """Attempt to resolve selectors and write resolved plan + playwright script.
    Returns the resolved plan dict.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise RuntimeError('playwright is required for auto-resolve: ' + str(e))

    steps = plan.get('steps', [])
    resolved_steps = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        # Walk through steps, performing only safe browser actions to reach UI states.
        for idx, step in enumerate(steps):
            action = (step.get('action') or '').lower()
            target = step.get('target')
            value = step.get('value') or ''
            expected = step.get('expected') or ''
            metadata = step.get('metadata') or {}
            note = ''
            if isinstance(metadata, dict):
                note = metadata.get('note','') or ''
            elif isinstance(metadata, str):
                note = metadata

            # Perform safe browser actions to progress state
            try:
                if action == 'navigate' and isinstance(target, str) and target.strip().lower().startswith(('http://','https://')):
                    page.goto(target, timeout=timeout)
                    time.sleep(1)
                elif action == 'click' and target and not str(target).upper().startswith('DESCRIBE'):
                    try:
                        page.click(target, timeout=timeout)
                        time.sleep(0.5)
                    except Exception:
                        # try a text-based click without raising
                        try:
                            page.locator(target).first.click(timeout=timeout)
                            time.sleep(0.5)
                        except Exception:
                            pass
                elif action == 'fill' and target and value and not str(target).upper().startswith('DESCRIBE'):
                    try:
                        page.fill(target, str(value), timeout=timeout)
                    except Exception:
                        try:
                            page.locator(target).fill(str(value), timeout=timeout)
                        except Exception:
                            pass
                elif action == 'submit' and target and not str(target).upper().startswith('DESCRIBE'):
                    try:
                        page.locator(target).press('Enter')
                    except Exception:
                        try:
                            page.keyboard.press('Enter')
                        except Exception:
                            pass
                elif action == 'wait':
                    t = int(step.get('timeout_seconds') or 3)
                    page.wait_for_timeout(t*1000)
            except Exception:
                # ignore navigation/fill/click errors; we just want to reach best-effort state
                pass

            # After performing the action, try to resolve this step if needed, or upcoming ones
            need = False
            if not target or 'DESCRIBE' in str(target).upper() or not any(ch in str(target) for ch in ('#','.', 'text=', 'xpath=')):
                need = True

            if need:
                # build candidate list: metadata note, expected, value, action words
                candidates = []
                if note:
                    candidates.append(note)
                if expected:
                    candidates.append(expected)
                if value:
                    candidates.append(value)
                if isinstance(step.get('action'), str):
                    candidates.append(step.get('action'))

                # Also scan a short window of upcoming plan steps for helpful text
                for lookahead in range(1,4):
                    if idx+lookahead < len(steps):
                        other = steps[idx+lookahead]
                        for field in ('expected','value'):
                            if other.get(field):
                                candidates.append(other.get(field))
                        md = other.get('metadata')
                        if isinstance(md, dict) and md.get('note'):
                            candidates.append(md.get('note'))

                # Site-specific heuristics: Google search input
                try:
                    cur_url = (page.url or '').lower()
                except Exception:
                    cur_url = ''
                if 'google.' in cur_url:
                    # Map fill/submit placeholders to actual Google search input
                    if action == 'fill' and (not target or 'DESCRIBE' in str(target).upper() or str(target).startswith('text=')):
                        step['target'] = "input[name=q]"
                        resolved_steps.append(step)
                        continue
                    if action == 'submit' and (not target or 'DESCRIBE' in str(target).upper() or str(target).startswith('text=')):
                        step['target'] = "input[name=q]"
                        resolved_steps.append(step)
                        continue

                sel = suggest_on_page(page, candidates)
                if sel:
                    step['target'] = sel

            resolved_steps.append(step)

        try:
            ctx.close()
            browser.close()
        except Exception:
            pass

    resolved_plan = dict(plan)
    resolved_plan['steps'] = resolved_steps
    out_plan.write_text(json.dumps(resolved_plan, ensure_ascii=False, indent=2))

    # generate playwright script from resolved plan
    try:
        from pipeline.agents.executor.plan_to_playwright import generate_playwright_script
        generate_playwright_script(resolved_plan, out_script)
    except Exception:
        pass

    return resolved_plan


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', default='generated_test_plan.json')
    parser.add_argument('--out-plan', default='generated_test_plan_resolved.json')
    parser.add_argument('--out-script', default='generated_playwright_test_resolved.py')
    args = parser.parse_args(argv)

    plan_p = Path(args.plan)
    if not plan_p.exists():
        print('Plan not found:', plan_p)
        return 2
    plan = json.loads(plan_p.read_text())

    out_plan = Path(args.out_plan)
    out_script = Path(args.out_script)

    resolved = resolve_selectors(plan.get('plan', plan), out_plan, out_script)
    print('Wrote resolved plan to', out_plan)
    print('Generated playwright script at', out_script)


if __name__ == '__main__':
    main()

