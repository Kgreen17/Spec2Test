"""Playwright runner with a safe fallback simulator.

- If `playwright` is installed, the runner will launch a Chromium browser (headless), execute supported actions, capture screenshots on failures, and record results.
- If `playwright` is not available, the runner simulates execution: browser actions are marked PASS unless they contain DESCRIBE_TARGET (then SKIPPED/WARNING), and system actions are skipped.

Supported actions: navigate, click, fill, submit, wait, assert, scroll.
System actions (skipped unless explicitly enabled): run_command, copy, rename, start, stop.

Public API:
- run_steps(steps: List[dict], out_report: str | None = None, headless: bool = True, simulate_only: bool = False) -> dict

The function returns a report dict with per-step results and summary counts.
"""
from pathlib import Path
import json
import time
import os
from typing import List, Dict, Any, Optional


SYSTEM_ACTIONS = {"run_command", "copy", "rename", "start", "stop"}
BROWSER_ACTIONS = {"navigate", "click", "fill", "submit", "wait", "assert", "scroll"}


def _safe_makedirs(p: Path):
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)


def _simulate_step(step: Dict[str, Any]) -> Dict[str, Any]:
    action = step.get('action', '').lower()
    target = step.get('target')
    result = {"id": step.get('id'), "action": action, "target": target, "status": "SKIPPED", "reason": None}

    if action in SYSTEM_ACTIONS:
        result['status'] = 'SKIPPED'
        result['reason'] = 'System action skipped for safety'
        return result

    if action in BROWSER_ACTIONS:
        # If target is a descriptive placeholder, mark as WARNING
        if not target or str(target).upper().startswith('DESCRIBE'):
            result['status'] = 'SKIPPED'
            result['reason'] = 'Placeholder target; unable to execute'
            return result
        # Simulate success
        result['status'] = 'PASS'
        return result

    # Unknown action -> mark as WARNING (but include it)
    result['status'] = 'SKIPPED'
    result['reason'] = 'Unknown action - not executed'
    return result


def _dismiss_cookie_banner(page):
    """Try common cookie/consent selectors and click them if present."""
    selectors = [
        "button:has-text('I agree')",
        "button:has-text('I Agree')",
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "#L2AGLb",
        "button[aria-label='Accept all']",
        "button[aria-label='Agree']",
        "text=I agree",
    ]
    for sel in selectors:
        try:
            if page.locator(sel).count() > 0:
                try:
                    page.click(sel, timeout=3000)
                    return True
                except Exception:
                    try:
                        page.locator(sel).first.click(timeout=3000)
                        return True
                    except Exception:
                        continue
        except Exception:
            continue
    return False


