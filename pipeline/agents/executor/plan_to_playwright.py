"""Convert a normalized test plan into a runnable Playwright Python script.

- Only converts browser actions (navigate, click, fill, submit, wait, assert, scroll).
- Inserts TODO comments for system-level actions and DESCRIBE_TARGET placeholders.
- Produces a single Python file that uses Playwright sync API.
"""
from pathlib import Path
from typing import Dict, Any, List

BROWSER_ACTIONS = {"navigate", "click", "fill", "submit", "wait", "assert", "scroll"}


def generate_playwright_script(plan: Dict[str, Any], out_path: Path, title: str = 'generated_test') -> Path:
    steps = plan.get('steps', [])
    lines: List[str] = []
    lines.append('from playwright.sync_api import sync_playwright')
    lines.append('')
    lines.append('def run():')
    lines.append('    with sync_playwright() as p:')
    lines.append('        browser = p.chromium.launch(headless=True)')
    lines.append('        ctx = browser.new_context()')
    lines.append('        page = ctx.new_page()')
    lines.append('')

    for s in steps:
        action = str(s.get('action') or '').lower()
        target = s.get('target')
        value = s.get('value')
        expected = s.get('expected')
        tid = s.get('id')

        if action in BROWSER_ACTIONS:
            if not target or str(target).upper().startswith('DESCRIBE'):
                lines.append(f"        # TODO: replace DESCRIBE_TARGET for step {tid} with a real selector")
                lines.append(f"        # step {tid}: {action} {target}")
                continue
            if action == 'navigate':
                lines.append(f"        page.goto(r'{target}')")
            elif action == 'click':
                lines.append(f"        page.click(r'{target}')")
            elif action == 'fill':
                lines.append(f"        page.fill(r'{target}', r'{value or ''}')")
            elif action == 'submit':
                lines.append(f"        try:")
                lines.append(f"            page.locator(r'{target}').press('Enter')")
                lines.append(f"        except Exception:")
                lines.append(f"            page.keyboard.press('Enter')")
            elif action == 'wait':
                t = int(s.get('timeout_seconds') or 5)
                lines.append(f"        page.wait_for_timeout({t}*1000)")
            elif action == 'assert':
                if expected:
                    lines.append(f"        assert '{expected}' in (page.locator(r'{target}').inner_text() if page.locator(r'{target}').count()>0 else page.text_content('body')), 'Assertion failed: {expected}'")
                else:
                    lines.append(f"        assert page.locator(r'{target}').count() > 0, 'Locator not found: {target}'")
            elif action == 'scroll':
                lines.append(f"        try:")
                lines.append(f"            page.locator(r'{target}').scroll_into_view_if_needed()")
                lines.append(f"        except Exception:")
                lines.append(f"            page.evaluate(\"(sel) => document.querySelector(sel).scrollIntoView()\", r'{target}')")
        else:
            # system or unknown action
            lines.append(f"        # TODO: system or unknown action for step {tid}: {action} {target}")

    lines.append('')
    lines.append("if __name__ == '__main__':")
    lines.append('    run()')

    out_path.write_text('\n'.join(lines))
    return out_path

