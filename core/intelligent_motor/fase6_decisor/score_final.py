from __future__ import annotations

from typing import Any


def _clamp(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, valor))


def _normalizar(valor: Any, maximo: Any) -> float:
    try:
        valor_num = float(valor)
        maximo_num = float(maximo)
    except Exception:
        return 0.0

    if maximo_num <= 0:
        return 0.0

    return _clamp(valor_num / maximo_num)


def calcular_score_final(
    metadados: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> float:
    """
    Calcula o score final da notícia com base na configuração da fase 6.

    Parâmetros:
        metadados: dicionário com campos 'relevancia_global', 'score_heuristico', 'urgencia'
        config: dicionário completo de configuração (carregado pelo orquestrador)
                Deve conter a seção "fase6" com subseção "score_final".
    """
    # Valores padrão (caso não haja configuração)
    DEFAULT_CFG = {
        "pesos": {
            "relevancia_global": 0.4,
            "score_heuristico": 0.4,
            "urgencia": 0.2,
        },
        "max_score_heuristico": 20,
        "max_urgencia": 10,
    }

    if config is None:
        score_final_cfg = DEFAULT_CFG
    else:
        fase6_cfg = config.get("fase6", {})
        score_final_cfg = fase6_cfg.get("score_final", DEFAULT_CFG)

    pesos = score_final_cfg.get("pesos", {})
    peso_relevancia = float(pesos.get("relevancia_global", 0.4))
    peso_heuristico = float(pesos.get("score_heuristico", 0.4))
    peso_urgencia = float(pesos.get("urgencia", 0.2))

    max_score_heuristico = score_final_cfg.get("max_score_heuristico", 20)
    max_urgencia = score_final_cfg.get("max_urgencia", 10)

    relevancia_global = _clamp(float(metadados.get("relevancia_global", 0.0)))
    score_heuristico_norm = _normalizar(metadados.get("score_heuristico", 0.0), max_score_heuristico)
    urgencia_norm = _normalizar(metadados.get("urgencia", 0.0), max_urgencia)

    score = (
        relevancia_global * peso_relevancia
        + score_heuristico_norm * peso_heuristico
        + urgencia_norm * peso_urgencia
    )

    return round(_clamp(score), 4)


__all__ = ["calcular_score_final"]