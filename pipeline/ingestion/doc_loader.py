"""Doc loader: loads text from files under a directory.
Supports: .pdf (via PyPDF2 if installed), .txt, .md
Includes OCR fallback using PyMuPDF + pytesseract + Pillow when PDF text extraction returns empty.
"""

# This module exposes a single public function `load_documents(dir_path)` that:
# 1. Walks the directory tree under `dir_path` looking for files.
# 2. For each file, decides how to extract text based on suffix (.pdf/.md/.txt/other) file su.
# 3. For PDFs it first tries direct text extraction using PyPDF2.
#    - If PyPDF2 returns no text, it attempts OCR fallback(s):
#      a) Primary: render pages with PyMuPDF (fitz) and run pytesseract OCR on page images.
#      b) Secondary: use pdf2image (requires poppler) and pytesseract as an alternative.
# 4. Returns a list of dicts: {"path": str(path), "text": extracted_text_or_message, "type": "pdf"|"text"|"other"}.

from pathlib import Path
from typing import List
import argparse
import sys
import traceback
import os

# New optional imports will be attempted in helper functions when needed.
import csv


def _extract_docx_text(path: Path) -> str:
    try:
        import docx
    except Exception as e:
        return f"[DOCX extraction unavailable: missing package python-docx ({e})] {path}"

    try:
        doc = docx.Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text]
        return "\n\n".join(paragraphs)
    except Exception as e:
        return f"[DOCX read error: {e}] {path}"


