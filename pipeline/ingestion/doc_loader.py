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
    # Public API: given a directory path, return a list of document records.
    # Each record is a dict: {"path": str, "text": str, "type": 'pdf'|'text'|'other'}
    base = Path(dir_path)
    docs = []
    if not base.exists():
        return [{"path": str(base), "text": "[Directory not found]", "type": "none"}]

    for p in sorted(base.rglob("*")):
        if p.is_file():
            lower = p.suffix.lower()
            if lower == ".pdf":
                # For PDFs use the PDF extractor which internally handles OCR fallbacks.
                txt = _extract_pdf_text(p)
                docs.append({"path": str(p), "text": txt, "type": "pdf"})
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
