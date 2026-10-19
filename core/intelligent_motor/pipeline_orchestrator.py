from __future__ import annotations

import copy
import threading
import time
from typing import Dict, Any, Optional

from .config_loader import load_global_config
from .fase1_global_filter.pipeline import avaliar_relevancia_global
from .fase1_global_filter.embedding_generator import EmbeddingGenerator
from .fase1_global_filter.cache_manager import get_cache_manager
from .fase2_tickers.pipeline import relacionar_tickers
from .fase3_heuristica.pipeline import avaliar_heuristica
from .fase4_llm_gate.pipeline import classificar_noticia
from .fase5_rich_classification.pipeline import classificar_noticia_rica
from .pipeline_metrics import registrar_metrica, classificar_tickers_por_origem


_init_lock = threading.Lock()


def _ensure_initialized(
    config: Dict[str, Any],
    model_name: Optional[str],
    cache_enabled: bool,
    device: Optional[str] = None,
) -> None:
    """Inicializa o cache (se habilitado) e o modelo de embeddings solicitado."""
    with _init_lock:
        if cache_enabled:
            get_cache_manager(config=config)
        EmbeddingGenerator.instance(model_name=model_name, config=config, device=device)


def _registrar_fim(
    metrica: Dict[str, Any],
    noticia: Dict[str, Any],
    t_inicio: float,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    metrica["t_total_s"] = round(time.perf_counter() - t_inicio, 4)
    registrar_metrica(metrica, config=config)
    return noticia


def processar_noticia_completa(
    noticia: dict,
    carteira_usuario: list,
    model_name: Optional[str] = None,
    run_id: Optional[int] = None,
    stop_after: int = 5,
    usar_llm: bool = True,
    cache_enabled: Optional[bool] = None,
    device: Optional[str] = None,
) -> dict:
    """Executa o pipeline com modelo e ponto de parada configuráveis.

    Parâmetros:
        noticia: dict com 'id', 'titulo', 'descricao', 'conteudo', 'link'
        carteira_usuario: lista de tickers para a Fase 2
        model_name: modelo de embeddings (path local ou ID do Hugging Face)
        run_id: ID do ExperimentRun, apenas para instrumentação
        stop_after: 1..5; para após a fase indicada
        usar_llm: se False, Fases 4/5 usam apenas regras/fallback
        cache_enabled: sobrescreve a configuração de cache (experimentos)
        device: 'cpu', 'cuda', 'auto' ou None (usa o default das settings)
    """
    stop_after = max(1, min(int(stop_after), 5))
    config = copy.deepcopy(load_global_config())

    if model_name:
        config.setdefault("fase1", {})["modelo"] = model_name
    effective_model = model_name or config.get("fase1", {}).get("modelo")

    if cache_enabled is not None:
        config.setdefault("fase1", {}).setdefault("cache", {})["enabled"] = bool(
            cache_enabled
        )
        config.setdefault("fase5", {}).setdefault("cache", {})["enabled"] = bool(
            cache_enabled
        )

    effective_cache = bool(
        config.get("fase1", {}).get("cache", {}).get("enabled", True)
    )
    _ensure_initialized(config, effective_model, effective_cache, device=device)

    t_inicio = time.perf_counter()
    metrica: Dict[str, Any] = {
        "noticia_id": noticia.get("id"),
        "link": noticia.get("link"),
        "feed_url": noticia.get("feed_url"),
        "publicado_em": noticia.get("publicado_em"),
        "run_id": run_id,
        "modelo": effective_model,
        "device": EmbeddingGenerator.resolve_device(device),
        "stop_after": stop_after,
        "usar_llm": bool(usar_llm),
        "n_tickers_carteira": len(carteira_usuario or []),
    }

    # ------------------------------------------------------------ Fase 1
    t0 = time.perf_counter()
    res1 = avaliar_relevancia_global(noticia, config=config)
    metrica["fase1_tempo_s"] = round(time.perf_counter() - t0, 4)

    if res1 is None:
        metrica["fase1_aprovada"] = False
        metrica["relevancia_binaria"] = 0
        metrica["motivo_descarte"] = "fase1_relevancia_global"
        noticia["fase1_aprovada"] = False
        noticia["relevancia_binaria"] = 0
        return _registrar_fim(metrica, noticia, t_inicio, config)

    metrica["fase1_aprovada"] = True
    metrica["relevancia_global"] = res1["relevancia_global"]
    noticia["fase1_aprovada"] = True
    noticia["relevancia_global"] = res1["relevancia_global"]
    noticia["embedding_noticia"] = res1["embedding"]

    if stop_after == 1:
        metrica["motivo_descarte"] = "parada_fase_1"
        return _registrar_fim(metrica, noticia, t_inicio, config)

    # ------------------------------------------------------------ Fase 2
    t0 = time.perf_counter()
    tickers = relacionar_tickers(
        noticia,
        carteira_usuario,
        config=config,
        model_name=effective_model,
        device=device,
    )
    metrica["fase2_tempo_s"] = round(time.perf_counter() - t0, 4)

    noticia["tickers_relacionados"] = tickers
    metrica["n_tickers_relacionados"] = len(tickers)

    n_b3, n_sp500, n_outros = classificar_tickers_por_origem(tickers)
    metrica["n_tickers_b3"] = n_b3
    metrica["n_tickers_sp500"] = n_sp500
    metrica["n_tickers_outros"] = n_outros

    if stop_after == 2:
        metrica["motivo_descarte"] = "parada_fase_2"
        return _registrar_fim(metrica, noticia, t_inicio, config)

    # ------------------------------------------------------------ Fase 3
    t0 = time.perf_counter()
    noticia = avaliar_heuristica(noticia, config=config)
    metrica["fase3_tempo_s"] = round(time.perf_counter() - t0, 4)

    metrica["score_heuristico"] = noticia.get("score_heuristico")
    metrica["criterios_ativados"] = noticia.get("criterios_ativados")

    if stop_after == 3:
        metrica["motivo_descarte"] = "parada_fase_3"
        return _registrar_fim(metrica, noticia, t_inicio, config)

    # ------------------------------------------------------------ Fase 4
    t0 = time.perf_counter()
    noticia = classificar_noticia(noticia, config=config, usar_llm=usar_llm)
    metrica["fase4_tempo_s"] = round(time.perf_counter() - t0, 4)

    metrica["relevancia_binaria"] = noticia.get("relevancia_binaria")
    metrica["provider_fase4"] = noticia.get("provider_fase4")
    metrica["confianca_fase4"] = noticia.get("confianca_fase4")
    metrica["fase4_cache_hit"] = noticia.get("cache_hit_fase4")

    if stop_after == 4:
        metrica["motivo_descarte"] = (
            None
            if noticia.get("relevancia_binaria") == 1
            else "fase4_relevancia_binaria"
        )
        return _registrar_fim(metrica, noticia, t_inicio, config)

    if noticia.get("relevancia_binaria") != 1:
        metrica["motivo_descarte"] = "fase4_relevancia_binaria"
        return _registrar_fim(metrica, noticia, t_inicio, config)

    # ------------------------------------------------------------ Fase 5
    t0 = time.perf_counter()
    noticia = classificar_noticia_rica(
        noticia,
        config=config,
        usar_llm=usar_llm,
    )
    metrica["fase5_tempo_s"] = round(time.perf_counter() - t0, 4)

    metrica["sentimento"] = noticia.get("sentimento")
    metrica["impacto"] = noticia.get("impacto")
    metrica["urgencia"] = noticia.get("urgencia")
    metrica["categoria"] = noticia.get("categoria")
    metrica["fase5_provider"] = noticia.get("provider_fase5")
    metrica["fase5_cache_hit"] = noticia.get("cache_hit_fase5")
    metrica["fase5_fallback_heuristico"] = noticia.get("fallback_fase5")

    metrica["motivo_descarte"] = None
    return _registrar_fim(metrica, noticia, t_inicio, config)


__all__ = ["processar_noticia_completa"]
