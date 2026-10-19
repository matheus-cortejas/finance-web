from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.core.exceptions import ValidationError

from core.intelligent_motor.config_loader import load_global_config
from core.intelligent_motor.fase2_tickers.gating import ESTRATEGIAS as ESTRATEGIAS_FASE2


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
TOP_K_MIN = 1
TOP_K_MAX = 100


def _coerce_top_k(value) -> int | None:
    """Converte ``top_k`` para inteiro positivo; vazio/None = sem limite."""
    if value in (None, "", "null", "none", "None"):
        return None
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return None
    return ivalue if ivalue >= TOP_K_MIN else None


def _checkbox(post, field: str) -> bool:
    """Lê um checkbox do POST (ausente = desmarcado)."""
    return str(post.get(field, "")).strip().lower() in {
        "on",
        "1",
        "true",
        "sim",
        "yes",
    }


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
    rerank = fase2.get("rerank", {}) or {}
    llm2 = fase2.get("llm", {}) or {}
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
            "estrategia": str(
                fase2.get("estrategia", "similaridade") or "similaridade"
            ),
            "top_k": _coerce_top_k(fase2.get("top_k")),
            "peso_lexical": float(fase2.get("peso_lexical", 0.0) or 0.0),
            "rerank": {
                "enabled": bool(rerank.get("enabled", False)),
                "modelo": str(rerank.get("modelo", "") or ""),
                "threshold": float(rerank.get("threshold", 0.5)),
                "top_n": int(rerank.get("top_n", 20)),
            },
            "llm": {
                "enabled": bool(llm2.get("enabled", False)),
                "provider": str(llm2.get("provider", "local") or "local"),
                "model": str(llm2.get("model", "") or ""),
                "base_url": str(llm2.get("base_url", "") or ""),
                "top_n": int(llm2.get("top_n", 20)),
            },
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

    fase2: dict[str, Any] = {}
    threshold_similaridade = _parse_float(
        post,
        "fase2_threshold",
        base["fase2"]["threshold_similaridade"],
    )
    if abs(threshold_similaridade - base["fase2"]["threshold_similaridade"]) > 1e-12:
        fase2["threshold_similaridade"] = threshold_similaridade

    estrategia = (post.get("fase2_estrategia") or "").strip() or base["fase2"][
        "estrategia"
    ]
    if estrategia != base["fase2"]["estrategia"]:
        fase2["estrategia"] = estrategia

    if "fase2_top_k" in post:
        top_k = _coerce_top_k((post.get("fase2_top_k") or "").strip())
        if top_k != base["fase2"]["top_k"]:
            fase2["top_k"] = top_k

    peso_lexical = _parse_float(
        post,
        "fase2_peso_lexical",
        base["fase2"]["peso_lexical"],
        low=0.0,
        high=1.0,
    )
    if abs(peso_lexical - base["fase2"]["peso_lexical"]) > 1e-12:
        fase2["peso_lexical"] = peso_lexical

    # A3 — reranking.
    base_rerank = base["fase2"]["rerank"]
    rerank: dict[str, Any] = {}
    enabled = _checkbox(post, "fase2_rerank_enabled")
    if enabled != base_rerank["enabled"]:
        rerank["enabled"] = enabled
    modelo = (post.get("fase2_rerank_modelo") or "").strip()
    if modelo and modelo != base_rerank["modelo"]:
        rerank["modelo"] = modelo
    rerank_threshold = _parse_float(
        post, "fase2_rerank_threshold", base_rerank["threshold"]
    )
    if abs(rerank_threshold - base_rerank["threshold"]) > 1e-12:
        rerank["threshold"] = rerank_threshold
    rerank_top_n = _parse_int(
        post, "fase2_rerank_top_n", base_rerank["top_n"],
        low=TOP_K_MIN, high=TOP_K_MAX,
    )
    if rerank_top_n != base_rerank["top_n"]:
        rerank["top_n"] = rerank_top_n
    if rerank:
        fase2["rerank"] = rerank

    # A4 — LLM.
    base_llm = base["fase2"]["llm"]
    llm2: dict[str, Any] = {}
    llm_enabled = _checkbox(post, "fase2_llm_enabled")
    if llm_enabled != base_llm["enabled"]:
        llm2["enabled"] = llm_enabled
    llm_provider = (
        (post.get("fase2_llm_provider") or "").strip() or base_llm["provider"]
    )
    if llm_provider != base_llm["provider"]:
        llm2["provider"] = llm_provider
    llm_model = (post.get("fase2_llm_model") or "").strip()
    if llm_model and llm_model != base_llm["model"]:
        llm2["model"] = llm_model
    llm_base_url = (post.get("fase2_llm_base_url") or "").strip()
    if llm_base_url and llm_base_url != base_llm["base_url"]:
        llm2["base_url"] = llm_base_url
    llm_top_n = _parse_int(
        post, "fase2_llm_top_n", base_llm["top_n"],
        low=TOP_K_MIN, high=TOP_K_MAX,
    )
    if llm_top_n != base_llm["top_n"]:
        llm2["top_n"] = llm_top_n
    if llm2:
        fase2["llm"] = llm2

    if fase2:
        overrides["fase2"] = fase2

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

    if fase2.get("estrategia") not in ESTRATEGIAS_FASE2:
        raise ValidationError(
            "Fase 2: estratégia deve ser uma de "
            + ", ".join(ESTRATEGIAS_FASE2)
            + "."
        )
    top_k = fase2.get("top_k")
    if top_k is not None and not (TOP_K_MIN <= int(top_k) <= TOP_K_MAX):
        raise ValidationError(
            f"Fase 2: top_k deve estar entre {TOP_K_MIN} e {TOP_K_MAX} "
            "(ou vazio para sem limite)."
        )
    peso_lexical = float(fase2.get("peso_lexical", 0.0) or 0.0)
    if not (0.0 <= peso_lexical <= 1.0):
        raise ValidationError("Fase 2: peso_lexical deve estar entre 0 e 1.")

    rerank = fase2.get("rerank", {}) or {}
    if not (0.0 <= float(rerank.get("threshold", 0.5)) <= 1.0):
        raise ValidationError("Fase 2: rerank.threshold deve estar entre 0 e 1.")
    if not (TOP_K_MIN <= int(rerank.get("top_n", 20)) <= TOP_K_MAX):
        raise ValidationError(
            f"Fase 2: rerank.top_n deve estar entre {TOP_K_MIN} e {TOP_K_MAX}."
        )

    llm2 = fase2.get("llm", {}) or {}
    if str(llm2.get("provider", "local")).strip().lower() not in {"local", "openai"}:
        raise ValidationError(
            "Fase 2: llm.provider deve ser 'local' ou 'openai'."
        )
    if not (TOP_K_MIN <= int(llm2.get("top_n", 20)) <= TOP_K_MAX):
        raise ValidationError(
            f"Fase 2: llm.top_n deve estar entre {TOP_K_MIN} e {TOP_K_MAX}."
        )
    if llm2.get("enabled") and not str(llm2.get("model", "") or "").strip():
        raise ValidationError(
            "Fase 2: informe o modelo quando o LLM da Fase 2 estiver ativo."
        )

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
