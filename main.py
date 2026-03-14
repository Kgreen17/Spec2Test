"""Orchestrator CLI (main) for the current pipeline.

This script exercises the flow implemented in `pipeline/ingestion` and `pipeline/rag`:
- discovers docs (docs/ by default)
- loads the WebGoat PDF (or first matching doc)
- chunks the text
- computes embeddings (OpenAI when available, otherwise dummy)
- optionally saves embeddings to JSON
- optionally persists embeddings into a local Chroma DB
- runs a sample retrieval to demonstrate everything wired up

Usage examples:
    python3 main.py --docs docs --save out.json --persist-chroma --collection webgoat

Notes:
- Requires OpenAI key in OPENAI_API_KEY env var for real embeddings (or will use dummy embeddings)
- Chromadb operations are optional (install chromadb if you want persistence)
"""

from pathlib import Path
import argparse
import json
import sys
import os
import importlib.util


def load_module_from_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default=None, help="Docs dir (defaults to ./docs)")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--tokenize", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=200)
    parser.add_argument("--overlap-tokens", type=int, default=20)
    parser.add_argument("--model", default="text-embedding-3-small", help="OpenAI embedding model")
    parser.add_argument("--planner-model", default="gpt-3.5-turbo", help="LLM model to use for test planner (chat model)")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--save", default=None, help="Save chunks+embeddings to JSON")
    parser.add_argument("--persist-chroma", action="store_true", help="Persist embeddings into local Chroma DB (requires chromadb)")
    parser.add_argument("--collection", default="webgoat", help="Chroma collection name")
    parser.add_argument("--persist-dir", default="db/chroma", help="Chroma persist directory")
    parser.add_argument("--query", default="deploy the war file", help="Demo query to run against the embeddings")
    parser.add_argument("--n", type=int, default=3, help="Number of results to return")
    parser.add_argument("--generate-tests", action="store_true", help="Run LLM test planner after embeddings are generated")
    parser.add_argument("--test-objective", default=None, help="Short objective for test generation (if omitted a default will be used)")
    parser.add_argument("--test-max-steps", type=int, default=20, help="Maximum number of steps for the generated test plan")
    parser.add_argument("--tests-out", default=None, help="Path to write generated test plan JSON (defaults to ./generated_test_plan.json if --generate-tests)")
    # Executor / Allure options
    parser.add_argument("--run-executor", action="store_true", help="Run the Playwright executor on the generated test plan")
    parser.add_argument("--simulate-executor", action="store_true", help="Run executor in simulate-only mode (safe, no browser launched)")
    parser.add_argument("--executor-out", default="reports/generated_test_plan_report.json", help="Path to write executor run report JSON")
    parser.add_argument("--allure-generate", action="store_true", help="Convert executor report into Allure results and attempt to generate HTML report (requires Allure CLI)")
    parser.add_argument("--allure-open", action="store_true", help="Open the generated Allure report in a browser (runs `allure open`) when used with --allure-generate")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    # Accept --docs as a URL, a file path, or a directory. If not provided, default to repo_root/docs
    if args.docs:
        docs_input = args.docs.strip()
        if docs_input.startswith('http://') or docs_input.startswith('https://'):
            docs_source = docs_input
            print(f"Using docs URL: {docs_source}")
        else:
            p = Path(docs_input).expanduser().resolve()
            if not p.exists():
                print(f"Docs path not found: {p}")
                sys.exit(2)
            docs_source = p
            print(f"Using docs path: {docs_source}")
    else:
        docs_source = repo_root / 'docs'
        print(f"Using default docs directory: {docs_source}")
        if not docs_source.exists():
            print(f"Docs directory not found: {docs_source}")
            sys.exit(2)

    base = Path(__file__).resolve().parent / "pipeline" / "ingestion"
    doc_loader = load_module_from_path(base / 'doc_loader.py', 'doc_loader')
    chunker = load_module_from_path(base / 'chunker.py', 'chunker')
    embedder = load_module_from_path(base / 'embedder.py', 'embedder')

    print(f"Loading documents from: {docs_source}")
    docs = doc_loader.load_documents(str(docs_source))
    if not docs:
        print("No documents found.")
        sys.exit(3)

    # pick a document (prefer webgoat-named file if present)
    target = None
    for d in docs:
        p = d.get('path','') or ''
        t = (d.get('text') or '').lower()
        if 'webgoat' in p.lower() or 'webgoat' in t:
            target = d
            break
    if not target:
        target = docs[0]
        print(f"No WebGoat doc found; using first document: {target.get('path')}")

    text = target.get('text','') or ''
    if not text or text.startswith('[PDF extraction unavailable'):
        print('Selected document has no usable text. Exiting.')
        sys.exit(4)

    if args.tokenize:
        print('Chunking by tokens...')
        chunks = chunker.chunk_text_by_tokens(text, max_tokens=args.max_tokens, overlap_tokens=args.overlap_tokens, model=args.model)
    else:
        print('Chunking by characters...')
        chunks = chunker.chunk_text(text, chunk_size=args.chunk_size)

    print(f"Created {len(chunks)} chunks")

    # Determine backend choice (prefer OpenAI if key available)
    try:
        from pipeline.openai_utils import get_openai_api_key
        has_key = bool(get_openai_api_key(required=False))
    except Exception:
        has_key = bool(os.environ.get('OPENAI_API_KEY'))

    backend = 'openai' if has_key else 'dummy'
    print(f"Embedding backend: {backend}")

    try:
        embeddings = embedder.embed_chunks(chunks, backend=backend, model=args.model, batch_size=args.batch_size)
    except Exception as e:
        print('Embedding failed:', e)
        sys.exit(5)

    if not embeddings or len(embeddings) != len(chunks):
        print('Embedding count mismatch')
        sys.exit(6)

    print(f"Generated {len(embeddings)} embeddings (dim={len(embeddings[0]) if embeddings else 0})")

    saved_json = None
    if args.save:
        out = {
            'source': target.get('path'),
            'chunk_size': args.chunk_size,
            'backend': backend,
            'chunks': chunks,
            'embeddings': embeddings,
        }
        out_path = Path(args.save)
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        saved_json = str(out_path)
        print(f"Saved embeddings to {out_path}")

    if args.persist_chroma:
        try:
            import chromadb
            from chromadb.config import Settings
            client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=str(Path(args.persist_dir))))
            coll = None
            try:
                coll = client.get_collection(args.collection)
                print('Using existing Chroma collection:', args.collection)
            except Exception:
                coll = client.create_collection(args.collection)
                print('Created Chroma collection:', args.collection)

            ids = [f"chunk_{i}" for i in range(len(chunks))]
            metadatas = [{'source': target.get('path'), 'chunk_index': i} for i in range(len(chunks))]
            documents = [c[:1000] for c in chunks]
            coll.add(ids=ids, metadatas=metadatas, documents=documents, embeddings=embeddings)
            try:
                # Some chromadb client versions expose persist() on the client; others may use different APIs.
                # Wrap in try/except to avoid hard failures for different versions.
                client.persist()
            except Exception:
                pass
            print(f"Persisted {len(ids)} embeddings to Chroma collection '{args.collection}' at {args.persist_dir}")
        except Exception as e:
            print('Chroma persistence failed (is chromadb installed?):', e)

    # Run a demo retrieval: prefer Chroma query if persisted, otherwise use SimpleRetriever on saved JSON
    if args.persist_chroma:
        try:
            print('Running demo query against Chroma...')
            # do a raw query by computing query embedding
            try:
                q_emb = embedder.embed_chunks([args.query], backend=backend, model=args.model, batch_size=args.batch_size)[0]
            except Exception as e:
                print('Failed to embed query for Chroma:', e)
                q_emb = None

            if q_emb is not None:
                res = coll.query(query_embeddings=[q_emb], n_results=args.n, include=['documents','metadatas','distances'])
                print('\nSearch results (Chroma):')
                for i, (doc, meta, dist) in enumerate(zip(res['documents'][0], res['metadatas'][0], res['distances'][0])):
                    print(f"#{i+1}: chunk_index={meta.get('chunk_index')} distance={dist}")
                    print(' preview:', doc[:300].replace('\n',' '))
                    print()
        except Exception as e:
            print('Chroma query failed:', e)

    if not args.persist_chroma:
        # If we saved JSON, use SimpleRetriever; otherwise save to a temp file and use it
        json_path = saved_json or (repo_root / 'docs' / 'webgoat_embeddings.json')
        if not Path(json_path).exists():
            # if no saved json, create a temporary file in current working dir
            tmp_path = Path('out_embeddings.json')
            tmp_path.write_text(json.dumps({'source': target.get('path'), 'chunks': chunks, 'embeddings': embeddings}, ensure_ascii=False, indent=2))
            json_path = str(tmp_path)

        print('Running demo retrieval using SimpleRetriever...')
        # load retriever module and run retrieve
        retriever_mod = load_module_from_path(Path(__file__).resolve().parent / 'pipeline' / 'rag' / 'retriever.py', 'retriever')
        SimpleRetriever = getattr(retriever_mod, 'SimpleRetriever')
        r = SimpleRetriever(json_path)
        out = r.retrieve(args.query, top_k=args.n, embed_kwargs={'model': args.model, 'batch_size': args.batch_size})
        print('\nSearch results (SimpleRetriever):')
        for o in out:
            print(f"index={o['index']} score={o['score']}")
            print(o['chunk'][:400].replace('\n',' '))
            print()

    print('Flow complete')

    # --- Test generation step (LLM planner) ---
    if args.generate_tests:
        # assemble context for planner: prefer joined chunks (top K) or the saved JSON if present
        print('Running LLM Test Planner...')
        try:
            gen_mod = load_module_from_path(Path(__file__).resolve().parent / 'pipeline' / 'test_generator' / 'generator_agent.py', 'generator_agent')
            generate_test_plan = getattr(gen_mod, 'generate_test_plan')

            # Use a reasonable subset of chunks as context to avoid huge prompts
            ctx_chunks = chunks[:min(20, len(chunks))]
            context_text = '\n\n'.join(ctx_chunks)
            objective = args.test_objective or f"Generate a test plan to validate the feature described in the docs: {target.get('path')}"

            gen_res = generate_test_plan(context=context_text, objective=objective, max_steps=args.test_max_steps, model=args.planner_model)

            out_path = Path(args.tests_out) if args.tests_out else Path('generated_test_plan.json')
            out_path.write_text(json.dumps(gen_res, ensure_ascii=False, indent=2))
            print(f'Wrote generated test plan result to: {out_path}')

            if 'plan' in gen_res:
                print('Test plan generated successfully:')
                print(gen_res['plan']['test_name'])
            else:
                print('Test planner returned an error:', gen_res.get('error'), gen_res.get('message',''))

            # Optionally run executor and produce Allure results
            if args.run_executor:
                try:
                    print('Running executor on generated plan...')
                    # import runner module
                    exec_mod = load_module_from_path(Path(__file__).resolve().parent / 'pipeline' / 'agents' / 'executor' / 'playwright_runner.py', 'playwright_runner')
                    run_steps = getattr(exec_mod, 'run_steps')
                    # Determine steps source: use gen_res['plan']['steps'] if available else read from saved file
                    steps = gen_res.get('plan', {}).get('steps') if gen_res.get('plan') else None
                    if not steps:
                        # read from file
                        data = json.loads(out_path.read_text())
                        steps = data.get('plan', {}).get('steps', [])

                    executor_report = run_steps(steps, out_report=args.executor_out, headless=True, simulate_only=args.simulate_executor)
                    print(f'Executor finished. Report written to {args.executor_out}')

                    # Generate Allure results from the executor report
                    if args.allure_generate:
                        try:
                            print('Converting executor report into Allure results...')
                            gen_allure = load_module_from_path(Path(__file__).resolve().parent / 'pipeline' / 'agents' / 'executor' / 'generate_allure_results.py', 'generate_allure_results')
                            # reuse the module's main-like behavior: call make_result for each step
                            out_dir = Path('allure-results')
                            out_dir.mkdir(parents=True, exist_ok=True)
                            for s in executor_report.get('results', []):
                                gen_allure.make_result(s, out_dir)
                            print('Allure result files created in allure-results')

                            # Attempt to generate the HTML report if allure is installed
                            try:
                                import subprocess
                                subprocess.run(['allure', 'generate', 'allure-results', '-o', 'allure-report', '--clean'], check=True)
                                print('Allure HTML report generated at ./allure-report')
                                if args.allure_open:
                                    subprocess.run(['allure', 'open', 'allure-report'], check=False)
                            except Exception as e:
                                print('Allure CLI invocation failed or allure not installed. Result files are in ./allure-results. Install Allure CLI to generate the HTML report:', e)

                        except Exception as e:
                            print('Failed to generate Allure results:', e)
                except Exception as e:
                    print('Executor failed:', e)

        except Exception as e:
            print('Test generation failed:', e)
            import traceback as _tb
            _tb.print_exc()


if __name__ == '__main__':
    main()
