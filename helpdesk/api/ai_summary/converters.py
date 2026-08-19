"""File → text/markdown converters for the AI summary feature.

Layer 2 of the pipeline: turns a file's raw bytes into plain text/markdown.
Every conversion runs inside a hard timeout so a single slow file can never
hold the request hostage. Each file type has its own converter and its own
5 second budget.

OCR (PDF scans and images) is deliberately restricted to the first page only
and shares the same 5 second budget — if it does not finish in time the whole
conversion is treated as failed and the caller stops, without retrying.
"""

import io
import re
import sys
import threading
import time

CONVERSION_TIMEOUT = 10  # seconds per file (OCR of a scan needs headroom)
MIN_MEANINGFUL_CHARS = 20


def log_step(step: str, seconds: float) -> None:
    """Emit a timing line to the container log for OCR debugging.

    Uses the same `[AI Summary]` prefix so it shows up in `docker logs
    backend` alongside the other AI Summary entries.
    """
    sys.stderr.write(f"[AI Summary] converters step {step}: {seconds:.3f}s\n")

# File types that can be handled by the pipeline (whitelisted by the App Guard).
# Values match the normalized (lowercased) `File.file_type` / filename extension.
SUPPORTED_FILE_TYPES = {
    "pdf",
    "docx",
    "xlsx",
    "csv",
    "txt",
    "md",
    "markdown",
    "png",
    "jpg",
    "jpeg",
}


class ConversionError(Exception):
    """Raised when a file cannot be converted into meaningful text."""


def convert_file(content: bytes, filename: str, file_type: str) -> str:
    """Extract text/markdown from `content` of the given `file_type`.

    Returns extracted text. Raises `ConversionError` when the file cannot be
    read or does not contain enough meaningful text (fewer than
    `MIN_MEANINGFUL_CHARS` meaningful characters).
    """
    content = content or b""
    if isinstance(content, str):
        content = content.encode("utf-8")
    t0 = time.time()
    try:
        if file_type == "pdf":
            text = run_with_timeout(_convert_pdf, CONVERSION_TIMEOUT, content)
        elif file_type == "docx":
            text = run_with_timeout(_convert_docx, CONVERSION_TIMEOUT, content)
        elif file_type == "xlsx":
            text = run_with_timeout(_convert_xlsx, CONVERSION_TIMEOUT, content)
        elif file_type == "csv":
            text = run_with_timeout(_convert_csv, CONVERSION_TIMEOUT, content)
        elif file_type in ("txt", "md", "markdown"):
            text = run_with_timeout(_convert_txt, CONVERSION_TIMEOUT, content)
        elif file_type in ("png", "jpg", "jpeg"):
            text = run_with_timeout(_convert_image, CONVERSION_TIMEOUT, content)
        else:
            raise ConversionError(f"Unsupported file type: {file_type}")
    except ConversionError:
        raise
    except TimeoutError:
        raise ConversionError(f"Timed out reading file: {filename}")
    except Exception:
        raise ConversionError(f"Could not read file: {filename}")
    finally:
        log_step(f"convert {file_type} took", time.time() - t0)

    text = _clean_text(text or "")
    if len(meaningful_chars(text)) < MIN_MEANINGFUL_CHARS:
        raise ConversionError(f"Not enough meaningful content in file: {filename}")
    return text


def run_with_timeout(func, timeout, *args, **kwargs):
    """Run `func` on a daemon thread, failing after `timeout` seconds.

    The worker thread is never killed — a runaway converter finishes on its
    own in the background — but the caller stops waiting once the budget is
    exceeded. Conversions are bounded by construction (one PDF page, small
    images, first 20 spreadsheet rows) so any leftover work is short-lived.
    """
    result = {}

    def _target():
        try:
            result["value"] = func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 - surfaced to caller below
            result["error"] = e

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError(f"Operation timed out after {timeout}s")
    if "error" in result:
        raise result["error"]
    return result["value"]


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def meaningful_chars(text: str) -> str:
    return re.sub(r"[^\w]", "", text, flags=re.UNICODE)


