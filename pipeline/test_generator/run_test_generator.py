"""CLI runner for the test generator.

Usage examples:
  python -m pipeline.test_generator.run_test_generator --text "Login page has #username" --objective "verify login" --out out.json
  python pipeline/test_generator/run_test_generator.py --embeddings docs/webgoat_embeddings.json --objective "verify login" --out out.json
"""
from pathlib import Path
import argparse
import json
import sys
import importlib.util


def load_module_from_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--embeddings', help='Path to embeddings JSON (optional)')
    parser.add_argument('--context-file', help='Path to plain text context file (optional)')
    parser.add_argument('--text', help='Inline text context (optional)')
    parser.add_argument('--objective', help='Short objective for test plan', required=True)
    parser.add_argument('--max-steps', type=int, default=20)
    parser.add_argument('--out', default='-', help='Output path for plan JSON (use - for stdout)')
    parser.add_argument('--top-k', type=int, default=5, help='Top-k chunks to retrieve from embeddings')
    parser.add_argument('--model', default='gpt-4o')
    args = parser.parse_args(argv)

    context = None

    if args.embeddings:
        # load SimpleRetriever from pipeline/rag/retriever.py
        retriever_mod = load_module_from_path(Path(__file__).resolve().parents[2] / 'rag' / 'retriever.py', 'retriever')
        SimpleRetriever = getattr(retriever_mod, 'SimpleRetriever')
        r = SimpleRetriever(args.embeddings)
        # Use retrieve to get top-k chunks for a combined context string
        try:
            out = r.retrieve(args.objective, top_k=args.top_k)
            parts = [o['chunk'] for o in out]
            context = '\n\n'.join(parts)
        except Exception as e:
            print(json.dumps({'error': 'retriever_error', 'message': str(e)}))
            sys.exit(2)

    if args.context_file:
        context = Path(args.context_file).read_text(encoding='utf-8')

    if args.text:
        context = args.text

    if not context:
        print(json.dumps({'error': 'no_context', 'message': 'Provide --embeddings or --context-file or --text'}))
        sys.exit(3)

    # load generator
    gen_mod = load_module_from_path(Path(__file__).resolve().parents[1] / 'test_generator' / 'generator_agent.py', 'generator_agent')
    generate_test_plan = getattr(gen_mod, 'generate_test_plan')

    res = generate_test_plan(context=context, objective=args.objective, max_steps=args.max_steps, model=args.model)

    out_path = args.out
    if out_path == '-':
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        Path(out_path).write_text(json.dumps(res, ensure_ascii=False, indent=2))
        print(f'Wrote plan to {out_path}')


if __name__ == '__main__':
    main()

