"""LLM-based Test Plan generator.

Public API:
    generate_test_plan(context: str, objective: str, max_steps: int = 20, model: str = "gpt-4o") -> dict

Behavior:
- Builds a prompt from context and objective
- Calls OpenAI ChatCompletion to request a JSON test plan
- Parses and validates JSON against Pydantic models
- Returns dict with either 'plan' on success or 'error' describing the failure

This module intentionally avoids adding new heavyweight dependencies: it uses `pydantic` (already present)
for validation and `openai` for LLM calls.
"""
from __future__ import annotations

from typing import List, Optional, Any, Dict
import json
import re
import os
import traceback

from pydantic import BaseModel, Field, ValidationError, validator


# Prompt templates and few-shot examples
SYSTEM_PROMPT = (
    "You are a test-generation assistant. Given documentation/context and a short objective, "
    "produce a single JSON object that exactly matches the required schema: keys \"test_name\" (string), "
    "optional \"description\", and \"steps\" (array of step objects). Supported step actions: "
    "navigate, click, fill, select, assert, wait, submit. Each step must include \"id\", \"action\", and \"target\". "
    "Optional keys are \"value\", \"expected\", \"retries\", \"timeout_seconds\", and \"metadata\". "
    "Output strictly valid JSON, no markdown, no surrounding text, no notes. If you cannot extract selectors use descriptive targets, "
    "but still produce valid JSON. Limit steps to at most {max_steps}. If the context is insufficient, use 'DESCRIBE_TARGET' placeholders."
)

FEW_SHOT_EXAMPLES = [
    {
        "context": "Login page contains form with input id='username', id='password', and button id='submit'. After login user sees element '#welcome' with text 'Welcome'.",
        "objective": "Verify login happy path",
        "output": {
            "test_name": "Login - happy path",
            "description": "Happy path login",
            "steps": [
                {"id": 1, "action": "navigate", "target": "https://example.com/login"},
                {"id": 2, "action": "fill", "target": "#username", "value": "<username>"},
                {"id": 3, "action": "fill", "target": "#password", "value": "<password>"},
                {"id": 4, "action": "click", "target": "#submit"},
                {"id": 5, "action": "assert", "target": "#welcome", "expected": "Welcome"}
            ]
        }
    },
    {
        "context": "A deployment doc shows how to deploy webapp via UI: menu -> Admin -> Deploy. There's a 'Deploy' button with selector '.deploy-btn' in the UI.",
        "objective": "Create test to deploy application via UI",
        "output": {
            "test_name": "Deploy via UI",
            "description": "Deploy app from Admin menu",
            "steps": [
                {"id": 1, "action": "navigate", "target": "https://example.com/admin"},
                {"id": 2, "action": "click", "target": "text=Admin"},
                {"id": 3, "action": "click", "target": ".deploy-btn"},
                {"id": 4, "action": "assert", "target": ".deploy-status", "expected": "Deployment successful"}
            ]
        }
    }
]


# Pydantic models for validation
class Step(BaseModel):
    id: Any
    action: str
    target: str
    value: Optional[str] = None
    expected: Optional[str] = None
    retries: Optional[int] = Field(default=0, ge=0)
    timeout_seconds: Optional[float] = Field(default=None, ge=0)
    metadata: Optional[Dict[str, Any]] = None

    @validator('action')
    def action_non_empty(cls, v):
        # Allow arbitrary action strings from LLMs but ensure non-empty.
        if not v or not str(v).strip():
            raise ValueError('action must be non-empty')
        return str(v)

    @validator('target')
    def target_non_empty(cls, v):
        if not v or not str(v).strip():
            raise ValueError("target must be non-empty")
        return v

    @validator('metadata', pre=True)
    def coerce_metadata(cls, v):
        # Allow metadata as a descriptive string from LLMs; coerce into {'note': <string>}.
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        # If the model returned a short descriptive string, wrap it into a dict
        return {"note": str(v)}


class TestPlan(BaseModel):
    test_name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    steps: List[Step]

    @validator('test_name')
    def non_empty_name(cls, v):
        if not v or not v.strip():
            raise ValueError('test_name must be non-empty')
        return v

    @validator('steps')
    def step_count_ok(cls, v):
        if not v or len(v) == 0:
            raise ValueError('steps must be a non-empty list')
        return v


# Pydantic v2 may require calling model_rebuild() when using postponed annotations
try:
    # For pydantic v2
    Step.model_rebuild()
    TestPlan.model_rebuild()
except Exception:
    # pydantic v1 or method not present -> ignore
    pass


# Helpers
def _strip_code_fences(text: str) -> str:
    if not text:
        return text
    # Remove Markdown code fences ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    return text


def _extract_first_json(text: str) -> Optional[str]:
    """Try to extract the first JSON object substring from text.
    Returns the JSON substring or None if not found.
    """
    if not text:
        return None
    # Find first '{' and matching '}' by last '}' occurrence
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end < start:
        return None
    return text[start:end+1]


