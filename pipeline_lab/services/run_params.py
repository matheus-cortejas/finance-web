from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.core.exceptions import ValidationError

from core.intelligent_motor.config_loader import load_global_config


# Pesos da Fase 3, na ordem em que aparecem no config.yaml.
PESOS_FASE3 = [
    ("ticker_explicito", "Ticker explícito"),
    ("setor_relacionado", "Setor relacionado"),
    ("macro", "Macro"),
    ("negativo", "Negativo"),
    ("urgencia", "Urgência"),
    ("fonte_confiavel", "Fonte confiável"),
    ("impacto", "Impacto"),
    ("tendencia_positiva", "Tendência positiva"),
    ("tendencia_negativa", "Tendência negativa"),
    ("tendencia_mista", "Tendência mista"),
    ("ambiguidade", "Ambiguidade"),
]

PESO_MIN = -20
PESO_MAX = 20
THRESHOLD_MIN = 0.0
THRESHOLD_MAX = 1.0


def _deep_merge(base: dict, extra: dict | None) -> dict:
    """Faz merge recursivo de ``extra`` em ``base`` (mutando ``base``)."""
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = deepcopy(value)
    return base


def defaults() -> dict:
    """Valores padrão das Fases 1–4, lidos do config.yaml."""
    cfg = load_global_config()
    fase1 = cfg.get("fase1", {}) or {}
    fase2 = cfg.get("fase2", {}) or {}
    fase3 = cfg.get("fase3", {}) or {}
    fase4 = cfg.get("fase4", {}) or {}
    pesos = fase3.get("pesos", {}) or {}
    faixa = fase4.get("faixa_llm", {}) or {}

    return {
        "fase1": {
            "threshold_relevancia": float(
                fase1.get("threshold_relevancia", 0.55)
            ),
            "centroides_referencia": list(
                fase1.get("centroides_referencia", []) or []
            ),
        },
        "fase2": {
            "threshold_similaridade": float(
                fase2.get("threshold_similaridade", 0.70)
            ),
        },
        "fase3": {
            "pesos": {chave: int(pesos.get(chave, 0)) for chave, _ in PESOS_FASE3}
        },
        "fase4": {
            "score_aprovacao_direta": int(
                fase4.get("score_aprovacao_direta", 7)
            ),
            "score_rejeicao_direta": int(
                fase4.get("score_rejeicao_direta", 2)
            ),
            "faixa_llm": {
                "minimo": int(faixa.get("minimo", 3)),
                "maximo": int(faixa.get("maximo", 6)),
            },
            "fallback_resultado": int(fase4.get("fallback_resultado", 1)),
        },
    }


def effective(overrides: dict | None = None) -> dict:
    """Defaults + overrides, sem mutar o cache do config_loader."""
    base = deepcopy(defaults())
    return _deep_merge(base, overrides or {})


def _parse_float(
    post,
    field: str,
    default: float,
    *,
    low: float = THRESHOLD_MIN,
    high: float = THRESHOLD_MAX,
) -> float:
    raw = (post.get(field) or "").strip()
    if raw == "":
        return default
    try:
        value = float(raw.replace(",", "."))
    except ValueError as exc:
        raise ValidationError(f"{field}: valor numérico inválido.") from exc
    if not (low <= value <= high):
        raise ValidationError(
            f"{field}: deve estar entre {low:g} e {high:g}."
        )
    return value


def _parse_int(
    post,
    field: str,
    default: int,
    *,
    low: int = PESO_MIN,
    high: int = PESO_MAX,
) -> int:
    raw = (post.get(field) or "").strip()
    if raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError(f"{field}: valor inteiro inválido.") from exc
    if not (low <= value <= high):
        raise ValidationError(
            f"{field}: deve estar entre {low} e {high}."
        )
    return value


def _parse_centroides(post) -> list[str] | None:
    if "fase1_centroides" not in post:
        return None
    linhas = [
        linha.strip()
        for linha in (post.get("fase1_centroides") or "").splitlines()
        if linha.strip()
    ]
    if not linhas:
        return None
    if len(linhas) > 50:
        raise ValidationError("Centroides: use no máximo 50 linhas.")
    for linha in linhas:
        if len(linha) > 1000:
            raise ValidationError(
                "Centroides: cada linha deve ter no máximo 1000 caracteres."
            )
    return linhas


