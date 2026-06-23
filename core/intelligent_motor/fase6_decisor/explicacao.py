from __future__ import annotations

from typing import Any


def gerar_explicacao(regra: dict[str, Any] | None) -> str:
    if not isinstance(regra, dict):
        return "Notícia registrada apenas para histórico."

    explicacao = regra.get("explicacao")
    if isinstance(explicacao, str) and explicacao.strip():
        return explicacao.strip()

    prioridade = str(regra.get("prioridade") or "baixa").strip().lower()
    if prioridade == "critica":
        return "Notícia crítica com necessidade de atenção imediata."
    if prioridade == "alta":
        return "Notícia de alta prioridade para acompanhamento rápido."
    if prioridade == "media":
        return "Notícia relevante para acompanhamento em painel."
    return "Notícia registrada apenas para histórico."


__all__ = ["gerar_explicacao"]
