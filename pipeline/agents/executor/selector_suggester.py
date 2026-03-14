"""Heuristic selector suggester for generated test plans.

Provides a simple function `suggest_selectors(plan, chunks)` that inspects the plan and text chunks
(from the docs/embedding output) to propose CSS/text selectors for steps that contain placeholder
`DESCRIBE_TARGET` or otherwise look underspecified.

This is intentionally conservative: suggestions are best-effort and returned as a list per step.
"""
import re
from typing import List, Dict, Any, Optional


def _find_ids_classes_in_text(text: str) -> List[str]:
    sels = set()
    # find id="foo" or id='foo'
    for m in re.finditer(r"id\s*=\s*['\"]([^'\"]+)['\"]", text):
        sels.add(f"#{m.group(1)}")
    # find class="a b" => return .a and .b
    for m in re.finditer(r"class\s*=\s*['\"]([^'\"]+)['\"]", text):
        parts = re.split(r"\s+", m.group(1).strip())
        for p in parts:
            if p:
                sels.add(f".{p}")
    # find role="button" or aria-label
    for m in re.finditer(r"aria-label\s*=\s*['\"]([^'\"]+)['\"]", text):
        textval = m.group(1).strip()
        if textval:
            sels.add(f"text={textval}")
    return list(sels)


def _find_text_snippets(text: str, query: str) -> List[str]:
    # naive: find sentences containing query tokens and return text="..."
    q = query.lower()
    results = []
    for m in re.finditer(r"([^\.\n]{0,120}%s[^\.\n]{0,120})" % re.escape(query), text, flags=re.IGNORECASE):
        snippet = m.group(1).strip()
        if snippet:
            results.append(f"text={snippet[:80]}")
    return results


def suggest_selectors(plan: Dict[str, Any], chunks: List[str], max_per_step: int = 3) -> Dict[Any, List[str]]:
    """Return suggestions mapping step id -> list of suggested selectors.

    Strategy:
      - For each step with target containing 'DESCRIBE' or lacking obvious selector chars (#, ., text=),
        search chunks for id/class/aria-label patterns and for plain text matches from metadata note or action.
      - Return up to `max_per_step` candidate selectors, prioritizing id/class then text snippets.
    """
    suggestions: Dict[Any, List[str]] = {}
    all_text = "\n\n".join(chunks or [])

    for s in (plan.get('steps') or []):
        sid = s.get('id')
        target = s.get('target') or ''
        metadata = s.get('metadata') or {}
        note = ''
        if isinstance(metadata, dict):
            note = metadata.get('note', '') or ''
        elif isinstance(metadata, str):
            note = metadata

        # heuristics: decide if suggestion needed
        need = False
        if not target or 'DESCRIBE' in str(target).upper() or (not any(ch in str(target) for ch in ('#', '.', 'text=', 'xpath='))):
            need = True

        if not need:
            continue

        candidates = []
        # search note first if available
        if note:
            candidates.extend(_find_ids_classes_in_text(note))
            candidates.extend(_find_text_snippets(all_text, note))

        # then search chunks for ids/classes
        candidates.extend(_find_ids_classes_in_text(all_text))

        # then search chunks for text-based snippets using step action/target keywords
        keywords = ''
        if isinstance(s.get('action'), str):
            keywords += s.get('action') + ' '
        if isinstance(s.get('value'), str):
            keywords += s.get('value') + ' '
        if isinstance(s.get('expected'), str):
            keywords += s.get('expected') + ' '
        if keywords.strip():
            candidates.extend(_find_text_snippets(all_text, keywords.strip()))

        # dedupe and limit
        unique = []
        for c in candidates:
            if c and c not in unique:
                unique.append(c)
            if len(unique) >= max_per_step:
                break

        suggestions[sid] = unique

    return suggestions