def _convert_pdf(content: bytes) -> str:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # PyMuPDF < 1.24

    with fitz.open(stream=content, filetype="pdf") as doc:
        parts = []
        for page in doc:
            parts.append(page.get_text("text"))
        text = "\n".join(parts)

        # No text layer → scanned PDF. OCR the first page only.
        if len(meaningful_chars(text)) < MIN_MEANINGFUL_CHARS and len(doc) > 0:
            # 150 dpi keeps raster small enough that Tesseract OCR finishes
            # well inside the conversion budget even on a small container.
            r0 = time.time()
            pix = doc[0].get_pixmap(dpi=150)
            log_step("pdf render first page", time.time() - r0)
            pixel_bytes = pix.tobytes("png")
            log_step("pdf pixmap bytes len", len(pixel_bytes) / 1024)
            text = _ocr_image(pixel_bytes)
    return text


def _convert_docx(content: bytes) -> str:
    import mammoth

    result = mammoth.convert_to_markdown(io.BytesIO(content))
    return result.value


def _convert_xlsx(content: bytes) -> str:
    import pandas as pd

    df = pd.read_excel(io.BytesIO(content), nrows=20)
    return _dataframe_to_text(df)


def _convert_csv(content: bytes) -> str:
    import pandas as pd

    df = None
    for encoding in ("utf-8", "utf-8-sig", "cp1258", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(content), nrows=20, encoding=encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if df is None:
        df = pd.read_csv(io.BytesIO(content), nrows=20)
    return _dataframe_to_text(df)


def _dataframe_to_text(df) -> str:
    lines = [", ".join(str(c) for c in df.columns)]
    for row in df.itertuples(index=False):
        lines.append(", ".join("" if pd_value_missing(v) else str(v) for v in row))
    return "\n".join(lines)


def _convert_txt(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1258", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _convert_image(content: bytes) -> str:
    import cv2
    import numpy as np

    arr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ConversionError("Could not decode image")
    return _ocr_image(img)


def _ocr_image(image) -> str:
    """OCR a single image (numpy array or raw bytes) with Tesseract.

    The image is pre-processed with OpenCV (downscale, deskew, binarize)
    before OCR to improve accuracy. Language packs `vie` and `eng` are tried
    first; if neither is installed Tesseract falls back to its default.
    """
    import cv2
    import numpy as np
    import pytesseract

    if isinstance(image, (bytes, bytearray)):
        arr = np.frombuffer(image, np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    t0 = time.time()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    log_step("ocr cvtColor", time.time() - t0)

    t1 = time.time()
    gray = _downscale(gray)
    log_step("ocr downscale", time.time() - t1)

    t2 = time.time()
    gray = _deskew(gray)
    log_step("ocr deskew", time.time() - t2)

    t3 = time.time()
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    log_step("ocr threshold", time.time() - t3)

    for lang in ("vie+eng", "vie", "eng", None):
        try:
            kwargs = {} if lang is None else {"lang": lang}
            t4 = time.time()
            out = pytesseract.image_to_string(thresh, **kwargs)
            log_step(f"ocr tesseract lang={lang}", time.time() - t4)
            return out
        except pytesseract.TesseractError:
            continue
    raise ConversionError("Tesseract OCR is not available")


def _downscale(gray):
    import cv2

    height, width = gray.shape[:2]
    max_dim = 2000
    if max(height, width) <= max_dim:
        return gray
    scale = max_dim / max(height, width)
    return cv2.resize(
        gray,
        (int(width * scale), int(height * scale)),
        interpolation=cv2.INTER_AREA,
    )


def _deskew(gray):
    import cv2
    import numpy as np

    coords = np.column_stack(np.where(gray > 0))
    if len(coords) < 50:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return gray
    height, width = gray.shape[:2]
    matrix = cv2.getRotationMatrix2D((width // 2, height // 2), angle, 1.0)
    return cv2.warpAffine(
        gray,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def pd_value_missing(value):
    try:
        import pandas as pd

        return pd.isna(value)
    except Exception:
        return value is None
