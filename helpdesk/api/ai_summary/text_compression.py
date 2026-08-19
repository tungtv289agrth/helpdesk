"""Text compression for the AI summary feature.

Layer 3 of the pipeline: when extracted text exceeds a budget it is reduced
with the `sumy` library (TextRank) — the most important sentences are kept
instead of naively cutting the first N characters.

Budgets:
- per file: 3.000 characters
- per call (after combining multiple files): 10.000 characters

The audio definition of a "sentence" works for Vietnamese and other languages
that end sentences with `. ! ?` regardless of NLTK grammar data being present,
so the pipeline degrades gracefully when `nltk` punkt models are unavailable.
"""

import re

PER_FILE_CHAR_LIMIT = 3000
TOTAL_CHAR_LIMIT = 10000
COMPRESSION_TIMEOUT = 3  # seconds

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…।।।])\s+|\s*-\s+")
_WORD_RE = re.compile(r"\w+", flags=re.UNICODE)


class _SimpleTokenizer:
    """Stand-in for sumy's NLTK-based `Tokenizer`.

    Splits paragraphs into sentences on terminal punctuation and words on
    alphanumeric runs. Works for Vietnamese without any external data files.
    """

    def to_sentences(self, paragraph: str):
        parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(paragraph)]
        return tuple(p for p in parts if p)

    def to_words(self, sentence: str):
        return tuple(w.lower() for w in _WORD_RE.findall(sentence))


def compress_text(text: str, char_limit: int = TOTAL_CHAR_LIMIT) -> str:
    """Reduce `text` to at most `char_limit` characters.

    Returns the text unchanged when it is already within the budget. When it
    is too long, sumy's TextRank picks the most representative sentences.
    """
    text = (text or "").strip()
    if len(text) <= char_limit or len(_meaningful_chars(text)) <= char_limit:
        return text

    return _compress_with_timeout(text, char_limit)


def _compress_with_timeout(text: str, char_limit: int) -> str:
    return run_with_timeout(_summary_text, COMPRESSION_TIMEOUT, text, char_limit)


def _summary_text(text: str, char_limit: int) -> str:
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.summarizers.text_rank import TextRankSummarizer

    try:
        parser = PlaintextParser.from_string(text, _SimpleTokenizer())
        summarizer = TextRankSummarizer()
        sentences = list(parser.document.sentences)
        wanted = _target_sentences(text, char_limit)
        if not sentences or wanted <= 0:
            return _truncate_by_sentences(text, char_limit)
        # A single sentence holds nothing to rank — ranking it would build a
        # huge word graph (O(n^2)) for boring punctuation-less blobs. Truncate.
        if len(sentences) <= 1:
            return _truncate_at_char(text, char_limit)

        ranked = summarizer(parser.document, min(wanted, len(sentences) or 1))
        out = _join_until_budget((str(s) for s in ranked), text, char_limit)
        if out:
            return out
    except Exception:
        # sumy/nltk failure must never derail the call — fall back verbatim.
        pass

    return _truncate_by_sentences(text, char_limit)


def _target_sentences(text: str, char_limit: int) -> int:
    """Rough estimate of how many sentences fit inside `char_limit`."""
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        return 1
    avg = len(text) / len(sentences)
    return max(1, int(char_limit / max(avg, 1)))


def _join_until_budget(sentences, original: str, char_limit: int) -> str:
    out = ""
    for sentence in sentences:
        candidate = (out + " " + sentence).strip()
        if len(candidate) > char_limit:
            break
        out = candidate
    if not out and sentences:
        first = next(iter(sentences))
        if len(first) <= char_limit:
            out = first
    return out or _truncate_by_sentences(original, char_limit)


def _truncate_by_sentences(text: str, char_limit: int) -> str:
    current = ""
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = (current + " " + sentence).strip()
        if len(candidate) > char_limit:
            break
        current = candidate
    # A single sentence larger than the budget is sliced at a word boundary.
    if len(current) > char_limit:
        return _truncate_at_char(text, char_limit)
    return current or _truncate_at_char(text, char_limit)


def _truncate_at_char(text: str, char_limit: int) -> str:
    if len(text) <= char_limit:
        return text
    return text[: char_limit].rsplit(" ", 1)[0]


def _meaningful_chars(text: str) -> str:
    return re.sub(r"[^\w]", "", text, flags=re.UNICODE)


def run_with_timeout(func, timeout, *args, **kwargs):
    import threading

    result = {}

    def _target():
        try:
            result["value"] = func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            result["error"] = e

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError(f"Compression timed out after {timeout}s")
    if "error" in result:
        raise result["error"]
    return result["value"]
