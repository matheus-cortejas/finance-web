import os
import yaml
import time
import json

from typing import Dict, Any, List, Optional

from .asset_embedding_store import AssetEmbeddingStore
from .similarity import cosine_similarity
from .exceptions import AssetStoreError
from ..fase1_global_filter.logging import log_event

def relacionar_tickers(
    noticia: Dict[str, Any],
    carteira_usuario: List[str],
    config: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Parâmetros:
        noticia: dicionário com 'embedding_noticia', 'id'
        carteira_usuario: lista de tickers para comparar
        config: dicionário completo de configuração (carregado pelo orquestrador).
                Se None, usa valores padrão (fallback).
    """
    if not isinstance(carteira_usuario, (list, tuple)):
        raise ValueError("carteira_usuario deve ser uma lista de tickers")

    emb_noticia = noticia.get("embedding_noticia")
    noticia_id = noticia.get("id")
    if emb_noticia is None:
        raise ValueError("noticia deve conter 'embedding_noticia' gerado pela Fase 1")

    # Extrai configuração da fase2 (se não fornecida, usa padrão)
    if config is None:
        fase_cfg = {}
    else:
        fase_cfg = config.get("fase2", {})

    threshold = float(fase_cfg.get("threshold_similaridade", 0.70))

    store = AssetEmbeddingStore()

    related = []
    start = time.time()

    for ticker in carteira_usuario:
        try:
            emb_asset = store.get_embedding(ticker)
        except AssetStoreError as exc:
            log_event("ERROR", noticia_id, "fase2", f"asset:{ticker}", None, "ASSET_STORE_ERROR", None, {"ticker": ticker, "error": str(exc)})
            continue

        if emb_asset is None:
            log_event("ERROR", noticia_id, "fase2", f"asset:{ticker}", None, "TICKER_WITHOUT_EMBEDDING", None, {"ticker": ticker})
            continue

        try:
            score = cosine_similarity(emb_noticia, emb_asset)
        except Exception as exc:
            log_event("ERROR", noticia_id, "fase2", f"asset:{ticker}", None, "ASSET_STORE_ERROR", None, {"ticker": ticker, "error": str(exc)})
            continue

        if score > threshold:
            related.append((ticker, float(score)))
            #log_event("INFO", noticia_id, "fase2", f"asset:{ticker}", float(score), "TICKER_RELATED", None, {"ticker": ticker, "score": float(score)})


    related.sort(key=lambda x: x[1], reverse=True)
    tickers = [t for t, s in related]

    elapsed_ms = (time.time() - start) * 1000.0

    if not tickers:
        log_event("INFO", noticia_id, "fase2", "none", None, "NO_TICKER_RELATED", elapsed_ms, {})

    return tickers


__all__ = ["relacionar_tickers"]
