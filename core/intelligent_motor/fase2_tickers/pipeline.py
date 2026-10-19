from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .asset_embedding_store import get_asset_embedding_store
from .similarity import cosine_similarity
from ..fase1_global_filter.logging import log_event


def relacionar_tickers(
    noticia: Dict[str, Any],
    carteira_usuario: List[str],
    config: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
    device: Optional[str] = None,
) -> List[str]:
    """Relaciona tickers por similaridade de embedding.

    Usa multiplicação matricial (numpy) quando possível; para 586 ativos e
    16k notícias isso é ordens de magnitude mais rápido que o loop Python.
    """
    if not isinstance(carteira_usuario, (list, tuple)):
        raise ValueError("carteira_usuario deve ser uma lista de tickers")

    emb_noticia = noticia.get("embedding_noticia")
    noticia_id = noticia.get("id")
    if emb_noticia is None:
        raise ValueError(
            "noticia deve conter 'embedding_noticia' gerado pela Fase 1"
        )

    if config is None:
        fase_cfg = {}
    else:
        fase_cfg = config.get("fase2", {})

    threshold = float(fase_cfg.get("threshold_similaridade", 0.70))
    store = get_asset_embedding_store(model_name=model_name, device=device)

    related: list[tuple[str, float]] = []
    start = time.time()

    present, matrix = store.get_matrix(carteira_usuario)
    used_matrix = False
    if matrix is not None:
        try:
            import numpy as np

            vector = np.asarray(emb_noticia, dtype=np.float32)
            if vector.shape[0] == matrix.shape[1]:
                norm = float(np.linalg.norm(vector))
                if norm > 0:
                    vector = vector / norm
                scores = matrix @ vector
                related = [
                    (ticker, float(score))
                    for ticker, score in zip(present, scores)
                    if float(score) > threshold
                ]
                used_matrix = True
            else:
                log_event(
                    "ERROR",
                    noticia_id,
                    "fase2",
                    "assets",
                    None,
                    "EMBEDDING_DIM_MISMATCH",
                    None,
                    {
                        "noticia": len(emb_noticia),
                        "ativos": int(matrix.shape[1]),
                    },
                )
        except Exception as exc:
            log_event(
                "ERROR",
                noticia_id,
                "fase2",
                "assets",
                None,
                "ASSET_STORE_ERROR",
                None,
                {"error": str(exc)},
            )

    if not used_matrix:
        embeddings = store.get_embeddings(carteira_usuario)
        if not embeddings:
            log_event(
                "ERROR",
                noticia_id,
                "fase2",
                "assets",
                None,
                "TICKER_WITHOUT_EMBEDDING",
                None,
                {"n_tickers": len(carteira_usuario)},
            )
        for ticker in carteira_usuario:
            emb_asset = embeddings.get(ticker)
            if emb_asset is None:
                continue
            try:
                score = cosine_similarity(emb_noticia, emb_asset)
            except Exception as exc:
                log_event(
                    "ERROR",
                    noticia_id,
                    "fase2",
                    f"asset:{ticker}",
                    None,
                    "ASSET_STORE_ERROR",
                    None,
                    {"ticker": ticker, "error": str(exc)},
                )
                continue
            if score > threshold:
                related.append((ticker, float(score)))

    related.sort(key=lambda item: item[1], reverse=True)
    tickers = [ticker for ticker, _ in related]

    elapsed_ms = (time.time() - start) * 1000.0
    if not tickers:
        log_event(
            "INFO",
            noticia_id,
            "fase2",
            "none",
            None,
            "NO_TICKER_RELATED",
            elapsed_ms,
            {},
        )

    return tickers


__all__ = ["relacionar_tickers"]