def _extract_spreadsheet_text(path: Path) -> str:
    # Try pandas first (handles csv and Excel). Fall back to csv module for .csv.
    suffix = path.suffix.lower()
    try:
        import pandas as pd
    except Exception:
        pd = None

    if pd:
        try:
            if suffix == '.csv':
                df = pd.read_csv(str(path), dtype=str, encoding='utf-8', low_memory=False)
            else:
                # Excel (xls/xlsx)
                df = pd.read_excel(str(path), dtype=str)
            # Convert a sample of rows into readable text (limit to first 200 rows)
            rows = []
            max_rows = min(200, len(df))
            cols = df.columns.tolist()
            rows.append(' | '.join(map(str, cols)))
            for i in range(max_rows):
                row = df.iloc[i].fillna('')
                rows.append(' | '.join(str(x) for x in row.tolist()))
            return '\n'.join(rows)
        except Exception as e:
            return f"[Spreadsheet parsing error (pandas): {e}] {path}"
    else:
        # No pandas: if CSV try the csv module, otherwise return helpful message
        if suffix == '.csv':
            try:
                with open(path, newline='', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    lines = []
                    for i, row in enumerate(reader):
                        lines.append(', '.join(row))
                        if i > 200:
                            break
                return '\n'.join(lines)
            except Exception as e:
                return f"[CSV read error: {e}] {path}"
        else:
            return f"[Spreadsheet extraction unavailable: install pandas for Excel support] {path}"


def _fetch_url_text(url: str) -> str:
    # First try to fetch Confluence/Jira content using link_extractor
    try:
        from . import link_extractor
        
        # Support optional basic auth for Confluence using env vars
        auth = None
        user = os.environ.get('CONFLUENCE_USER')
        token = os.environ.get('CONFLUENCE_TOKEN')
        if user and token:
            auth = (user, token)
        
        result = link_extractor.fetch_link_content(url, auth)
        if result:
            content = result.get('content', '')
            source_type = result.get('type', 'unknown')
            return f"[Source: {source_type}]\n\n{content}"
    except Exception as e:
        pass  # Fall back to basic HTML extraction
    
    # Fallback: generic HTML fetch
    try:
        import requests
    except Exception as e:
        return f"[URL fetch unavailable: missing package requests ({e})] {url}"

    # Support optional basic auth for Confluence using env vars
    auth = None
    user = os.environ.get('CONFLUENCE_USER')
    token = os.environ.get('CONFLUENCE_TOKEN')
    if user and token:
        auth = (user, token)

    try:
        resp = requests.get(url, auth=auth, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return f"[URL fetch error: {e}] {url}"

    # Parse HTML with BeautifulSoup if available, otherwise strip tags roughly
    try:
        from bs4 import BeautifulSoup
    except Exception:
        # Fallback: remove tags naively
        import re
        text = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.S | re.I)
        text = re.sub(r'<[^>]+>', '', text)
        return text

    try:
        soup = BeautifulSoup(html, 'html.parser')
        # Confluence often stores page contents inside <div id="main-content"> or <div id="content"> or <article>
        content = None
        for sel in ['#main-content', '#content', 'article', 'div#main-content', 'div#content', 'div#content-body', 'div.wiki-content', 'div.ak-renderer-document']:
            el = soup.select_one(sel)
            if el:
                content = el
                break
        if content is None:
            # fallback to the largest <div> or the body
            divs = soup.find_all('div')
            if divs:
                # pick the div with the most text
                divs_sorted = sorted(divs, key=lambda d: len(d.get_text() or ''), reverse=True)
                content = divs_sorted[0]
            else:
                content = soup.body or soup

        # Extract visible text, collapse whitespace
        text = content.get_text()
        text = (text or '').strip()
        return text or f"[No extractable text found in HTML] {url}"
    except Exception as e:
        return f"[HTML parse error: {e}] {url}"


def _ocr_pdf_text_with_pymupdf(path: Path) -> str:
    # Attempt to perform OCR on each PDF page using PyMuPDF (fitz) to render page images
    # and pytesseract to extract text from the images.
    # Returns the OCR'd text or an informative error message string starting with "[OCR unavailable" or "[OCR render error".
    try:
        import fitz  # PyMuPDF
        from PIL import Image
        import pytesseract
    except Exception as e:
        return f"[OCR unavailable: missing package: {e}] {path}"

    texts = []
    try:
        doc = fitz.open(str(path))
        for page in doc:
            # render the page to an image (higher dpi for better OCR)
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                mode = "RGBA" if pix.alpha else "RGB"
                # Pillow expects size as a tuple
                img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
                if mode == "RGBA":
                    img = img.convert("RGB")
                # pytesseract.image_to_string returns extracted text for the image
                txt = pytesseract.image_to_string(img)
                if txt:
                    texts.append(txt)
            except Exception:
                # On a single page render/OCR failure, continue to the next page.
                continue
        doc.close()
    except Exception as e:
        # Return a helpful message for upstream logging instead of raising.
        return f"[OCR render error: {e}] {path}"

    return "\n\n".join(texts) or ""


def _ocr_pdf_text_with_pdf2image(path: Path) -> str:
    # Secondary OCR method: convert PDF pages to images using pdf2image (which requires the
    # `pdftoppm` binary from poppler), then run pytesseract on those images.
    # This is a fallback if PyMuPDF is unavailable or fails.
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception as e:
        return f"[OCR unavailable: missing package: {e}] {path}"

    texts = []
    try:
        images = convert_from_path(str(path), dpi=200)
        for img in images:
            txt = pytesseract.image_to_string(img)
            if txt:
                texts.append(txt)
    except Exception as e:
        return f"[pdf2image OCR error: {e}] {path}"

    return "\n\n".join(texts) or ""


def _extract_pdf_text(path: Path) -> str:
    # Primary extraction: try PyPDF2 (fast) to extract selectable text.
    # If PyPDF2 is missing, or it finds no text, fall back to OCR methods above.
    try:
        import PyPDF2
    except Exception:
        # If PyPDF2 is missing, attempt OCR directly and return an informative message.
        ocr = _ocr_pdf_text_with_pymupdf(path)
        if ocr and not ocr.startswith("[OCR unavailable"):
            return "[OCR fallback used] \n\n" + ocr
        return f"[PDF extraction unavailable: PyPDF2 not installed] {path}"

    text_parts = []
    try:
        with open(path, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            for page in reader.pages:
                # Some PDFs have pages with extractable text, others do not.
                # We attempt extract_text() and aggregate any non-empty results.
                text = getattr(page, "extract_text", None)
                if callable(text):
                    t = text()
                    if t:
                        text_parts.append(t)
                else:
                    try:
                        t = page.extract_text()
                        if t:
                            text_parts.append(t)
                    except Exception:
                        continue
    except Exception as e:
        # Return a message instead of raising so callers can decide how to proceed.
        return f"[PDF read error: {e}] {path}"

    extracted = "\n\n".join(text_parts) or ""

    # If PyPDF2 returned nothing, attempt OCR fallbacks in order.
    if not extracted.strip():
        ocr_text = _ocr_pdf_text_with_pymupdf(path)
        if ocr_text and not ocr_text.startswith("[OCR unavailable") and not ocr_text.startswith("[OCR render error"):
            return "[OCR fallback used] \n\n" + ocr_text

        ocr_text2 = _ocr_pdf_text_with_pdf2image(path)
        if ocr_text2 and not ocr_text2.startswith("[OCR unavailable") and not ocr_text2.startswith("[pdf2image OCR error"):
            return "[OCR fallback (pdf2image) used] \n\n" + ocr_text2

        # If OCR also failed, prefer a helpful message describing the failure.
        if ocr_text:
            return ocr_text
        if ocr_text2:
            return ocr_text2

    return extracted

def _read_text_file(path: Path) -> str:
    # Read .txt or .md files, try utf-8 first then latin-1 as a fallback encoding.
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        try:
            return path.read_text(encoding="latin-1")
        except Exception as e:
            return f"[File read error: {e}] {path}"


def load_documents(dir_path: str) -> List[dict]:
    # Public API: given a directory path or a URL or file path, return a list of document records.
    # Each record is a dict: {"path": str, "text": str, "type": 'pdf'|'text'|'docx'|'spreadsheet'|'html'|'other'}
    base = Path(dir_path) if dir_path and not (dir_path.startswith('http://') or dir_path.startswith('https://')) else dir_path
    docs = []

    # If the caller passed a URL string, fetch it and return one record
    if isinstance(base, str) and (base.startswith('http://') or base.startswith('https://')):
        txt = _fetch_url_text(base)
        docs.append({"path": base, "text": txt, "type": "html"})
        return docs

    # If it's a file path, process the single file
    if isinstance(base, Path) and base.exists() and base.is_file():
        p = base
        lower = p.suffix.lower()
        if lower == ".pdf":
            txt = _extract_pdf_text(p)
            docs.append({"path": str(p), "text": txt, "type": "pdf"})
            return docs
        if lower == ".docx":
            txt = _extract_docx_text(p)
            docs.append({"path": str(p), "text": txt, "type": "docx"})
            return docs
        if lower in ('.csv', '.xls', '.xlsx'):
            txt = _extract_spreadsheet_text(p)
            docs.append({"path": str(p), "text": txt, "type": "spreadsheet"})
            return docs
        if lower in ('.txt', '.md'):
            txt = _read_text_file(p)
            docs.append({"path": str(p), "text": txt, "type": "text"})
            return docs
        # unknown single file
        docs.append({"path": str(p), "text": "[skipped non-text file]", "type": "other"})
        return docs

    # Otherwise treat base as a directory path (existing logic)
    if not isinstance(base, Path):
        base = Path(dir_path)

    if not base.exists():
        return [{"path": str(base), "text": "[Directory not found]", "type": "none"}]

    for p in sorted(base.rglob("*")):
        if p.is_file():
            lower = p.suffix.lower()
            if lower == ".pdf":
                # For PDFs use the PDF extractor which internally handles OCR fallbacks.
                txt = _extract_pdf_text(p)
                docs.append({"path": str(p), "text": txt, "type": "pdf"})
            elif lower == ".docx":
                txt = _extract_docx_text(p)
                docs.append({"path": str(p), "text": txt, "type": "docx"})
            elif lower in ('.csv', '.xls', '.xlsx'):
                txt = _extract_spreadsheet_text(p)
                docs.append({"path": str(p), "text": txt, "type": "spreadsheet"})
            elif lower in (".txt", ".md"):
                # For plain text/markdown read the file directly.
                txt = _read_text_file(p)
                docs.append({"path": str(p), "text": txt, "type": "text"})
            else:
                # For other binary files we skip text extraction but record the file.
                docs.append({"path": str(p), "text": "[skipped non-text file]", "type": "other"})

    return docs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load documents from a docs directory and print previews")
    parser.add_argument("--docs", help="Path to docs directory (optional). If omitted, resolver will try several common locations", default=None)
    args = parser.parse_args()

    # Candidate resolution: explicit --docs, repo_root/docs, repo_root/ai-ui-testing-agent/docs, cwd/docs
    candidates = []
    if args.docs:
        candidates.append(Path(args.docs).expanduser().resolve())

    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "docs")
    candidates.append(repo_root / "ai-ui-testing-agent" / "docs")
    candidates.append(Path.cwd() / "docs")

    print("Resolver candidates (in order):")
    for c in candidates:
        print(" -", c)
    sys.stdout.flush()

    docs_dir = None
    for c in candidates:
        try:
            if c.exists() and c.is_dir():
                docs_dir = c
                break
        except Exception as e:
            print(f"Error checking candidate {c}: {e}")
            traceback.print_exc()
            sys.stdout.flush()

    if docs_dir is None:
        print("No docs directory found. Tried the candidates above.")
        sys.stdout.flush()
        sys.exit(2)

    print(f"Using docs_dir: {docs_dir}")
    sys.stdout.flush()

    try:
        docs = load_documents(str(docs_dir))
        print(f"load_documents returned {len(docs)} entries")
        for d in docs:
            print(f"--- {d['type']} : {d['path']} ---")
            preview = (d.get('text') or '')[:1000].replace("\n", " ")
            print(preview)
            print()
        sys.stdout.flush()
    except Exception as e:
        print(f"Exception while loading documents: {e}")
        traceback.print_exc()
        sys.stdout.flush()
