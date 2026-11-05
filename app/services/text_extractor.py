"""Turn a downloaded PDF or web page into plain text."""
from __future__ import annotations

import io
import logging
import re

from bs4 import BeautifulSoup

from ..config import Config

log = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    text = (text or "").replace("\u00a0", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    return clean_text(soup.get_text("\n"))


def pdf_to_text(content: bytes) -> tuple[str, bool]:
    """Returns (text, looks_scanned). A scanned PDF is just pictures, so it has almost no text."""
    import pdfplumber

    pages_text, page_count = [], 0
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages[:Config.MAX_PDF_PAGES]:
                page_count += 1
                pages_text.append(page.extract_text() or "")
    except Exception as exc:
        log.warning("Could not read PDF (%s).", exc.__class__.__name__)
        return "", True
    text = clean_text("\n".join(pages_text))
    scanned = page_count > 0 and len(text) < 80
    if scanned:
        ocr_text = _try_ocr(content)
        if ocr_text:
            return clean_text(ocr_text), False
    return text, scanned


def _try_ocr(content: bytes) -> str:
    """Optional. Works only if pytesseract + pdf2image + Tesseract + Poppler are installed."""
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError:
        return ""
    try:
        images = convert_from_bytes(content, first_page=1, last_page=3)
        return "\n".join(pytesseract.image_to_string(img) for img in images)
    except Exception as exc:
        log.warning("OCR failed (%s).", exc.__class__.__name__)
        return ""
