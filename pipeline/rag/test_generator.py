"""Test Generator: produce structured test plans from documentation + retrieval.

This module provides `generate_test_plan(...)` which:
- Loads precomputed chunks+embeddings via the SimpleRetriever
- Retrieves top-k context chunks for a user-supplied goal or area
- Calls an LLM (OpenAI chat if available) with an instruction prompt to produce a
  structured JSON test plan. The function validates the model output is JSON and
  returns the parsed structure.

Expected output JSON format (example):
{
  "test_name": "Login test",
  "steps": [
    {"action":"navigate", "url":"https://example.com/login"},
    {"action":"fill", "selector":"#username", "value":"user"},
    {"action":"click", "selector":"#submit"},
    {"action":"assert", "selector":"#welcome", "text":"Welcome"}
  ]
}

Notes:
- If OpenAI is unavailable the function returns a fallback structure containing the
  retrieved contexts so you can manually author a test plan.
- Supported actions in the schema: navigate, click, fill, select, assert, wait, submit.
"""
from __future__ import annotations
from typing import Any, Dict, List
import json
import os
import importlib.util
from pathlib import Path

# Try to import optional langchain helper
_langchain_available = False
try:
    import pipeline.rag.langchain_rag as _lc  # type: ignore
    _langchain_available = True
except Exception:
    _langchain_available = False


def _load_retriever(embeddings_json: str):
    spec = importlib.util.spec_from_file_location('retriever', str(Path(__file__).resolve().parents[0] / 'retriever.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SimpleRetriever(embeddings_json)


def _call_openai_chat(system_prompt: str, user_prompt: str, model: str = 'gpt-4o-mini') -> str:
    try:
        import openai
    except Exception as e:
        raise RuntimeError('openai package required for LLM calls: ' + str(e))
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('OPENAI_API_KEY not set')
    openai.api_key = key
    # Use ChatCompletion for compatibility
    resp = openai.ChatCompletion.create(model=model, messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], max_tokens=800)
    return resp['choices'][0]['message']['content']


def generate_test_plan(embeddings_json: str, goal: str, top_k: int = 4, model: str = 'gpt-4o-mini', chroma_persist_dir: str | None = None) -> Dict[str, Any]:
    """Produce a structured test plan JSON for the given goal using the retrieved context.

    Args:
      embeddings_json: path to saved chunks+embeddings JSON
      goal: a short natural-language description of what we want to test (e.g., "deploy the war file" or "login flow")
      top_k: number of context chunks to retrieve
      model: OpenAI chat model to use
      chroma_persist_dir: optional path to a Chroma persist directory; if provided and langchain is available, use LangChain RAG.

    Returns:
      dict (parsed JSON) representing the test plan, or a fallback dict with 'contexts' if LLM not available.
    """
    # If LangChain and Chroma persist dir are available, prefer the LangChain RAG helper
    if chroma_persist_dir and _langchain_available:
        try:
            res = _lc.run_langchain_rag(chroma_persist_dir, 'webgoat', goal, k=top_k, llm_model=model)
            # res is expected to be {'answer': '...'} -> Return as an LLM-generated summary in plan.answer
            return {'plan': {'test_name': f'Auto-generated: {goal}', 'steps': [], 'llm_answer': res.get('answer')}, 'method': 'langchain'}
        except Exception:
            # Fall through to standard flow
            pass

    retriever = _load_retriever(embeddings_json)
    try:
        hits = retriever.retrieve(goal, top_k=top_k)
    except Exception as e:
        return {'error': f'Failed to run retriever: {e}'}

    context = '\n\n---\n\n'.join([f"Chunk {h['index']} (score={h['score']:.4f}):\n{h['chunk']}" for h in hits])

    # Build the instruction prompt for the test generator. Ask for JSON-only output.
    system_prompt = (
        "You are a test generation assistant. Given documentation context, produce a single JSON object that defines a test plan. "
        "Return only valid JSON and no additional text. The JSON must match the schema: {\n  \"test_name\": string,\n  \"steps\": [ {action:..., ...}, ... ]\n}. "
        "Supported actions: navigate, click, fill, select, assert, wait, submit. "
        "Each step should include the minimal fields required (e.g., navigate->url, fill->selector & value, click->selector, assert->selector & text). "
        "Use selectors if you can guess them from the context; when not available prefer descriptive targets."
    )

    user_prompt = (
        f"Documentation context:\n{context}\n\nGoal: {goal}\n\nProduce a concise test plan in strict JSON following the schema. "
        "If multiple independent test cases are needed, produce a single test covering a primary happy-path scenario."
    )

    # Try to call OpenAI, otherwise fallback.
    try:
        raw = _call_openai_chat(system_prompt, user_prompt, model=model)
        # The model is instructed to return JSON only; attempt to parse it.
        # Some models output code fences; strip them before parsing.
        text = raw.strip()
        if text.startswith("```"):
            # remove code fence
            parts = text.split('\n')
            # remove first line if it's fence
            if parts[0].startswith('```'):
                parts = parts[1:]
            # remove trailing ``` if present
            if parts and parts[-1].startswith('```'):
                parts = parts[:-1]
            text = '\n'.join(parts).strip()
        plan = json.loads(text)
        # Basic validation of structure
        if 'test_name' not in plan or 'steps' not in plan:
            return {'error': 'Model returned JSON but missing required keys', 'raw': plan}
        return {'plan': plan, 'hits': hits}
    except Exception as e:
        # Fallback: return contexts and a simple hint to author a test plan manually
        return {
            'fallback': True,
            'error': str(e),
            'hits': hits,
            'hint': f"Use the retrieved contexts to author a test plan for goal: {goal}."
        }


if __name__ == '__main__':
    print('Test Generator quick check using docs/webgoat_embeddings.json')
    fn = Path(__file__).resolve().parents[2] / 'docs' / 'webgoat_embeddings.json'
    if fn.exists():
        out = generate_test_plan(str(fn), 'deploy the war file', top_k=3)
        print(json.dumps(out, indent=2))
    else:
        print('No embeddings file found at', fn)
