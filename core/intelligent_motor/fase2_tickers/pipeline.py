from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .asset_embedding_store import get_asset_embedding_store
from .gating import (
    ESTRATEGIA_SETOR_LEXICAL,
    ESTRATEGIA_SIMILARIDADE,
    aplicar_estrategia,
    setores_por_ticker,
    texto_noticia,
    tickers_lexicais,
)
from .llm_picker import LLMPicker
from .rerank import DEFAULT_MODELO as RERANK_MODELO_PADRAO
from .rerank import rerankar
from .similarity import cosine_similarity
from ..fase1_global_filter.logging import log_event


def relacionar_tickers(
    noticia: Dict[str, Any],
    carteira_usuario: List[str],
    config: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
    device: Optional[str] = None,
    setores_ativos: Optional[Dict[str, str]] = None,
    detalhes: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Relaciona tickers por similaridade de embedding, com defesas opcionais.

    Usa multiplicação matricial (numpy) quando possível; para 586 ativos e
    16k notícias isso é ordens de magnitude mais rápido que o loop Python.

    ``config['fase2']`` controla as estratégias (ver ``gating.py``):

    * ``estrategia`` (padrão ``similaridade``): ``similaridade`` (A0),
      ``similaridade_setor`` (A1) ou ``similaridade_setor_lexical`` (A2).
    * ``top_k`` (padrão ``None``): limita o número de tickers retornados.
    * ``peso_lexical`` (padrão ``0``): bônus de ordenação para tickers citados
      explicitamente no texto (usado em A2).
    * ``rerank`` (A3): reordenar/filtrar os ``top_n`` candidatos com um
      cross-encoder. Se ``enabled`` e o modelo falhar, mantém a similaridade.
    * ``llm`` (A4): pedir ao LLM (local → escalonamento) os tickers afetados.

    ``detalhes`` (opcional) é preenchido com o que foi aplicado, para métricas.
    """
    if not isinstance(carteira_usuario, (list, tuple)):
        raise ValueError("carteira_usuario deve ser uma lista de tickers")

    emb_noticia = noticia.get("embedding_noticia")
    noticia_id = noticia.get("id")
    if emb_noticia is None:
        raise ValueError(
            "noticia deve conter 'embedding_noticia' gerado pela Fase 1"
        )

    fase_cfg = {} if config is None else (config.get("fase2", {}) or {})

    threshold = float(fase_cfg.get("threshold_similaridade", 0.70))
    estrategia = str(fase_cfg.get("estrategia", ESTRATEGIA_SIMILARIDADE))
    top_k = fase_cfg.get("top_k")
    peso_lexical = float(fase_cfg.get("peso_lexical", 0.0) or 0.0)

    # --- Pré-filtragem de candidatos (A1/A2); A0 devolve a carteira inteira.
    if estrategia and estrategia != ESTRATEGIA_SIMILARIDADE:
        if setores_ativos is None:
            setores_ativos = setores_por_ticker()
    else:
        setores_ativos = setores_ativos or {}

    candidatos = aplicar_estrategia(
        estrategia, list(carteira_usuario), noticia, setores_ativos
    )
    lexicais: set[str] = set()
    if estrategia == ESTRATEGIA_SETOR_LEXICAL:
        universo = set(carteira_usuario)
        lexicais = {t for t in tickers_lexicais(noticia) if t in universo}

    store = get_asset_embedding_store(model_name=model_name, device=device)

    related: list[tuple[str, float]] = []
    start = time.time()

    present, matrix = store.get_matrix(candidatos)
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
        embeddings = store.get_embeddings(candidatos)
        if not embeddings:
            log_event(
                "ERROR",
                noticia_id,
                "fase2",
                "assets",
                None,
                "TICKER_WITHOUT_EMBEDDING",
                None,
                {"n_tickers": len(candidatos)},
            )
        for ticker in candidatos:
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

    # --- Guarda lexical (A2): tickers citados são mantidos e priorizados.
    if lexicais:
        presentes = {ticker for ticker, _ in related}
        for ticker in lexicais:
            if ticker not in presentes and ticker in candidatos:
                related.append((ticker, 0.0))

    related.sort(
        key=lambda item: item[1]
        + (peso_lexical if item[0] in lexicais else 0.0),
        reverse=True,
    )

    # --- A3: reranking com cross-encoder no top-N do bi-encoder.
    rerank_cfg = fase_cfg.get("rerank") or {}
    if isinstance(rerank_cfg, dict) and rerank_cfg.get("enabled") and related:
        top_n = int(rerank_cfg.get("top_n", 20))
        entrada = [ticker for ticker, _ in related[:top_n]]
        descricoes = store.get_descriptions(entrada)
        aprovados = rerankar(
            texto_noticia(noticia),
            entrada,
            descricoes,
            model_name=str(rerank_cfg.get("modelo") or RERANK_MODELO_PADRAO),
            threshold=float(rerank_cfg.get("threshold", 0.5)),
            manter_minimo=int(rerank_cfg.get("manter_minimo", 1)),
            device=device,
        )
        if detalhes is not None:
            detalhes.setdefault("rerank", {})
            detalhes["rerank"].update(
                {
                    "enabled": True,
                    "aplicado": aprovados is not None,
                    "modelo": str(rerank_cfg.get("modelo") or RERANK_MODELO_PADRAO),
                    "n_entrada": len(entrada),
                }
            )
        if aprovados is not None:
            ordem = {ticker: i for i, ticker in enumerate(aprovados)}
            related = [(t, s) for t, s in related if t in ordem]
            related.sort(key=lambda item: ordem[item[0]])
            if detalhes is not None:
                detalhes["rerank"]["n_saida"] = len(related)

    # --- A4: LLM (local → escalonamento) escolhe os tickers afetados.
    llm_cfg = fase_cfg.get("llm") or {}
    if isinstance(llm_cfg, dict) and llm_cfg.get("enabled") and related:
        top_n = int(llm_cfg.get("top_n", 20))
        entrada = [ticker for ticker, _ in related[:top_n]]
        descricoes = store.get_descriptions(entrada)
        picker = LLMPicker(llm_cfg)
        escolhidos, provider = picker.escolher(
            texto_noticia(noticia),
            [(ticker, descricoes.get(ticker, ticker)) for ticker in entrada],
        )
        if detalhes is not None:
            detalhes["llm"] = {
                "enabled": True,
                "aplicado": escolhidos is not None,
                "provider": provider,
                "model": picker.model,
                "n_entrada": len(entrada),
            }
        if escolhidos is not None:
            conjunto = set(escolhidos)
            related = [(t, s) for t, s in related if t in conjunto]
            if detalhes is not None:
                detalhes["llm"]["n_saida"] = len(related)

    tickers = [ticker for ticker, _ in related]

    if top_k:
        try:
            tickers = tickers[: int(top_k)]
        except (TypeError, ValueError):
            pass

    if detalhes is not None:
        detalhes["estrategia"] = estrategia
        detalhes["n_candidatos"] = len(candidatos)
        detalhes["n_tickers_final"] = len(tickers)

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
