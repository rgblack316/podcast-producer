"""Turns an uploaded reference document (docx, pdf, rtf, odt, html, md, txt, ...) into plain text."""
import io
import os
import re
import zipfile

from docx_utils import extract_text as _docx_text

TEXT_EXTS = {".txt", ".text", ".md", ".markdown", ".csv", ".tsv", ".log", ".rst", ".json", ".yaml", ".yml", ".xml"}
SUPPORTED = sorted(TEXT_EXTS | {".docx", ".pdf", ".rtf", ".odt", ".html", ".htm"})
MAX_PDF_PAGES = 400
MAX_CHARS = 2_000_000
MAX_ODT_XML = 30 * 1024 * 1024


class UnsupportedDocument(ValueError):
    pass


def ext_of(filename: str) -> str:
    return os.path.splitext((filename or "").lower())[1]


def _decode(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise UnsupportedDocument("This PDF is password-protected")
    pages = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        t = (page.extract_text() or "").strip()
        if t:
            pages.append(t)
    return "\n\n".join(pages)


def _rtf(data: bytes) -> str:
    from striprtf.striprtf import rtf_to_text
    return rtf_to_text(_decode(data), errors="ignore")


def _html(data: bytes) -> str:
    from lxml import html as lh
    tree = lh.fromstring(_decode(data))
    for bad in tree.xpath("//script|//style|//noscript|//head"):
        bad.getparent().remove(bad)
    for br in tree.xpath("//br"):
        br.tail = "\n" + (br.tail or "")
    for el in tree.xpath("//p|//div|//li|//tr|//h1|//h2|//h3|//h4|//h5|//h6"):
        el.tail = "\n" + (el.tail or "")
    return tree.text_content()


def _odt(data: bytes) -> str:
    import defusedxml.ElementTree as ET
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        info = z.getinfo("content.xml")
        if info.file_size > MAX_ODT_XML:
            raise UnsupportedDocument("This document is too large to read")
        root = ET.fromstring(z.read(info))
    out = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag in ("p", "h"):
            out.append("".join(el.itertext()).strip())
    return "\n\n".join(t for t in out if t)


def extract(filename: str, data: bytes) -> str:
    ext = ext_of(filename)
    if ext == ".docx":
        text = _docx_text(data)
    elif ext == ".pdf":
        text = _pdf(data)
    elif ext == ".rtf":
        text = _rtf(data)
    elif ext == ".odt":
        text = _odt(data)
    elif ext in (".html", ".htm"):
        text = _html(data)
    elif ext in TEXT_EXTS:
        if b"\x00" in data[:4096] and data[:2] not in (b"\xff\xfe", b"\xfe\xff"):
            raise UnsupportedDocument("This looks like a binary file, not text")
        text = _decode(data)
    else:
        raise UnsupportedDocument(f"Unsupported file type. Use one of: {', '.join(SUPPORTED)}")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:MAX_CHARS]
