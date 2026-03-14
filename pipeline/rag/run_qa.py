"""CLI runner for Retriever + RAG QA

Usage:
    python3 pipeline/rag/run_qa.py --embeddings docs/webgoat_embeddings.json --query "deploy the war file" --top-k 3

If OPENAI_API_KEY is set and the `openai` package is installed, the runner will call OpenAI chat to
produce a concise answer. Otherwise it will print the retrieved contexts for manual inspection.
"""
import argparse
from pathlib import Path
import json
import sys

from pipeline.rag.qa import answer_query


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--embeddings', default='docs/webgoat_embeddings.json', help='Path to embeddings JSON')
    parser.add_argument('--query', required=True, help='Query to ask')
    parser.add_argument('--top-k', type=int, default=3, help='Number of chunks to retrieve')
    parser.add_argument('--openai-model', default='gpt-4o-mini', help='OpenAI chat model to use if available')
    args = parser.parse_args()

    emb_path = Path(args.embeddings)
    if not emb_path.exists():
        print('Embeddings JSON not found:', emb_path)
        sys.exit(2)

    res = answer_query(str(emb_path), args.query, top_k=args.top_k, openai_model=args.openai_model)
    print('\n=== RESULT ===')
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

