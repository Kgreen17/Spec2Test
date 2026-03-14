"""Run chunking on the WebGoat PDF using the existing doc_loader and chunker modules.

This script performs the following steps:
1. Resolve the docs directory (explicit --docs or repo_root/docs fallback).
2. Load the `doc_loader` to find and extract the WebGoat PDF text.
3. Use either character-based chunking (`chunk_text`) or token-aware chunking (`chunk_text_by_tokens`) based on flags.
4. Print simple stats and chunk previews.
5. Optionally save the chunk list to a JSON file.

CLI flags:
- --docs: path to docs directory
- --chunk-size: char chunk size for fallback chunking
- --tokenize: use token-aware chunking (requires tiktoken)
- --max-tokens: max tokens per token chunk
- --overlap-tokens: overlap tokens between chunks
- --preview-count: how many chunks to print
- --save: optional JSON path to save chunks
"""
import argparse
import importlib.util
from pathlib import Path
import json
import sys


def load_module_from_path(path: Path, name: str):
    # Load a module from the given file path
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
    parser.add_argument("--preview-count", type=int, default=3, help="Number of chunk previews to print")
    parser.add_argument("--save", default=None, help="Optional path to save chunks as JSON")
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

    # Load doc_loader and chunker modules
    base = Path(__file__).resolve().parents[1]
    doc_loader_path = base / "ingestion" / "doc_loader.py"
    chunker_path = base / "ingestion" / "chunker.py"

    doc_loader = load_module_from_path(doc_loader_path, "doc_loader")
    chunker = load_module_from_path(chunker_path, "chunker")

    # Load documents from the resolved docs directory
    docs = doc_loader.load_documents(str(docs_dir))
    target = None
    # Find the WebGoat PDF document from the loaded documents
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

    # If the text starts with a message like [OCR fallback used], we still chunk the text after that message
    # Remove a single leading bracketed message line if present
    if text.startswith("["):
        # remove first line if it looks like a loader message
        first_line, _, rest = text.partition('\n')
        if first_line.startswith('[') and 'used' in first_line or 'unavailable' in first_line or 'error' in first_line:
            text = rest.lstrip('\n')

    chunk_size = args.chunk_size
    # Chunk the text using the specified chunking method
    if args.tokenize:
        chunks = chunker.chunk_text_by_tokens(text, max_tokens=args.max_tokens, overlap_tokens=args.overlap_tokens, model=args.model if hasattr(args, 'model') else 'text-embedding-3-small')
    else:
        chunks = chunker.chunk_text(text, chunk_size=chunk_size)

    # Print document and chunking statistics
    print(f"Document path: {target['path']}")
    print(f"Total characters: {len(text)}")
    print(f"Chunk size: {chunk_size}")
    print(f"Number of chunks: {len(chunks)}")
    print()

    preview_count = min(args.preview_count, len(chunks))
    # Print previews of the generated chunks
    for i in range(preview_count):
        c = chunks[i]
        print(f"--- Chunk {i+1}/{len(chunks)} (len={len(c)}) ---")
        print(c[:1000].replace('\n',' '))
        print()

    # Optionally save the chunks to a JSON file
    if args.save:
        out_path = Path(args.save)
        out = {"source": target['path'], "chunk_size": chunk_size, "chunks": chunks}
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        print(f"Saved {len(chunks)} chunks to {out_path}")


if __name__ == '__main__':
    main()

