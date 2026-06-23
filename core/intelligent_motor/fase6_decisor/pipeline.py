from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .exceptions import Fase6Error, PerfilInvalidoError
from .perfis import PerfilUsuario
from .motor_regras import avaliar_regras
from .score_final import calcular_score_final
from .explicacao import gerar_explicacao

logger = logging.getLogger("fase6.pipeline")

# Configuração padrão (fallback caso nenhuma config seja fornecida)
_CONFIG_PADRAO = {
    "regras": [
        {
            "nome": "impacto_negativo_alto",
            "condicoes": {"e": [{"impacto": "alto"}, {"sentimento": "negativo"}]},
            "prioridade": "critica",
            "acoes": ["email", "push", "dashboard_destacado"],
            "explicacao": "Impacto alto com sentimento negativo: requer atenção imediata.",
        },
        {
            "nome": "impacto_alto_ou_urgencia",
            "condicoes": {"ou": [{"impacto": "alto"}, {"urgencia": {"min": 8}}]},
            "prioridade": "alta",
            "acoes": ["push", "dashboard"],
            "explicacao": "Alto impacto ou urgência elevada.",
        },
        {
            "nome": "score_heuristico_ou_relevancia",
            "condicoes": {"ou": [{"score_heuristico": {"min": 10}}, {"relevancia_global": {"min": 0.85}}]},
            "prioridade": "media",
            "acoes": ["dashboard"],
            "explicacao": "Relevância significativa detectada.",
        },
        {
            "nome": "default",
            "condicoes": {},
            "prioridade": "baixa",
            "acoes": ["historico"],
            "explicacao": "Notícia registrada apenas para histórico.",
        },
    ],
    "score_final": {
        "pesos": {
            "relevancia_global": 0.4,
            "score_heuristico": 0.4,
            "urgencia": 0.2,
        },
        "max_score_heuristico": 20,
        "max_urgencia": 10,
    },
    "perfil_padrao": {
        "canais_habilitados": ["email", "push", "dashboard"],
        "notificar_apenas_categorias": [],
    },
    "acoes_canais": {
        "email": "email",
        "push": "push",
        "dashboard": "dashboard",
        "dashboard_destacado": "dashboard",
        "historico": "historico",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _emit_event(evento: str, dados: dict[str, Any]) -> None:
    payload = {"timestamp": _now_iso(), "evento": evento, "fase": "fase6"}
    payload.update(dados)
    try:
        logger.info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        logger.info("%s", payload)


def _resolver_perfil(
    perfil: PerfilUsuario | dict[str, Any] | None,
    cfg: dict[str, Any],
) -> PerfilUsuario:
    if perfil is None:
        return PerfilUsuario.padrao(cfg)

    if isinstance(perfil, PerfilUsuario):
        return perfil

    if isinstance(perfil, dict):
        return PerfilUsuario.from_dict(perfil, config=cfg)

    raise PerfilInvalidoError("Perfil inválido")


def _normalizar_prioridade(prioridade: Any) -> str:
    return str(prioridade or "baixa").strip().lower()


def _historico() -> list[str]:
    return ["historico"]


def decidir_alerta(
    noticia: dict[str, Any],
    perfil: PerfilUsuario | dict[str, Any] | None = None,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Executa a Fase 6 - Motor de regras e decisão de alertas.

    Parâmetros:
        noticia: dicionário enriquecido pelas fases 1-5.
        perfil: perfil do usuário (opcional).
        config: dicionário completo de configuração (carregado pelo orquestrador).
                Se None, usa as configurações padrão embutidas.
    """
    if not isinstance(noticia, dict):
        raise Fase6Error("noticia deve ser um dicionário")

    resultado = dict(noticia)

    # Extrai configuração da fase6 (prioriza o config recebido, senão usa padrão)
    if config is not None:
        fase6_cfg = config.get("fase6", {})
        if not fase6_cfg:
            fase6_cfg = _CONFIG_PADRAO
    else:
        fase6_cfg = _CONFIG_PADRAO

    perfil_invalido = False
    try:
        perfil_usuario = _resolver_perfil(perfil, fase6_cfg)
    except Exception as exc:
        perfil_invalido = True
        perfil_usuario = PerfilUsuario.padrao(fase6_cfg)
        _emit_event(
            "FASE6_ERROR",
            {
                "erro": str(exc),
                "regra": "perfil_invalido",
                "prioridade": "baixa",
                "acoes": _historico(),
                "score_final": None,
            },
        )

    regra = avaliar_regras(resultado, fase6_cfg.get("regras", []))
    prioridade = _normalizar_prioridade(regra.get("prioridade"))
    acoes = list(regra.get("acoes", []))
    explicacao = gerar_explicacao(regra)

    if perfil_invalido:
        prioridade = "baixa"
        acoes = _historico()
        explicacao = "Notícia registrada apenas para histórico."
    else:
        categoria = resultado.get("categoria")
        categoria_permitida = perfil_usuario.categoria_permitida(categoria)

        if not categoria_permitida:
            prioridade = "baixa"
            acoes = _historico()
            explicacao = "Notícia registrada apenas para histórico."
        else:
            acoes_filtradas = [
                acao
                for acao in acoes
                if perfil_usuario.canal_habilitado(acao)
            ]
            if acoes_filtradas:
                acoes = acoes_filtradas
            else:
                prioridade = "baixa"
                acoes = _historico()
                explicacao = "Notícia registrada apenas para histórico."

        _emit_event(
            "FASE6_PROFILE_FILTER",
            {
                "regra": regra.get("nome"),
                "prioridade": prioridade,
                "acoes": acoes,
                "categoria_permitida": categoria_permitida,
                "canais_filtrados": acoes,
                "score_final": None,
            },
        )

    score = calcular_score_final(resultado, fase6_cfg)

    if prioridade == "baixa" and acoes == _historico():
        regra_saida = "default"
    else:
        regra_saida = str(regra.get("nome") or "default")

    resultado.update(
        {
            "prioridade": prioridade,
            "acao_sugerida": acoes,
            "score_final": score,
            "regra_disparada": regra_saida,
            "explicacao_regra": explicacao,
        }
    )

    _emit_event(
        "FASE6_RULE_MATCH",
        {
            "regra": regra_saida,
            "prioridade": prioridade,
            "acoes": acoes,
            "score_final": score,
        },
    )
    _emit_event(
        "FASE6_SCORE_CALCULATED",
        {
            "regra": regra_saida,
            "prioridade": prioridade,
            "acoes": acoes,
            "score_final": score,
        },
    )
    _emit_event(
        "FASE6_DECISION",
        {
            "regra": regra_saida,
            "prioridade": prioridade,
            "acoes": acoes,
            "score_final": score,
        },
    )

    return resultado


__all__ = ["decidir_alerta"]