def _call_openai_chat(system_prompt: str, user_prompt: str, model: str = 'gpt-4o', max_tokens: int = 1024, temperature: float = 0.0) -> Dict[str, Any]:
    """Call OpenAI ChatCompletion and return the response dict. Requires OPENAI_API_KEY set.
    Raises RuntimeError if openai package or key is not available.
    """
    try:
        import openai
    except Exception as e:
        raise RuntimeError(f"openai package required: {e}")

    # Use central key loader
    try:
        from pipeline.openai_utils import get_openai_api_key
        key = get_openai_api_key(required=True)
    except Exception as e:
        # fallback to environment variable
        key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('OPENAI_API_KEY not set')

    # Support both new and legacy openai SDKs
    use_new_client = hasattr(openai, 'OpenAI')

    try:
        if use_new_client:
            # New OpenAI Python SDK (>=1.0.0)
            try:
                client = openai.OpenAI(api_key=key)
            except TypeError:
                openai.api_key = key
                client = openai.OpenAI()
            # call the chat completions endpoint
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            # Convert to dict if possible
            try:
                resp_dict = resp.to_dict()
            except Exception:
                # Fallback: try mapping-like access
                resp_dict = resp if isinstance(resp, dict) else getattr(resp, '__dict__', {})
            return resp_dict
        else:
            # Legacy openai SDK
            openai.api_key = key
            resp = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return resp
    except Exception as e:
        raise RuntimeError(f"OpenAI call failed: {e}")


def generate_test_plan(context: str, objective: str, max_steps: int = 20, model: str = 'gpt-4o') -> Dict[str, Any]:
    """Generate a test plan using the LLM.

    Returns either:
      {'plan': <dict>, 'source': 'llm', 'usage': {...}}
    or
      {'error': '...', 'message': '...', 'raw': '...'}
    """
    # Basic param validation
    if not objective or not objective.strip():
        return {'error': 'validation_failed', 'message': 'objective required'}

    if not context or len(context.strip()) < 20:
        return {'error': 'validation_failed', 'message': 'insufficient_context', 'details': 'Provide more documentation or use --embeddings to retrieve context.'}

    # Build prompt
    few_shot_text = ''
    for ex in FEW_SHOT_EXAMPLES:
        # include context and objective and the expected JSON as demonstration
        few_shot_text += f"Context: {ex['context']}\nObjective: {ex['objective']}\nOutput: {json.dumps(ex['output'])}\n\n"

    user_prompt = f"{few_shot_text}Context:\n{context}\n\nObjective:\n{objective}\n\nProduce a JSON test plan with at most {max_steps} steps."

    try:
        resp = _call_openai_chat(SYSTEM_PROMPT.format(max_steps=max_steps), user_prompt, model=model, max_tokens=1024)
    except Exception as e:
        return {'error': 'llm_unavailable', 'message': str(e)}

    # Extract text content from response
    try:
        # OpenAI ChatCompletion shape: resp['choices'][0]['message']['content']
        choices = resp.get('choices') or []
        if not choices:
            return {'error': 'llm_unavailable', 'message': 'no choices in response', 'raw': str(resp)}
        content = choices[0].get('message', {}).get('content', '')
    except Exception as e:
        return {'error': 'llm_unavailable', 'message': f'unexpected response format: {e}', 'raw': str(resp)}

    raw_text = content
    cleaned = _strip_code_fences(raw_text)
    json_text = _extract_first_json(cleaned) or cleaned

    try:
        parsed = json.loads(json_text)
    except Exception:
        return {'error': 'parse_error', 'message': 'Could not parse JSON from model output', 'raw': raw_text}

    # Validate with pydantic
    try:
        plan = TestPlan.parse_obj(parsed)
    except ValidationError as ve:
        # Attempt a permissive normalization fallback: coerce fields so we still return a usable plan
        try:
            norm_steps = []
            raw_steps = parsed.get('steps', []) if isinstance(parsed, dict) else []
            for s in raw_steps:
                step = {}
                step['id'] = s.get('id') if isinstance(s, dict) else None
                step['action'] = str(s.get('action')) if isinstance(s, dict) and s.get('action') is not None else 'unknown'
                step['target'] = str(s.get('target')) if isinstance(s, dict) and s.get('target') is not None else 'DESCRIBE_TARGET'
                if isinstance(s, dict) and 'value' in s:
                    step['value'] = s.get('value')
                if isinstance(s, dict) and 'expected' in s:
                    step['expected'] = s.get('expected')
                # retries
                try:
                    step['retries'] = int(s.get('retries', 0)) if isinstance(s, dict) else 0
                except Exception:
                    step['retries'] = 0
                # timeout
                try:
                    step['timeout_seconds'] = float(s.get('timeout_seconds')) if isinstance(s, dict) and s.get('timeout_seconds') is not None else None
                except Exception:
                    step['timeout_seconds'] = None
                # metadata coercion
                meta = None
                if isinstance(s, dict) and 'metadata' in s:
                    if isinstance(s['metadata'], dict):
                        meta = s['metadata']
                    else:
                        meta = {'note': str(s['metadata'])}
                step['metadata'] = meta
                norm_steps.append(step)

            norm_plan = {
                'test_name': parsed.get('test_name') if isinstance(parsed, dict) else 'Generated Test',
                'description': parsed.get('description') if isinstance(parsed, dict) else None,
                'metadata': parsed.get('metadata') if isinstance(parsed, dict) else None,
                'steps': norm_steps,
            }
            # Return normalized plan with warning about validation
            return {'plan': norm_plan, 'source': 'llm', 'warnings': {'validation_errors': json.loads(ve.json())}}
        except Exception as e:
            return {'error': 'validation_failed', 'message': 'Schema validation failed', 'details': json.loads(ve.json()), 'raw': parsed}
    except Exception as e:
        return {'error': 'validation_failed', 'message': str(e), 'raw': parsed}

    usage = None
    if isinstance(resp, dict) and resp.get('usage'):
        usage = resp.get('usage')

    return {'plan': plan.dict(), 'source': 'llm', 'usage': usage}

