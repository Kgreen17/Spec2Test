"""Simple embedding-based retriever

This module provides a minimal Retriever that can load precomputed chunks+embeddings
from a JSON file (the format produced by `run_embedder.py`) and perform cosine-similarity
retrieval against a query embedding computed via `embedder.embed_chunks`.

It is intentionally lightweight and works without external vector DBs. If you have
Chroma or another vector store, use `store_and_query_chroma.py` instead or extend this class.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import importlib.util


class SimpleRetriever:
    def __init__(self, embeddings_json: str):
        data = json.loads(Path(embeddings_json).read_text(encoding='utf-8'))
        self.source = data.get('source')
        self.chunks: List[str] = data.get('chunks', [])
        self.embeddings: List[List[float]] = data.get('embeddings', [])
        if len(self.chunks) != len(self.embeddings):
            raise ValueError('chunks and embeddings length mismatch')

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        da = math.sqrt(sum(x * x for x in a))
        db = math.sqrt(sum(x * x for x in b))
        if da == 0 or db == 0:
            return 0.0
        return sum(x * y for x, y in zip(a, b)) / (da * db)

    def retrieve(self, query: str, top_k: int = 3, embedder_module_path: Optional[str] = None, embed_kwargs: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve top_k chunks for the given query.

        If embedder_module_path is provided, it will dynamically load that module and call
        embed_chunks([query], backend='auto', **embed_kwargs) to compute the query embedding.
        Otherwise, the function will attempt to import the project's embedder module at
        pipeline/ingestion/embedder.py using a relative path.

        Returns a list of dicts with keys: index, chunk, score
        """
        # Load embedder dynamically if possible
        if embedder_module_path:
            spec = importlib.util.spec_from_file_location('embedder', embedder_module_path)
            emb_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(emb_mod)
        else:
            # default path relative to this repo
            spec = importlib.util.spec_from_file_location('embedder', str(Path(__file__).resolve().parents[1] / 'ingestion' / 'embedder.py'))
            emb_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(emb_mod)

        embed_kwargs = embed_kwargs or {}
        try:
            # Prefer OpenAI if key available; embedder will handle 'openai' backend
            from pipeline.openai_utils import get_openai_api_key
            has_key = bool(get_openai_api_key(required=False))
        except Exception:
            import os as _os
            has_key = bool(_os.environ.get('OPENAI_API_KEY'))

        backend = 'openai' if has_key else 'auto'
        try:
            q_emb = emb_mod.embed_chunks([query], backend=backend, **embed_kwargs)[0]
        except Exception as e:
            # If embedding fails, raise a clear error for the caller to handle
            raise RuntimeError(f'Failed to embed query: {e}')

        sims: List[Tuple[int, float]] = []
        for i, emb in enumerate(self.embeddings):
            sims.append((i, self._cosine(q_emb, emb)))
        sims.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in sims[:top_k]:
            results.append({'index': idx, 'chunk': self.chunks[idx], 'score': score})
        return results


if __name__ == '__main__':
    print('SimpleRetriever: quick test using docs/webgoat_embeddings.json (if present)')
    fn = Path(__file__).resolve().parents[2] / 'docs' / 'webgoat_embeddings.json'
    if fn.exists():
        r = SimpleRetriever(str(fn))
        out = r.retrieve('deploy the war file', top_k=2)
        for o in out:
            print(o['index'], o['score'])
            print(o['chunk'][:200].replace('\n',' '))
    else:
        print('No embeddings JSON found at', fn)
