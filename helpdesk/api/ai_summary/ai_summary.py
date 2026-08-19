"""AI summary endpoint for the "Tải file lên" feature on the new-ticket page.

A synchronous convenience that reads an uploaded file (File doctype), turns
it into plain text, optionally compresses it, and asks an LLM for a ticket
title + description. Strict budgets (App Guard, conversion timeouts, text
compression, LLM timeout) guarantee the whole pipeline finishes well inside
the ~20s the frontend is willing to wait. No background job / queue is used.

Response shape:

    {
        "success": bool,
        "title": str | null,
        "summary": str | null,
        "reason": "ok" | "not_enough_information" | "irrelevant_content"
                 | "limit_exceeded" | "processing_failed"
                 | "rate_limited" | "too_many_files" | "file_too_large"
                 | "unsupported_file_type",
    }
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import frappe

from helpdesk.api.ai_summary.converters import (
    MIN_MEANINGFUL_CHARS,
    SUPPORTED_FILE_TYPES,
    ConversionError,
    convert_file,
    meaningful_chars,
)
from helpdesk.api.ai_summary.llm import LLMError, log_error, summarize_text
from helpdesk.api.ai_summary.text_compression import (
    PER_FILE_CHAR_LIMIT,
    TOTAL_CHAR_LIMIT,
    compress_text,
)

MAX_FILES_PER_CALL = 3
MAX_FILE_SIZE_MB = 15
RATE_LIMIT_PER_USER = 15
RATE_LIMIT_WINDOW_MINUTES = 10

# Whole pipeline should finish well inside the frontend budget (~30s).
# OCR of a scanned page needs more room than plain text conversion.
PRE_LLM_BUDGET_SECONDS = 15


class GuardError(Exception):
    """Rejected by the App Guard, before any expensive work happens."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class AppGuard:
    """Layer 1 — fastest checks first, nothing heavy.

    Whitelist file types, cap size and count, and rate-limit per user via
    Redis INCR + TTL. Any violation short-circuits the pipeline.
    """

    def __init__(self, file_names: list[str]):
        self.file_names = file_names or []
        self.max_files = conf_int(
            "ai_summary_max_files_per_call", MAX_FILES_PER_CALL
        )
        self.max_size_bytes = (
            conf_int("ai_summary_max_file_size_mb", MAX_FILE_SIZE_MB) * 1024 * 1024
        )
        self.rate_limit = conf_int(
            "ai_summary_rate_limit_per_user", RATE_LIMIT_PER_USER
        )
        self.rate_window_seconds = (
            conf_int(
                "ai_summary_rate_limit_window_minutes",
                RATE_LIMIT_WINDOW_MINUTES,
            )
            * 60
        )

    def check(self):
        if len(self.file_names) == 0:
            raise GuardError("processing_failed")
        if len(self.file_names) > self.max_files:
            raise GuardError("too_many_files")
        if not self.check_rate_limit():
            raise GuardError("rate_limited")

    def check_rate_limit(self) -> bool:
        cache = frappe.cache()
        key = cache.make_key("ai_summary:summarize", user=True)
        current = cache.incrby(key, 1)
        if current == 1:
            cache.expire(key, self.rate_window_seconds)
        return current <= self.rate_limit

    def load_files(self) -> list:
        """Fetch and validate the File docs referenced by `file_names`."""
        files = []
        for name in self.file_names:
            file = self.get_file(name)
            ftype = guess_file_type(file)
            if ftype not in SUPPORTED_FILE_TYPES:
                raise GuardError("unsupported_file_type")
            if (file.file_size or 0) > self.max_size_bytes:
                raise GuardError("file_too_large")
            files.append(file)
        return files

    def get_file(self, name) -> object:
        if not name or not frappe.db.exists("File", name):
            raise GuardError("processing_failed")
        file = frappe.get_doc("File", name)
        if file.owner != frappe.session.user and not frappe.has_permission(
            "File", "read", doc=file
        ):
            raise GuardError("processing_failed")
        return file


