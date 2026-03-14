"""Run embedding on document chunks using `embedder.py`.

This script:
1. Resolves docs directory (explicit --docs or repo_root/docs fallback).
2. Loads the WebGoat PDF using `doc_loader`.
3. Chunks the extracted text either by characters or by tokens (if --tokenize).
4. Calls `embedder.embed_chunks` with the selected backend (`dummy`, `openai`, or `auto`).
5. Prints chunk/embedding stats and a few previews.
6. Optionally saves chunks + embeddings to a JSON file.

CLI flags (key ones):
- --tokenize / --max-tokens / --overlap-tokens: token-aware chunking (requires tiktoken)
- --backend: embedding backend to use (auto/dummy/openai)
- --model: model name for OpenAI embeddings
- --batch-size: number of chunks per OpenAI API call
- --save: path to save results JSON

Behavior notes:
- If --backend=openai is selected, ensure OPENAI_API_KEY is set and `openai` package installed.
- `auto` backend will attempt OpenAI if an API key is present; otherwise it uses the dummy backend.
"""

import argparse
import importlib.util
from pathlib import Path
import json
import sys
import os


def load_module_from_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default=None, help="Path to docs directory")
    parser.add_argument("--chunk-size", type=int, default=500, help="Chunk size in characters")
    parser.add_argument("--tokenize", action="store_true", help="Use token-aware chunking (requires tiktoken)")
    parser.add_argument("--max-tokens", type=int, default=200, help="Max tokens per chunk when using token-aware chunking")
    parser.add_argument("--overlap-tokens", type=int, default=20, help="Overlap tokens between chunks when using token-aware chunking")
    parser.add_argument("--backend", default="auto", choices=["auto", "dummy", "openai"], help="Embedding backend to use")
    parser.add_argument("--model", default="text-embedding-3-small", help="OpenAI embedding model to use (if backend=openai)")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for OpenAI embedding requests")
    parser.add_argument("--save", default=None, help="Optional path to save embeddings JSON")
    parser.add_argument("--preview-count", type=int, default=3, help="Number of chunk previews to print")
    args = parser.parse_args()

    # Resolve docs path
    if args.docs:
        docs_dir = Path(args.docs).expanduser().resolve()
    else:
        repo_root = Path(__file__).resolve().parents[2]
        docs_dir = repo_root / "docs"

    if not docs_dir.exists() or not docs_dir.is_dir():
        print(f"Docs directory not found: {docs_dir}")
        sys.exit(2)

    base = Path(__file__).resolve().parents[1]
    doc_loader_path = base / "ingestion" / "doc_loader.py"
    chunker_path = base / "ingestion" / "chunker.py"
    embedder_path = base / "ingestion" / "embedder.py"

    doc_loader = load_module_from_path(doc_loader_path, "doc_loader")
    chunker = load_module_from_path(chunker_path, "chunker")
    embedder = load_module_from_path(embedder_path, "embedder")

    docs = doc_loader.load_documents(str(docs_dir))
    target = None
    for d in docs:
        if "webgoat" in d["path"].lower() or "webgoat" in d.get("text", "").lower():
            target = d
            break

    if not target:
        print(f"WebGoat PDF not found under {docs_dir}")
        sys.exit(2)

    text = target.get("text", "") or ""
    if not text:
        print("No extracted text available for WebGoat PDF")
        sys.exit(3)

    # strip loader message if present
    if text.startswith("["):
        first_line, _, rest = text.partition('\n')
        if first_line.startswith('[') and ('used' in first_line or 'unavailable' in first_line or 'error' in first_line):
            text = rest.lstrip('\n')

    if args.tokenize:
        chunks = chunker.chunk_text_by_tokens(text, max_tokens=args.max_tokens, overlap_tokens=args.overlap_tokens, model=args.model)
    else:
        chunks = chunker.chunk_text(text, chunk_size=args.chunk_size)
    print(f"Document path: {target['path']}")
    print(f"Total characters: {len(text)}")
    if args.tokenize:
        print(f"Token chunking: max_tokens={args.max_tokens}, overlap={args.overlap_tokens}")
    else:
        print(f"Chunk size: {args.chunk_size}")
    print(f"Number of chunks: {len(chunks)}")

    # Embed
    try:
        # Detect if OpenAI key is available and prefer OpenAI when possible
        try:
            from pipeline.openai_utils import get_openai_api_key
            has_key = bool(get_openai_api_key(required=False))
        except Exception:
            has_key = bool(os.environ.get('OPENAI_API_KEY'))

        backend_to_use = 'openai' if has_key and args.backend in ('auto', 'openai') else (args.backend if args.backend in ('auto', 'dummy', 'openai') else 'auto')

        embeddings = embedder.embed_chunks(chunks, backend=backend_to_use, model=args.model, batch_size=args.batch_size)
    except Exception as e:
        print(f"Embedding failed: {e}")
        if args.backend in ("auto", "openai"):
            print("If you intended to use OpenAI, ensure OPENAI_API_KEY is set in your environment and the 'openai' package is installed.")
        sys.exit(4)

    print(f"Generated {len(embeddings)} embeddings (dim={len(embeddings[0]) if embeddings else 0})")
    print()

    preview = min(args.preview_count, len(chunks))
    for i in range(preview):
        print(f"--- Chunk {i+1} preview (len={len(chunks[i])}) ---")
        print(chunks[i][:500].replace('\n',' '))
        print(f"Embedding sample: {embeddings[i][:8]}")
        print()

    if args.save:
        out = {
            "source": target['path'],
            "chunk_size": args.chunk_size,
            "backend": backend_to_use,
            "chunks": chunks,
            "embeddings": embeddings,
        }
        out_path = Path(args.save)
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        print(f"Saved embeddings to: {out_path}")


if __name__ == '__main__':
    main()

