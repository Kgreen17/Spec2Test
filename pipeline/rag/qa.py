"""Question-answering helper that uses SimpleRetriever + optional OpenAI LLM to produce answers.

Behavior:
- Load the embeddings JSON via SimpleRetriever.
- Retrieve top-K chunks for the query.
- If OpenAI is available (OPENAI_API_KEY set and openai package installed), call the ChatCompletion/Chat API
  to generate a concise answer using retrieved context as system prompt.
- Otherwise return the retrieved contexts as a fallback answer.
"""
from __future__ import annotations
from typing import List, Dict, Any
import os
import importlib.util

from pathlib import Path


def _load_retriever(embeddings_json: str):
    spec = importlib.util.spec_from_file_location('retriever', str(Path(__file__).resolve().parents[0] / 'retriever.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SimpleRetriever(embeddings_json)


def answer_query(embeddings_json: str, query: str, top_k: int = 3, openai_model: str = 'gpt-4o-mini') -> Dict[str, Any]:
    retriever = _load_retriever(embeddings_json)
    try:
        hits = retriever.retrieve(query, top_k=top_k)
    except Exception as e:
        return {'error': str(e)}

    # Build a simple context by concatenating top hits with separators, include source metadata
    context = '\n\n---\n\n'.join([f"Chunk {h['index']} (score={h['score']:.4f}):\n{h['chunk']}" for h in hits])

    # If openai package and key are available, call OpenAI Chat to produce an answer using the context
    try:
        import openai
        key = os.environ.get('OPENAI_API_KEY')
        if not key:
            raise RuntimeError('OPENAI_API_KEY not set')
        openai.api_key = key
        system_message = {
            'role': 'system',
            'content': 'You are a helpful assistant. Use the provided context to answer the user query concisely and cite the chunk indices.'
        }
        user_message = {
            'role': 'user',
            'content': f"Context:\n{context}\n\nUser query: {query}\n\nProvide a brief answer and list the chunk indices you used."
        }
        # Use the Chat completions endpoint if available
        resp = openai.ChatCompletion.create(model=openai_model, messages=[system_message, user_message], max_tokens=512)
        ans = resp['choices'][0]['message']['content']
        return {'answer': ans, 'hits': hits}
    except Exception as e:
        # Fallback: return retrieved contexts and a simple heuristic answer (first sentence match)
        fallback = {'answer': 'OpenAI unavailable or failed; returning retrieved contexts for manual inspection.', 'hits': hits, 'error': str(e)}
        return fallback


if __name__ == '__main__':
    print('QA helper quick test against docs/webgoat_embeddings.json (if present)')
    fn = Path(__file__).resolve().parents[2] / 'docs' / 'webgoat_embeddings.json'
    if fn.exists():
        print(answer_query(str(fn), 'How to deploy the war file?', top_k=3))
    else:
        print('No embeddings JSON found at', fn)