def guess_file_type(file) -> str:
    raw = (file.get("file_type") or "").lower()
    if raw:
        return raw
    return (file.file_name or "").rsplit(".", 1)[-1].lower()


def conf_int(name: str, default: int) -> int:
    try:
        return int(frappe.conf.get(name) or default)
    except (TypeError, ValueError):
        return default


@frappe.whitelist(methods=["POST"])
def ai_summarize_files(file_names: list[str]) -> dict:
    """Process uploaded files and return an AI-suggested title + summary."""
    start = time.time()

    guard = AppGuard(file_names)
    try:
        guard.check()
        files = guard.load_files()
    except GuardError as e:
        log_error(
            "AI Summary", f"guard rejected: {e.reason}", include_traceback=False
        )
        return failure(e.reason)

    if not files:
        log_error("AI Summary", "no files loaded", include_traceback=False)
        return failure("processing_failed")

    # Read file bytes on this thread: `frappe.local` is thread-local and not
    # bound inside the worker threads, while `get_content()` may touch it.
    prepared = []
    for f in files:
        try:
            content = f.get_content() or b""
        except Exception as e:  # noqa: BLE001
            log_error("AI Summary", f"failed reading {f.file_name}: {e}")
            return failure("processing_failed")
        prepared.append((f, content))
    log_error("AI Summary", f"read files took {time.time() - start:.3f}s", include_traceback=False)

    # Layer 2 — convert every file to text, in parallel (each bounded to 5s).
    texts = {}
    workers = max(1, min(len(files), MAX_FILES_PER_CALL))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_convert_one, f, content): f for f, content in prepared}
        for future in as_completed(futures):
            file = futures[future]
            try:
                text = future.result()
            except ConversionError as e:
                log_error("AI Summary", f"failed converting {file.file_name}: {e}")
                return failure("processing_failed")
            if text:
                texts[file.name] = text

    if not texts:
        log_error(
            "AI Summary", "no file produced readable text", include_traceback=False
        )
        return failure("processing_failed")
    log_error(
        "AI Summary",
        f"convert files took {time.time() - start:.3f}s",
        include_traceback=False,
    )

    if time.time() - start > PRE_LLM_BUDGET_SECONDS:
        log_error(
            "AI Summary",
            f"pipeline took too long before LLM ({time.time() - start:.1f}s)",
            include_traceback=False,
        )
        return failure("processing_failed")

    # Layer 3 — compress per-file (3k) then combined (10k) with sumy.
    combined = "\n\n".join(
        compress_text(text, PER_FILE_CHAR_LIMIT) for text in texts.values()
    )
    combined = compress_text(combined, TOTAL_CHAR_LIMIT)
    log_error(
        "AI Summary",
        f"compress took {time.time() - start:.3f}s",
        include_traceback=False,
    )

    if len(meaningful_chars(combined)) < MIN_MEANINGFUL_CHARS:
        return {
            "success": True,
            "title": None,
            "summary": None,
            "reason": "not_enough_information",
        }

    if time.time() - start > PRE_LLM_BUDGET_SECONDS:
        log_error(
            "AI Summary",
            f"pipeline took too long before LLM ({time.time() - start:.1f}s)",
            include_traceback=False,
        )
        return failure("processing_failed")

    # Layer 4 — ask the LLM (bounded to 10s).
    try:
        result = summarize_text(combined)
    except LLMError as e:
        log_error("AI Summary", f"LLM failed: {e}")
        return failure("processing_failed")
    log_error(
        "AI Summary",
        f"LLM took {time.time() - start:.3f}s total; total pipeline {time.time() - start:.3f}s",
        include_traceback=False,
    )

    return {
        "success": True,
        "title": result["title"],
        "summary": result["summary"],
        "reason": result["reason"],
    }


def _convert_one(file, content: bytes) -> str:
    return convert_file(content, file.file_name, guess_file_type(file))


def failure(reason: str) -> dict:
    return {
        "success": False,
        "title": None,
        "summary": None,
        "reason": reason,
    }
