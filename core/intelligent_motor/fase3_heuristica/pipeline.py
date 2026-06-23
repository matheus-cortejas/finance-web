# fase3_heuristica/pipeline.py
import time
from typing import Dict, Any, Optional

from .criterios import (
    avaliar_ticker_explicito,
    avaliar_setor_relacionado,
    avaliar_palavras_macro,
    avaliar_palavras_negativas,
    avaliar_palavras_urgencia,
    avaliar_fonte_confiavel,
    avaliar_palavras_impacto,
    avaliar_tendencia_positiva,
    avaliar_tendencia_negativa,
    avaliar_ambiguidade,
)
from ..fase1_global_filter.logging import log_event


def calcular_score_heuristico(
    noticia: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    start = time.time()
    # Extrai configuração da fase3 (se não fornecida, usa dicionário vazio)
    fase_cfg = config.get("fase3", {}) if config else {}
    pesos = fase_cfg.get("pesos", {})

    criterios_ativados = []
    score = 0

    try:
        # Ticker explícito
        ticker_ok, tickers_encontrados = avaliar_ticker_explicito(noticia)
        if ticker_ok:
            criterios_ativados.append("ticker")
            score += int(pesos.get("ticker_explicito", 0))
            noticia["tickers_encontrados"] = tickers_encontrados

        # Setor relacionado – usa o campo já preenchido pela Fase 2
        if avaliar_setor_relacionado(noticia):
            criterios_ativados.append("setor")
            score += int(pesos.get("setor_relacionado", 0))

        # Demais critérios recebem a config
        if avaliar_palavras_macro(noticia, config=config):
            criterios_ativados.append("macro")
            score += int(pesos.get("macro", 0))

        if avaliar_palavras_negativas(noticia, config=config):
            criterios_ativados.append("negativo")
            score += int(pesos.get("negativo", 0))

        if avaliar_palavras_urgencia(noticia, config=config):
            criterios_ativados.append("urgencia")
            score += int(pesos.get("urgencia", 0))

        if avaliar_fonte_confiavel(noticia, config=config):
            criterios_ativados.append("fonte_confiavel")
            score += int(pesos.get("fonte_confiavel", 0))

        if avaliar_palavras_impacto(noticia, config=config):
            criterios_ativados.append("impacto")
            score += int(pesos.get("impacto", 0))

        positivo = avaliar_tendencia_positiva(noticia, config=config)
        negativo = avaliar_tendencia_negativa(noticia, config=config)

        if positivo and not negativo:
            criterios_ativados.append("tendencia_positiva")
            score += int(pesos.get("tendencia_positiva", 0))
        elif negativo and not positivo:
            criterios_ativados.append("tendencia_negativa")
            score += int(pesos.get("tendencia_negativa", 0))
        elif negativo and positivo:
            criterios_ativados.append("tendencia_mista")
            score += int(pesos.get("tendencia_mista", 0))

        if avaliar_ambiguidade(noticia, config=config):
            criterios_ativados.append("ambiguidade")
            score += int(pesos.get("ambiguidade", 0))

    except Exception as exc:
        log_event("ERROR", noticia.get("id"), "fase3", "heuristica", None, "MODEL_ERROR", None, {"error": str(exc)})
        return {"score_heuristico": 0, "criterios_ativados": []}

    elapsed_ms = (time.time() - start) * 1000.0
    # log_event opcional
    return {"score_heuristico": int(score), "criterios_ativados": criterios_ativados}


def avaliar_heuristica(
    noticia: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Adiciona os campos 'score_heuristico' e 'criterios_ativados' à notícia.
    """
    res = calcular_score_heuristico(noticia, config=config)
    noticia["score_heuristico"] = res["score_heuristico"]
    noticia["criterios_ativados"] = res["criterios_ativados"]
    return noticia


__all__ = ["calcular_score_heuristico", "avaliar_heuristica"]