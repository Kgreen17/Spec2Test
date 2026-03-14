"""Embedder
Provides embed_chunks(chunks, backend='auto', **kwargs')
Backends:
- auto: use OpenAI if available and API key set, otherwise dummy
- openai: explicit OpenAI (requires openai package and OPENAI_API_KEY)
- dummy: returns a simple length-based embedding for each chunk

OpenAI embedding supports batching and simple retry/backoff.

Usage notes:
- For OpenAI: set OPENAI_API_KEY in your environment and install the `openai` package.
- The `auto` backend will use OpenAI only if the API key is present; otherwise it returns dummy embeddings.
- When using OpenAI, you can pass `model`, `batch_size`, `max_retries`, and `retry_backoff` through kwargs.
"""
from typing import List, Iterable
import os
import time


def _dummy_embed(chunks: Iterable[str]) -> List[List[float]]:
    # deterministic simple embedding: normalized character counts of some buckets
    vecs = []
    for c in chunks:
        l = len(c)
        # produce a small vector of character-count features
        vecs.append([float(l), float(l % 97), float((l // 100) % 100)])
    return vecs


def _openai_embed(chunks: Iterable[str], model: str = "text-embedding-3-small", batch_size: int = 100, max_retries: int = 3, retry_backoff: float = 1.0) -> List[List[float]]:
    try:
        import openai
    except Exception as e:
        raise RuntimeError("openai package required for OpenAI embedding: " + str(e))

    # Use centralized key loader
    try:
        from pipeline.openai_utils import get_openai_api_key
    except Exception:
        key = os.environ.get("OPENAI_API_KEY")
    else:
        key = get_openai_api_key(required=True)

    if not key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    # Prefer new OpenAI Python client (openai.OpenAI) if available; otherwise use legacy interface
    inputs = list(chunks)
    all_embeddings = []

    # Determine sdk style
    use_new_client = hasattr(openai, "OpenAI")

    for i in range(0, len(inputs), batch_size):
        batch = inputs[i:i+batch_size]
        attempt = 0
        while True:
            try:
                if use_new_client:
                    # new-style OpenAI client: openai.OpenAI(api_key=...)
                    try:
                        client = openai.OpenAI(api_key=key)
                    except TypeError:
                        # some builds expect setting openai.api_key instead
                        openai.api_key = key
                        client = openai.OpenAI()
                    resp = client.embeddings.create(model=model, input=batch)
                    # resp.data: list of items, each may be dict-like or object-like
                    batch_embs = []
                    for item in getattr(resp, 'data', []) or resp.get('data', []):
                        if isinstance(item, dict):
                            emb = item.get('embedding')
                        else:
                            emb = getattr(item, 'embedding', None)
                        batch_embs.append(emb)
                else:
                    # legacy openai package interface
                    openai.api_key = key
                    resp = openai.Embedding.create(input=batch, model=model)
                    batch_embs = [e["embedding"] for e in resp["data"]]

                all_embeddings.extend(batch_embs)
                break
            except Exception as e:
                attempt += 1
                if attempt > max_retries:
                    raise RuntimeError(f"OpenAI embedding failed after {max_retries} attempts: {e}")
                sleep_time = retry_backoff * (2 ** (attempt - 1))
                time.sleep(sleep_time)
    return all_embeddings


def embed_chunks(chunks: Iterable[str], backend: str = "auto", **kwargs) -> List[List[float]]:
    """Embed a sequence of text chunks.

    Args:
        chunks: iterable of strings
        backend: 'auto'|'openai'|'dummy'
        kwargs: backend-specific kwargs (e.g., model, batch_size for OpenAI)

    Returns:
        list of vector embeddings (list of floats)
    """
    if backend == "dummy":
        return _dummy_embed(chunks)

    if backend == "openai":
        return _openai_embed(chunks, model=kwargs.get("model", "text-embedding-3-small"), batch_size=kwargs.get("batch_size", 100), max_retries=kwargs.get("max_retries", 3), retry_backoff=kwargs.get("retry_backoff", 1.0))

    # auto: try openai if available and env key set, otherwise dummy
    if backend == "auto":
        try:
            # Prefer the centralized helper to detect an available API key
            from pipeline.openai_utils import get_openai_api_key
            if get_openai_api_key(required=False):
                return _openai_embed(chunks, model=kwargs.get("model", "text-embedding-3-small"), batch_size=kwargs.get("batch_size", 100), max_retries=kwargs.get("max_retries", 3), retry_backoff=kwargs.get("retry_backoff", 1.0))
        except Exception:
            # Fall back to checking the raw environment to remain robust
            if os.environ.get("OPENAI_API_KEY"):
                return _openai_embed(chunks, model=kwargs.get("model", "text-embedding-3-small"), batch_size=kwargs.get("batch_size", 100), max_retries=kwargs.get("max_retries", 3), retry_backoff=kwargs.get("retry_backoff", 1.0))
        return _dummy_embed(chunks)

    raise ValueError(f"Unknown embed backend: {backend}")


if __name__ == "__main__":
    print(embed_chunks(["hello world", "another chunk"], backend="dummy"))
