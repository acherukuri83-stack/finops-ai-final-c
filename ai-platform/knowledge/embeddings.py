"""Local embeddings. fastembed = ONNX runtime, no torch. Model is pulled once and cached
under the fastembed cache dir (HF hub). 384-dim, cosine.
"""

from __future__ import annotations

from functools import cache

from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIM = 384


@cache
def _model() -> TextEmbedding:
    return TextEmbedding(model_name=MODEL_NAME)


def embed(texts: list[str]) -> list[list[float]]:
    return [[float(x) for x in vec] for vec in _model().embed(list(texts))]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
