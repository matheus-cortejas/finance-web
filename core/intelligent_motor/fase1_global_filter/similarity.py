from typing import Sequence
import math


def calcular_similaridade(emb1: Sequence[float], emb2: Sequence[float]) -> float:
    if emb1 is None or emb2 is None:
        raise ValueError("Embeddings não podem ser None")

    if len(emb1) != len(emb2):
        raise ValueError("Dimensões dos embeddings não coincidem")

    if len(emb1) == 0:
        raise ValueError("Embeddings vazios fornecidos")

    total = math.fsum((float(a) * float(b) for a, b in zip(emb1, emb2)))

    return float(total)


__all__ = ["calcular_similaridade"]
