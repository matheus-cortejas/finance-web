# pipeline_orchestrator.py
import threading
import time
from typing import Dict, Any

from .config_loader import load_global_config
from .fase1_global_filter.pipeline import avaliar_relevancia_global
from .fase1_global_filter.embedding_generator import EmbeddingGenerator
from .fase1_global_filter.cache_manager import get_cache_manager
from .fase2_tickers.pipeline import relacionar_tickers
from .fase3_heuristica.pipeline import avaliar_heuristica
from .fase4_llm_gate.pipeline import classificar_noticia
from .fase5_rich_classification.pipeline import classificar_noticia_rica
from .pipeline_metrics import registrar_metrica, classificar_tickers_por_origem


_initialized = False
_init_lock = threading.Lock()


def _ensure_initialized(config: Dict[str, Any]) -> None:
    """Inicializa os singletons (cache, embedding) uma única vez."""
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        get_cache_manager(config=config)
        modelo = config.get("fase1", {}).get("modelo")
        if modelo:
            EmbeddingGenerator.instance(model_name=modelo, config=config)
        _initialized = True


def processar_noticia_completa(
    noticia: dict,
    carteira_usuario: list,          # obrigatório agora
) -> dict:
    """
    Executa o pipeline completo (fases 1 a 6).

    Parâmetros:
        noticia: dict com 'id', 'titulo', 'descricao', 'conteudo', 'link'
        carteira_usuario: lista de tickers para comparar na fase 2

    Instrumentação:
        Cada execução gera um registro de métricas (tempo por fase,
        scores, decisões de cada fase) via `registrar_metrica`, usado
        posteriormente para análise/avaliação do Motor Inteligente
        (ver pipeline_metrics.py e export_metrics.py). A instrumentação
        é "best effort": eventuais falhas no registro de métricas não
        interrompem o processamento da notícia.
    """
    config = load_global_config()
    _ensure_initialized(config)

    t_inicio = time.perf_counter()
    metrica: Dict[str, Any] = {
        "noticia_id": noticia.get("id"),
        "link": noticia.get("link"),
        "feed_url": noticia.get("feed_url"),
        "publicado_em": noticia.get("publicado_em"),
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
        metrica["t_total_s"] = round(time.perf_counter() - t_inicio, 4)
        registrar_metrica(metrica, config=config)
        return {"relevancia_binaria": 0}

    metrica["fase1_aprovada"] = True
    metrica["relevancia_global"] = res1["relevancia_global"]
    noticia["relevancia_global"] = res1["relevancia_global"]
    noticia["embedding_noticia"] = res1["embedding"]

    # ------------------------------------------------------------ Fase 2
    t0 = time.perf_counter()
    tickers = relacionar_tickers(noticia, carteira_usuario, config=config)
    metrica["fase2_tempo_s"] = round(time.perf_counter() - t0, 4)

    noticia["tickers_relacionados"] = tickers
    metrica["n_tickers_relacionados"] = len(tickers)

    n_b3, n_sp500, n_outros = classificar_tickers_por_origem(tickers)
    metrica["n_tickers_b3"] = n_b3
    metrica["n_tickers_sp500"] = n_sp500
    metrica["n_tickers_outros"] = n_outros

    # ------------------------------------------------------------ Fase 3
    t0 = time.perf_counter()
    noticia = avaliar_heuristica(noticia, config=config)
    metrica["fase3_tempo_s"] = round(time.perf_counter() - t0, 4)

    metrica["score_heuristico"] = noticia.get("score_heuristico")
    metrica["criterios_ativados"] = noticia.get("criterios_ativados")

    # ------------------------------------------------------------ Fase 4
    t0 = time.perf_counter()
    noticia = classificar_noticia(noticia, config=config)
    metrica["fase4_tempo_s"] = round(time.perf_counter() - t0, 4)

    metrica["relevancia_binaria"] = noticia.get("relevancia_binaria")
    metrica["provider_fase4"] = noticia.get("provider_fase4")
    metrica["confianca_fase4"] = noticia.get("confianca_fase4")
    # Campo opcional: só será preenchido se fase4_llm_gate.pipeline expuser
    # explicitamente se a resposta veio do cache (recomendado para o
    # artigo, pois permite medir economia de chamadas à LLM).
    metrica["fase4_cache_hit"] = noticia.get("cache_hit_fase4")

    if noticia.get("relevancia_binaria") != 1:
        metrica["motivo_descarte"] = "fase4_relevancia_binaria"
        metrica["t_total_s"] = round(time.perf_counter() - t_inicio, 4)
        registrar_metrica(metrica, config=config)
        return noticia   # notícia irrelevante

    # ------------------------------------------------------------ Fase 5
    t0 = time.perf_counter()
    noticia = classificar_noticia_rica(noticia, config=config)
    metrica["fase5_tempo_s"] = round(time.perf_counter() - t0, 4)

    metrica["sentimento"] = noticia.get("sentimento")
    metrica["impacto"] = noticia.get("impacto")
    metrica["urgencia"] = noticia.get("urgencia")
    metrica["categoria"] = noticia.get("categoria")
    # Campos opcionais (idem comentário da Fase 4): indicam se a Fase 5
    # usou a LLM, o cache, ou o fallback heurístico. Se essas chaves não
    # existirem no dicionário retornado por classificar_noticia_rica,
    # ficam como None e podem ser preenchidas posteriormente.
    metrica["fase5_provider"] = noticia.get("provider_fase5")
    metrica["fase5_cache_hit"] = noticia.get("cache_hit_fase5")
    metrica["fase5_fallback_heuristico"] = noticia.get("fallback_fase5")

    metrica["motivo_descarte"] = None
    metrica["t_total_s"] = round(time.perf_counter() - t_inicio, 4)
    registrar_metrica(metrica, config=config)

    return noticia
