"""A3 — reranking dos candidatos da Fase 2 com um cross-encoder.

O bi-encoder (Fase 1/2) compara notícia e ativo em *embeddings* separados, o
que é rápido, mas gera associações espúrias. Um **cross-encoder** lê o par
(notícia, ativo) *junto* e produz um score de relevância muito mais preciso —
porém caro. A estratégia A3 usa o bi-encoder para reduzir para os ``top_n``
candidatos e só então aplica o cross-encoder, reordenando e filtrando.

O modelo é carregado de forma preguiçosa e fica em cache por processo. Toda
falha (pacote ausente, modelo indisponível, sem GPU) é tratada como "não
aplicar": o chamador mantém o resultado da similaridade.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Sequence, Tuple

DEFAULT_MODELO = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
DEFAULT_THRESHOLD = 0.5
DEFAULT_TOP_N = 20


class CrossEncoderReranker:
    """Wrapper com cache de instâncias do ``sentence_transformers.CrossEncoder``."""

    _instances: Dict[str, "CrossEncoderReranker"] = {}
    _lock = threading.Lock()

    def __init__(
        self,
        model_name: str,
        device: Optional[str] = None,
        max_length: int = 512,
    ):
        from sentence_transformers import CrossEncoder

        kwargs = {"max_length": max_length}
        if device:
            kwargs["device"] = device
        self._model = CrossEncoder(model_name, **kwargs)
        self.model_name = model_name

    @classmethod
    def instance(
        cls,
        model_name: str,
        device: Optional[str] = None,
        max_length: int = 512,
    ) -> "CrossEncoderReranker":
        key = f"{model_name}::{device or ''}::{max_length}"
        with cls._lock:
            existing = cls._instances.get(key)
            if existing is None:
                existing = cls(model_name, device=device, max_length=max_length)
                cls._instances[key] = existing
            return existing

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instances.clear()

    def score(self, pares: Sequence[Tuple[str, str]]) -> List[float]:
        """Score de relevância para cada par (notícia, ativo)."""
        if not pares:
            return []
        scores = self._model.predict(list(pares))
        return [float(x) for x in scores]


def selecionar_por_score(
    tickers: Sequence[str],
    scores: Sequence[float],
    threshold: float,
    manter_minimo: int = 1,
) -> List[str]:
    """Ordena por score desc e mantém os que passam do ``threshold``.

    Se nenhum passar, mantém os ``manter_minimo`` melhores (0 = nenhum), para
    não perder o melhor candidato do bi-encoder.
    """
    if len(tickers) != len(scores):
        raise ValueError("tickers e scores devem ter o mesmo tamanho")
    ranked = sorted(
        zip(tickers, scores), key=lambda item: item[1], reverse=True
    )
    aprovados = [ticker for ticker, score in ranked if score >= threshold]
    if not aprovados and manter_minimo > 0:
        aprovados = [ticker for ticker, _ in ranked[:manter_minimo]]
    return aprovados


def rerankar(
    texto_noticia: str,
    candidatos: Sequence[str],
    descricoes: Dict[str, str],
    *,
    model_name: str = DEFAULT_MODELO,
    threshold: float = DEFAULT_THRESHOLD,
    manter_minimo: int = 1,
    device: Optional[str] = None,
) -> Optional[List[str]]:
    """Reordena/filtra ``candidatos`` com o cross-encoder.

    Retorna a lista de tickers aprovados, ou ``None`` se o reranking não pôde
    ser aplicado (o chamador deve manter a ordem de similaridade).
    """
    if not candidatos:
        return []
    try:
        reranker = CrossEncoderReranker.instance(model_name, device=device)
        pares = [
            (texto_noticia, descricoes.get(ticker) or ticker)
            for ticker in candidatos
        ]
        scores = reranker.score(pares)
    except Exception:
        return None
    return selecionar_por_score(
        candidatos, scores, threshold, manter_minimo=manter_minimo
    )


__all__ = [
    "DEFAULT_MODELO",
    "DEFAULT_THRESHOLD",
    "DEFAULT_TOP_N",
    "CrossEncoderReranker",
    "selecionar_por_score",
    "rerankar",
]