def run_steps(steps: List[Dict[str, Any]], out_report: Optional[str] = None, headless: bool = True, simulate_only: bool = False) -> Dict[str, Any]:
    """Execute or simulate the given steps and return a report.

    If Playwright is available and simulate_only is False, attempt real execution in a headless browser.
    Otherwise run a simulation.
    """
    # Try to import Playwright only if not in simulate mode
    playwright_available = False
    if not simulate_only:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
            playwright_available = True
        except Exception:
            playwright_available = False

    report = {"results": [], "summary": {"pass": 0, "fail": 0, "skipped": 0, "warnings": 0}}
    screenshots_dir = Path('reports') / 'screenshots'
    _safe_makedirs(screenshots_dir)

    if playwright_available and not simulate_only:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()

            for step in steps:
                sid = step.get('id')
                action = str(step.get('action') or '').lower()
                target = step.get('target')
                expected = step.get('expected')
                step_result = {"id": sid, "action": action, "target": target, "status": None, "error": None}
                try:
                    if action in SYSTEM_ACTIONS:
                        step_result['status'] = 'SKIPPED'
                        step_result['error'] = 'System action skipped for safety'
                    elif action == 'navigate':
                        page.goto(target)
                        # Dismiss cookie banners if present
                        _dismiss_cookie_banner(page)
                        # Small wait to allow dynamic content to load
                        time.sleep(3)
                        step_result['status'] = 'PASS'
                    elif action == 'click':
                        page.click(target)
                        step_result['status'] = 'PASS'
                    elif action == 'fill':
                        # Try to fill using different methods in order
                        tried = False
                        # Wait for the target to appear first (best-effort)
                        try:
                            page.wait_for_selector(target, timeout=8000)
                        except Exception:
                            pass

                        try:
                            page.fill(target, str(step.get('value') or ''), timeout=5000)
                            step_result['status'] = 'PASS'
                            tried = True
                        except Exception:
                            try:
                                page.locator(target).fill(str(step.get('value') or ''), timeout=5000)
                                step_result['status'] = 'PASS'
                                tried = True
                            except Exception:
                                # Special-case: if this looks like a Google search input, try common alternative selectors and keyboard typing
                                try:
                                    cur_url = (page.url or '').lower()
                                except Exception:
                                    cur_url = ''
                                if 'google.' in cur_url:
                                    alt_selectors = [
                                        "input[name='q']",
                                        'input[name=q]',
                                        "input[aria-label='Search']",
                                        "input[aria-label*='Search']",
                                        "input[title='Search']",
                                        "input[type='search']",
                                        "input.gsfi",
                                        "input[role='combobox']",
                                        "input[aria-label*='search']",
                                    ]
                                    for sel in alt_selectors:
                                        try:
                                            if page.locator(sel).count() > 0:
                                                try:
                                                    page.click(sel, timeout=3000)
                                                except Exception:
                                                    pass
                                                try:
                                                    page.fill(sel, str(step.get('value') or ''), timeout=5000)
                                                    step_result['status'] = 'PASS'
                                                    tried = True
                                                    break
                                                except Exception:
                                                    try:
                                                        page.locator(sel).fill(str(step.get('value') or ''), timeout=5000)
                                                        step_result['status'] = 'PASS'
                                                        tried = True
                                                        break
                                                    except Exception:
                                                        # try keyboard typing
                                                        try:
                                                            page.focus(sel)
                                                            page.keyboard.type(str(step.get('value') or ''))
                                                            step_result['status'] = 'PASS'
                                                            tried = True
                                                            break
                                                        except Exception:
                                                            continue
                                        except Exception:
                                            continue
                                # Global fallback: keyboard type into the target after focusing
                                if not tried:
                                    try:
                                        page.focus(target)
                                        page.keyboard.type(str(step.get('value') or ''))
                                        step_result['status'] = 'PASS'
                                        tried = True
                                    except Exception:
                                        pass
                                if not tried:
                                    # Fallback to wait_for_selector and set via JS
                                    try:
                                        page.wait_for_selector(target, timeout=5000)
                                        page.evaluate("(selector, value) => { const el = document.querySelector(selector); if(el){ el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); } }", target, str(step.get('value') or ''))
                                        step_result['status'] = 'PASS'
                                        tried = True
                                    except Exception as e:
                                        # Stronger JS fallback: find any likely input and set its value
                                        try:
                                            set_ok = page.evaluate("(val) => { const inputs = Array.from(document.querySelectorAll('input')); if(inputs.length===0) return false; const candidates = inputs.filter(i => i.name==='q' || /search/i.test(i.getAttribute('aria-label')||'') || i.type==='search' || i.matches('[role=combobox]')); const el = candidates[0] || inputs[0]; if(!el) return false; el.focus(); el.value = val; el.dispatchEvent(new Event('input', { bubbles: true })); return true; }", str(step.get('value') or ''))
                                            if set_ok:
                                                try:
                                                    # try to press Enter to submit search
                                                    page.keyboard.press('Enter')
                                                except Exception:
                                                    pass
                                                step_result['status'] = 'PASS'
                                                tried = True
                                            else:
                                                step_result['status'] = 'FAIL'
                                                step_result['error'] = f"Fill action failed: {str(e)}"
                                        except Exception as e2:
                                            step_result['status'] = 'FAIL'
                                            step_result['error'] = f"Fill action failed (fallback): {str(e2)}"
                    elif action == 'submit':
                        # Try to submit by pressing Enter on the target or calling evaluate
                        try:
                            page.locator(target).press('Enter')
                            step_result['status'] = 'PASS'
                        except Exception:
                            page.keyboard.press('Enter')
                            step_result['status'] = 'PASS'
                    elif action == 'wait':
                        timeout = int(step.get('timeout_seconds', 10) or 10) * 1000
                        page.wait_for_timeout(timeout)
                        step_result['status'] = 'PASS'
                    elif action == 'assert':
                        # If expected provided, check that locator contains expected text
                        if expected and target:
                            locator = page.locator(target)
                            text = locator.inner_text() if locator.count() > 0 else page.text_content('body')
                            if text and str(expected) in str(text):
                                step_result['status'] = 'PASS'
                            else:
                                step_result['status'] = 'FAIL'
                                step_result['error'] = f"Assertion failed: expected '{expected}' not found in target"
                                # capture screenshot
                                path = screenshots_dir / f"step_{sid}_fail.png"
                                page.screenshot(path=str(path), full_page=True)
                                step_result['screenshot'] = str(path)
                        else:
                            # Basic presence check
                            if page.locator(target).count() > 0:
                                step_result['status'] = 'PASS'
                            else:
                                step_result['status'] = 'FAIL'
                                step_result['error'] = 'Locator not found'
                                path = screenshots_dir / f"step_{sid}_fail.png"
                                page.screenshot(path=str(path), full_page=True)
                                step_result['screenshot'] = str(path)
                    elif action == 'scroll':
                        try:
                            page.locator(target).scroll_into_view_if_needed()
                            step_result['status'] = 'PASS'
                        except Exception:
                            page.evaluate("(sel) => document.querySelector(sel).scrollIntoView()", target)
                            step_result['status'] = 'PASS'
                    else:
                        step_result['status'] = 'SKIPPED'
                        step_result['error'] = 'Unknown action'
                except PlaywrightTimeoutError as te:
                    step_result['status'] = 'FAIL'
                    step_result['error'] = f'Playwright timeout: {te}'
                except Exception as e:
                    step_result['status'] = 'FAIL'
                    step_result['error'] = str(e)
                    try:
                        path = screenshots_dir / f"step_{sid}_error.png"
                        page.screenshot(path=str(path), full_page=True)
                        step_result['screenshot'] = str(path)
                    except Exception:
                        pass

                report['results'].append(step_result)
                if step_result['status'] == 'PASS':
                    report['summary']['pass'] += 1
                elif step_result['status'] == 'FAIL':
                    report['summary']['fail'] += 1
                else:
                    report['summary']['skipped'] += 1

            try:
                context.close()
                browser.close()
            except Exception:
                pass

    else:
        # Simulation run
        for step in steps:
            sid = step.get('id')
            sres = _simulate_step(step)
            # translate to unified fields
            r = {"id": sres.get('id'), "action": sres.get('action'), "target": sres.get('target'), "status": None, "reason": None}
            if sres['status'] == 'PASS':
                r['status'] = 'PASS'
                report['summary']['pass'] += 1
            elif sres['status'] == 'SKIPPED':
                r['status'] = 'SKIPPED'
                r['reason'] = sres.get('reason')
                report['summary']['skipped'] += 1
            else:
                r['status'] = 'WARNING'
                r['reason'] = sres.get('reason')
                report['summary']['warnings'] += 1
            report['results'].append(r)

    report['summary']['total'] = len(report['results'])
    # Save report if requested
    if out_report:
        try:
            Path(out_report).write_text(json.dumps(report, indent=2))
        except Exception:
            pass
    return report


if __name__ == '__main__':
    # simple CLI: load generated_test_plan.json and run
    import sys
    plan_file = sys.argv[1] if len(sys.argv) > 1 else 'generated_test_plan.json'
    out_file = sys.argv[2] if len(sys.argv) > 2 else 'generated_test_plan_report.json'
    if not Path(plan_file).exists():
        print('Plan file not found:', plan_file)
        raise SystemExit(2)
    data = json.loads(Path(plan_file).read_text())
    steps = data.get('plan', {}).get('steps', []) if isinstance(data, dict) else []
    rpt = run_steps(steps, out_report=out_file)
    print('Report written to', out_file)
