from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from .prompt_builder import build_prompt
from .llm_classifier import LLMClassifier

logger = logging.getLogger("fase4.pipeline")


def classificar_noticia(
    noticia: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(noticia, dict):
        return None

    # Extrai configuração da fase4 (se não fornecida, usa valores padrão)
    if config is None:
        fase_cfg = {}
    else:
        fase_cfg = config.get("fase4", {})

    aprovacao = int(fase_cfg.get("score_aprovacao_direta", 7))
    rejeicao = int(fase_cfg.get("score_rejeicao_direta", 2))
    faixa = fase_cfg.get("faixa_llm", {}) or {}
    minimo = int(faixa.get("minimo", 3))
    maximo = int(faixa.get("maximo", 6))

    score_raw = noticia.get("score_heuristico")
    try:
        score = int(score_raw) if score_raw is not None else None
    except Exception:
        score = None

    # Bypass aprovação direta
    if score is not None and score >= aprovacao:
        noticia["relevancia_binaria"] = 1
        noticia["provider_fase4"] = "bypass"
        noticia["status_fase4"] = "aprovacao_direta"
        noticia["confianca_fase4"] = 1.0
        return noticia

    # Bypass rejeição direta
    if score is not None and score <= rejeicao:
        noticia["relevancia_binaria"] = 0
        noticia["provider_fase4"] = "bypass"
        noticia["status_fase4"] = "rejeicao_direta"
        noticia["confianca_fase4"] = 1.0
        return noticia

    # Faixa intermediária: aciona LLM
    title = noticia.get("titulo") or noticia.get("title") or ""
    description = noticia.get("descricao") or noticia.get("description") or ""
    content = noticia.get("conteudo") or noticia.get("content") or None
    criterios = noticia.get("criterios_ativados") or noticia.get("criterios") or []

    prompt = build_prompt(title, description, content, criterios)
    # Passa a configuração para o LLMClassifier
    classifier = LLMClassifier(config=config, model=fase_cfg.get("llm", {}).get("model"))

    decision = classifier.classificar(prompt)
    try:
        decision = int(decision)
    except Exception:
        decision = int(getattr(classifier, "fallback_result", 1))

    confidence = getattr(classifier, "last_confidence", None)
    if confidence is None:
        confidence = 1.0

    noticia["relevancia_binaria"] = decision
    noticia["confianca_fase4"] = float(confidence)
    noticia["provider_fase4"] = "openai" if getattr(classifier, "client", None) else "fallback"
    noticia["status_fase4"] = "ok" if noticia["provider_fase4"] == "openai" else "fallback"
    return noticia


__all__ = ["classificar_noticia"]