def build_overrides(post) -> dict:
    """Monta o dict de overrides a partir do POST, guardando só o que mudou."""
    base = defaults()
    overrides: dict[str, Any] = {}

    fase1: dict[str, Any] = {}
    threshold_relevancia = _parse_float(
        post,
        "fase1_threshold",
        base["fase1"]["threshold_relevancia"],
    )
    if abs(threshold_relevancia - base["fase1"]["threshold_relevancia"]) > 1e-12:
        fase1["threshold_relevancia"] = threshold_relevancia

    centroides = _parse_centroides(post)
    if centroides is not None and centroides != base["fase1"]["centroides_referencia"]:
        fase1["centroides_referencia"] = centroides
    if fase1:
        overrides["fase1"] = fase1

    threshold_similaridade = _parse_float(
        post,
        "fase2_threshold",
        base["fase2"]["threshold_similaridade"],
    )
    if abs(threshold_similaridade - base["fase2"]["threshold_similaridade"]) > 1e-12:
        overrides["fase2"] = {
            "threshold_similaridade": threshold_similaridade
        }

    pesos: dict[str, int] = {}
    for chave, _ in PESOS_FASE3:
        valor = _parse_int(
            post,
            f"fase3_{chave}",
            base["fase3"]["pesos"][chave],
        )
        if valor != base["fase3"]["pesos"][chave]:
            pesos[chave] = valor
    if pesos:
        overrides["fase3"] = {"pesos": pesos}

    fase4: dict[str, Any] = {}
    aprovacao = _parse_int(
        post,
        "fase4_aprovacao",
        base["fase4"]["score_aprovacao_direta"],
        low=0,
        high=20,
    )
    if aprovacao != base["fase4"]["score_aprovacao_direta"]:
        fase4["score_aprovacao_direta"] = aprovacao

    rejeicao = _parse_int(
        post,
        "fase4_rejeicao",
        base["fase4"]["score_rejeicao_direta"],
        low=0,
        high=20,
    )
    if rejeicao != base["fase4"]["score_rejeicao_direta"]:
        fase4["score_rejeicao_direta"] = rejeicao

    llm_min = _parse_int(
        post,
        "fase4_llm_min",
        base["fase4"]["faixa_llm"]["minimo"],
        low=0,
        high=20,
    )
    llm_max = _parse_int(
        post,
        "fase4_llm_max",
        base["fase4"]["faixa_llm"]["maximo"],
        low=0,
        high=20,
    )
    faixa: dict[str, int] = {}
    if llm_min != base["fase4"]["faixa_llm"]["minimo"]:
        faixa["minimo"] = llm_min
    if llm_max != base["fase4"]["faixa_llm"]["maximo"]:
        faixa["maximo"] = llm_max
    if faixa:
        fase4["faixa_llm"] = faixa

    fallback = _parse_int(
        post,
        "fase4_fallback",
        base["fase4"]["fallback_resultado"],
        low=0,
        high=1,
    )
    if fallback != base["fase4"]["fallback_resultado"]:
        fase4["fallback_resultado"] = fallback

    if fase4:
        overrides["fase4"] = fase4

    validate_overrides(overrides)
    return overrides


def validate_overrides(overrides: dict | None) -> None:
    """Valida os valores efetivos (defaults + overrides)."""
    eff = effective(overrides)
    fase1 = eff["fase1"]
    fase2 = eff["fase2"]
    fase4 = eff["fase4"]
    faixa = fase4["faixa_llm"]

    for nome, valor in (
        ("Fase 1 threshold_relevancia", fase1["threshold_relevancia"]),
        ("Fase 2 threshold_similaridade", fase2["threshold_similaridade"]),
    ):
        if not (THRESHOLD_MIN <= float(valor) <= THRESHOLD_MAX):
            raise ValidationError(
                f"{nome}: deve estar entre {THRESHOLD_MIN:g} e "
                f"{THRESHOLD_MAX:g}."
            )

    if not fase1["centroides_referencia"]:
        raise ValidationError("Fase 1: informe ao menos um centroide.")

    if fase4["score_rejeicao_direta"] >= faixa["minimo"]:
        raise ValidationError(
            "Fase 4: o corte de rejeição direta deve ser menor que o "
            "mínimo da faixa do LLM."
        )
    if faixa["minimo"] > faixa["maximo"]:
        raise ValidationError(
            "Fase 4: o mínimo da faixa do LLM não pode ser maior que o máximo."
        )
    if faixa["maximo"] >= fase4["score_aprovacao_direta"]:
        raise ValidationError(
            "Fase 4: o máximo da faixa do LLM deve ser menor que o corte "
            "de aprovação direta."
        )
    if fase4["fallback_resultado"] not in (0, 1):
        raise ValidationError("Fase 4: fallback_resultado deve ser 0 ou 1.")
