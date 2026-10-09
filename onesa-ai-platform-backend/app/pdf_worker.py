"""Disposable, secret-free PDF parser with POSIX CPU/address-space/output limits."""

import encodings
import importlib
import importlib.util
import io
import pkgutil
import resource
import sys
from pathlib import Path


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    # macOS address-space limits are not reliably supported; Linux deployment enforces it.
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    from pypdf import PdfReader

    data = sys.stdin.buffer.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024 or not data.startswith(b"%PDF-"):
        raise ValueError("Invalid input")
    # Preload supported codecs before denying additional file opens.
    for codec in pkgutil.iter_modules(encodings.__path__):
        try:
            importlib.import_module("encodings." + codec.name)
        except ImportError:
            pass  # Windows-only codecs are unavailable on the supported Linux/macOS path.
    # Isolated -I execution excludes the app directory: load the trusted sibling by file.
    spec = importlib.util.spec_from_file_location(
        "pdf_restrictions", Path(__file__).with_name("pdf_restrictions.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("PDF restrictions missing")
    restrictions = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(restrictions)
    restrictions.restrict()
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted or len(reader.pages) > 100:
        raise ValueError("Invalid PDF")
    pages = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        total += len(text) + 1
        if total > 256000:
            raise ValueError("Too much text")
        pages.append(text)
    sys.stdout.buffer.write("\n".join(pages).encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Parent exposes only the existing safe invalid_pdf error.
        raise SystemExit(1) from None
