"""Sentence embeddings for semantic retrieval: BAAI/bge-small-en-v1.5 (384-d) on CPU via ONNX.

fastembed runs the same model as sentence-transformers without PyTorch, which keeps the API
image small and its cold start fast on Hugging Face's free CPU (see DECISIONS.md).
"""

from collections.abc import Iterable, Sequence
from functools import cached_property
from pathlib import Path

from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384
_MAX_CHARS = 600  # well inside the model's 512-token window


def product_text(product_name: str, brand: str | None = None, category: str | None = None) -> str:
    """What we embed for a recalled product: name first, then who makes it and what it is.

    Hazard wording is left out on purpose: queries describe products, not hazards.
    """
    parts = [product_name.strip()]
    if brand and brand.lower() not in product_name.lower():
        parts.append(brand.strip())
    if category:
        parts.append(category.replace("_", " "))
    return " | ".join(parts)[:_MAX_CHARS]


class Embedder:
    def __init__(self, cache_dir: Path | None = None, threads: int | None = None) -> None:
        self._cache_dir = cache_dir
        self._threads = threads

    @cached_property
    def _model(self) -> TextEmbedding:
        return TextEmbedding(
            MODEL_NAME,
            cache_dir=str(self._cache_dir) if self._cache_dir else None,
            threads=self._threads,
        )

    def warm_up(self) -> None:
        """Load the model now (downloads it on first use) instead of on the first request."""
        _ = self._model

    def passages(self, texts: Sequence[str], batch_size: int = 64) -> list[list[float]]:
        return [
            vector.tolist()
            for vector in self._model.passage_embed(list(texts), batch_size=batch_size)
        ]

    def query(self, text: str) -> list[float]:
        # bge applies its retrieval instruction to queries; passages are embedded as-is.
        (vector,) = self._model.query_embed([text[:_MAX_CHARS]])
        return list(vector.tolist())

    def queries(self, texts: Iterable[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.query_embed([t[:_MAX_CHARS] for t in texts])]
