"""Text cleanup shared by the extractors."""

import re
import unicodedata

# openFDA text has "¿" wherever a non-ASCII character was lost upstream ("Jalapen¿o", "30¿").
_LOST_CHAR = re.compile(r"(?<=[\w\d])¿|¿(?=[\w\d])")
_SPACES = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")


def clean(text: str | None) -> str:
    """NFKC-normalise, drop lost-character markers, and collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _LOST_CHAR.sub("", text)
    return _SPACES.sub(" ", text).strip()


def sentences(text: str) -> list[str]:
    """Split prose into sentences (good enough for recall notices; not a general tokenizer)."""
    return [part.strip() for part in _SENTENCE_END.split(clean(text)) if part.strip()]


def truncate(text: str, limit: int) -> str:
    """Cut at a word boundary and mark the cut."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + " …"


def code_key(value: str) -> str:
    """Normalised form of an identifier for exact matching: "WD-123.a" -> "WD123A"."""
    return re.sub(r"[^0-9A-Z]", "", value.upper())
