"""Store embeddings into a local Chroma DB and run a sample query.

This script supports two modes:
- Load precomputed chunks+embeddings from a JSON file (fast)
- Compute chunks and embeddings on-the-fly (token-aware chunking optional) and then store

Main steps:
1. Load JSON if --embeddings is provided, otherwise extract text and compute chunks.
2. Compute embeddings via `embedder.embed_chunks` (auto/openai/dummy) with batching support.
3. Create or get a Chroma collection, add (or upsert) the ids/documents/embeddings.
4. Persist the Chroma DB to `--persist_dir` and run a sample semantic query.

CLI highlights:
- --embeddings: path to precomputed JSON file (contains chunks & embeddings)
- --docs: docs path to extract and compute embeddings (when --embeddings omitted)
- --persist_dir: directory where Chroma will persist its DB
- --model / --batch-size: OpenAI embedding options when computing embeddings
- --tokenize / --max-tokens / --overlap-tokens: use token-aware chunking when computing
- --query / --n: demo search query and number of results to return
"""
import argparse
import json
from pathlib import Path
import importlib.util
import sys
import os


def load_module_from_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--embeddings", help="Path to JSON with chunks+embeddings", default=None)
    parser.add_argument("--docs", help="Docs dir to re-run embedding if embeddings file missing", default=None)
    parser.add_argument("--persist_dir", help="Chroma persist dir", default="db/chroma")
    parser.add_argument("--collection", help="Chroma collection name", default="webgoat")
    parser.add_argument("--query", help="Query string for demo search", required=False, default="how to deploy the war file")
    parser.add_argument("--model", help="OpenAI embedding model to use when computing embeddings", default="text-embedding-3-small")
    parser.add_argument("--batch-size", type=int, help="Batch size for OpenAI embedding requests", default=100)
    parser.add_argument("--tokenize", action="store_true", help="Use token-aware chunking (requires tiktoken)")
    parser.add_argument("--max-tokens", type=int, default=200, help="Max tokens per chunk when using token-aware chunking")
    parser.add_argument("--overlap-tokens", type=int, default=20, help="Overlap tokens between chunks when using token-aware chunking")
    parser.add_argument("--n", type=int, help="Number of results", default=3)
    args = parser.parse_args()

    # Load or compute embeddings
    embeddings_file = Path(args.embeddings) if args.embeddings else None
    chunks = None
    embeddings = None
    source = None

    if embeddings_file and embeddings_file.exists():
        # Load precomputed chunks and embeddings from the provided JSON file
        data = json.loads(embeddings_file.read_text(encoding='utf-8'))
        chunks = data.get('chunks', [])
        embeddings = data.get('embeddings', [])
        source = data.get('source')
    else:
        # attempt to compute using doc_loader, chunker, embedder
        base = Path(__file__).resolve().parents[1]
        doc_loader = load_module_from_path(base / 'ingestion' / 'doc_loader.py', 'doc_loader')
        chunker = load_module_from_path(base / 'ingestion' / 'chunker.py', 'chunker')
        embedder = load_module_from_path(base / 'ingestion' / 'embedder.py', 'embedder')

        # resolve docs dir
        if args.docs:
            docs_dir = Path(args.docs).expanduser().resolve()
        else:
            docs_dir = Path(__file__).resolve().parents[2] / 'docs'

        # Load documents from the specified directory
        docs = doc_loader.load_documents(str(docs_dir))
        target = None
        for d in docs:
            # Look for a document related to WebGoat
            if 'webgoat' in d['path'].lower() or 'webgoat' in d.get('text','').lower():
                target = d
                break
        if not target:
            print('WebGoat PDF not found under', docs_dir)
            sys.exit(2)

        text = target.get('text','') or ''
        if text.startswith('['):
            first_line, _, rest = text.partition('\n')
            if first_line.startswith('[') and ('used' in first_line or 'unavailable' in first_line or 'error' in first_line):
                text = rest.lstrip('\n')

        # Compute chunks from the loaded text
        chunks = chunker.chunk_text(text, chunk_size=500)
        try:
            # Compute embeddings for the chunks using the specified model and options
            if args.tokenize:
                chunks = chunker.chunk_text_by_tokens(text, max_tokens=args.max_tokens, overlap_tokens=args.overlap_tokens, model=args.model)
            else:
                chunks = chunker.chunk_text(text, chunk_size=500)

            # Prefer OpenAI if the environment has a key; otherwise use the requested backend
            try:
                from pipeline.openai_utils import get_openai_api_key
                has_key = bool(get_openai_api_key(required=False))
            except Exception:
                has_key = bool(os.environ.get("OPENAI_API_KEY"))

            chosen_backend = 'openai' if has_key and args.model else args.backend if hasattr(args, 'backend') else 'auto'

            # use embedder with explicit backend and pass model/batch_size
            embeddings = embedder.embed_chunks(chunks, backend=( 'openai' if has_key else 'dummy' ), model=args.model, batch_size=args.batch_size)
        except Exception as e:
            print('Embedder failed, falling back to dummy embedding:', e)
            embeddings = embedder.embed_chunks(chunks, backend='dummy')
        source = target.get('path')

    # validate
    if not chunks or not embeddings or len(chunks) != len(embeddings):
        print('Invalid chunks/embeddings data (counts mismatch)')
        sys.exit(3)

    # Import chromadb
    try:
        import chromadb
        from chromadb.config import Settings
    except Exception as e:
        print('chromadb is required to run this script. Install with: pip install chromadb')
        print('Error:', e)
        sys.exit(4)

    # Create a Chroma client to interact with the database
    print('Creating chroma client with persist dir:', args.persist_dir)
    sys.stdout.flush()
    try:
        client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=str(Path(args.persist_dir))))
        print('Chroma client created')
        sys.stdout.flush()
    except Exception as e:
        print('Failed to create Chroma client:', e)
        import traceback
        traceback.print_exc()
        sys.exit(5)

    coll = None
    try:
        # Try to get the existing collection
        coll = client.get_collection(args.collection)
        print('Got existing collection:', args.collection)
    except Exception:
        # If the collection doesn't exist, create a new one
        print('Collection not found, creating:', args.collection)
        try:
            coll = client.create_collection(args.collection)
            print('Collection created')
        except Exception as e:
            print('Failed to create collection:', e)
            import traceback
            traceback.print_exc()
            sys.exit(6)

    print('Preparing to add', len(chunks), 'items')
    sys.stdout.flush()
    ids = [f"chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"source": source, "chunk_index": i} for i in range(len(chunks))]
    documents = [c[:1000] for c in chunks]  # store preview as document

    # add or upsert
    try:
        # Attempt to add new items to the collection
        coll.add(ids=ids, metadatas=metadatas, documents=documents, embeddings=embeddings)
        print('Added items to collection')
    except Exception as e:
        print('Add failed, attempting upsert:', e)
        try:
            # If add fails, attempt to upsert (update or insert) the items
            coll.upsert(ids=ids, metadatas=metadatas, documents=documents, embeddings=embeddings)
            print('Upsert succeeded')
        except Exception as e2:
            print('Upsert failed:', e2)
            import traceback
            traceback.print_exc()
            sys.exit(7)

    try:
        # Persist the changes to the Chroma DB
        client.persist()
        print('Persist called')
    except Exception as e:
        print('Persist failed:', e)
        import traceback
        traceback.print_exc()
        sys.exit(8)

    print(f"Stored {len(ids)} items into Chroma collection '{args.collection}' at {args.persist_dir}")
    sys.stdout.flush()

    # perform a query embedding
    # load embedder to compute query embedding
    base = Path(__file__).resolve().parents[1]
    embedder = load_module_from_path(base / 'ingestion' / 'embedder.py', 'embedder')
    try:
        # Compute the embedding for the query
        q_emb = embedder.embed_chunks([args.query], backend='openai' if ('openai' in globals() or os.environ.get('OPENAI_API_KEY')) else 'dummy', model=args.model, batch_size=args.batch_size)[0]
    except Exception:
        q_emb = embedder.embed_chunks([args.query], backend='dummy')[0]

    # Execute the query on the Chroma collection
    res = coll.query(query_embeddings=[q_emb], n_results=args.n, include=['documents','metadatas','distances'])

    print('\nSearch results:')
    for i, (doc, meta, dist) in enumerate(zip(res['documents'][0], res['metadatas'][0], res['distances'][0])):
        print(f"#{i+1}: chunk_index={meta.get('chunk_index')} distance={dist}")
        print(' preview:', doc[:300].replace('\n',' '))
        print()

if __name__ == '__main__':
    main()

