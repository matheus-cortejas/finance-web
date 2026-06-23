from typing import Sequence
import math


def cosine_similarity(emb1: Sequence[float], emb2: Sequence[float]) -> float:
    if emb1 is None or emb2 is None:
        raise ValueError("Embeddings cannot be None")
    if len(emb1) != len(emb2):
        raise ValueError("Embedding dimensions must match")
    if len(emb1) == 0:
        raise ValueError("Embeddings must be non-empty")

    return float(math.fsum((float(a) * float(b) for a, b in zip(emb1, emb2))))


__all__ = ["cosine_similarity"]
