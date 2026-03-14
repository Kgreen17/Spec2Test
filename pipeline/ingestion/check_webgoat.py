"""Check WebGoat PDF is present and loaded by the doc loader."""
import importlib.util
from pathlib import Path
import sys
import argparse
from typing import Optional

# Dynamically load the doc_loader module from the pipeline path
base_dir = Path(__file__).resolve().parents[1]
module_path = base_dir / "ingestion" / "doc_loader.py"
spec = importlib.util.spec_from_file_location("doc_loader", str(module_path))
doc_loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doc_loader)


def check_webgoat(docs_dir: Optional[str] = None) -> int:
    """Return codes:
    0 = success (found & extracted)
    2 = not found
    3 = found but empty extraction
    4 = found but extractor error
    """
    # Resolve docs_dir if not provided: repo root / docs
    if docs_dir:
        docs_path = Path(docs_dir)
    else:
        repo_root = Path(__file__).resolve().parents[2]
        docs_path = repo_root / "docs"

    # Normalize
    docs_path = docs_path.expanduser().resolve()

    docs = doc_loader.load_documents(str(docs_path))
    target = None
    for d in docs:
        if "webgoat" in d["path"].lower() or "webgoat" in d.get("text", "").lower():
            target = d
            break

    if not target:
        print(f"WebGoat PDF not found under {docs_path}")
        return 2

    print(f"Found: {target['path']}")
    print(f"Type: {target['type']}")

    text = target.get("text", "")
    if not text:
        print("No extracted text (empty string)")
        return 3

    if text.startswith("[PDF extraction unavailable") or text.startswith("[PDF read error") or text.startswith("[OCR unavailable"):
        print("PDF was found but text extraction is unavailable or failed.")
        print(f"Extractor message: {text.splitlines()[0]}")
        return 4

    # Print a short preview
    preview = " ".join(text.splitlines())[:1000]
    print("--- Text preview (first ~1000 chars) ---")
    print(preview)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check WebGoat PDF extraction")
    parser.add_argument("--docs", help="Path to docs directory (optional). If omitted, repo_root/docs is used", default=None)
    args = parser.parse_args()
    raise SystemExit(check_webgoat(args.docs))
