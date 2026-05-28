from __future__ import annotations

from typing import Any


PRIORITY_THRESHOLDS = {
    "critica": 85.0,
    "alta": 65.0,
    "media": 40.0,
    "baixa": 0.0,
}
PRIORITY_ORDER = ["baixa", "media", "alta", "critica"]


_IMPACT_POINTS = {
    "alto": 25.0,
    "medio": 12.0,
    "baixo": 4.0,
}
_URGENCIA_POINTS = {
    "alta": 15.0,
    "media": 7.0,
    "baixa": 2.0,
}


def _get_value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _normalize_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        items = [item.strip() for item in value.replace(";", ",").split(",")]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        return []
    return [item for item in items if item]


def _normalize_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def _source_multiplier(reliability: Any) -> float:
    try:
        value = float(reliability)
    except (TypeError, ValueError):
        return 1.0
    value = max(0.0, min(1.0, value))
    return 0.85 + (0.3 * value)


def score_to_priority(score: float) -> str:
    if score >= PRIORITY_THRESHOLDS["critica"]:
        return "critica"
    if score >= PRIORITY_THRESHOLDS["alta"]:
        return "alta"
    if score >= PRIORITY_THRESHOLDS["media"]:
        return "media"
    return "baixa"


def is_priority_at_least(priority: str, minimum: str) -> bool:
    try:
        return PRIORITY_ORDER.index(priority) >= PRIORITY_ORDER.index(minimum)
    except ValueError:
        return False


def calculate_relevance_score(
    classificacao: Any,
    perfil: Any | None = None,
    carteira_tickers: list[str] | None = None,
    fonte_confiabilidade: float | None = None,
) -> dict:
    sentimento = str(_get_value(classificacao, "sentimento", "neutro") or "neutro").lower()
    impacto = str(_get_value(classificacao, "impacto", "medio") or "medio").lower()
    urgencia = str(_get_value(classificacao, "urgencia", "media") or "media").lower()
    setor = str(_get_value(classificacao, "setor", "") or "").strip().lower()
    relevancia_llm = _normalize_score(_get_value(classificacao, "relevancia_llm", 0.0))

    tickers_relacionados = set(_normalize_list(_get_value(classificacao, "tickers_relacionados", [])))
    carteira_tickers = set(_normalize_list(carteira_tickers or []))

    perfil_risco = str(_get_value(perfil, "perfil_risco", "moderado") or "moderado").lower()
    sensibilidade_negativo = _normalize_score(_get_value(perfil, "sensibilidade_negativo", 0.5))
    setores_preferidos = {item.lower() for item in _normalize_list(_get_value(perfil, "setores_preferidos", []))}

    base_points = relevancia_llm * 40.0
    impacto_points = _IMPACT_POINTS.get(impacto, 10.0)
    urgencia_points = _URGENCIA_POINTS.get(urgencia, 6.0)

    if sentimento == "negativo":
        sentimento_points = 8.0 + (sensibilidade_negativo * 10.0)
    elif sentimento == "positivo":
        if perfil_risco == "agressivo":
            sentimento_points = 10.0
        elif perfil_risco == "conservador":
            sentimento_points = 4.0
        else:
            sentimento_points = 7.0
    else:
        sentimento_points = 0.0

    if tickers_relacionados:
        ticker_match = bool(tickers_relacionados & carteira_tickers)
    else:
        ticker_match = bool(carteira_tickers)
    ticker_points = 10.0 if ticker_match else 0.0

    setor_match = bool(setor and setor in setores_preferidos)
    setor_points = 6.0 if setor_match else 0.0

    raw_score = base_points + impacto_points + urgencia_points + sentimento_points + ticker_points + setor_points
    score = raw_score * _source_multiplier(fonte_confiabilidade)
    score = max(0.0, min(100.0, score))
    prioridade = score_to_priority(score)

    motivos = {
        "base": round(base_points, 2),
        "impacto": round(impacto_points, 2),
        "urgencia": round(urgencia_points, 2),
        "sentimento": round(sentimento_points, 2),
        "ticker_match": ticker_match,
        "setor_match": setor_match,
        "fonte_multiplier": round(_source_multiplier(fonte_confiabilidade), 3),
        "raw_score": round(raw_score, 2),
        "perfil_risco": perfil_risco,
        "sensibilidade_negativo": round(sensibilidade_negativo, 2),
        "setor": setor,
        "tickers_relacionados": sorted(tickers_relacionados),
        "carteira_tickers": sorted(carteira_tickers),
    }

    return {
        "score_final": round(score, 2),
        "prioridade": prioridade,
        "motivos": motivos,
    }
