from typing import Dict, Any


def fallback_classify(
    noticia: dict,
    config: dict,
) -> dict:
    """
    Fallback heurístico para classificação rica.

    Utilizado quando:
    - LLM falha
    - timeout
    - resposta inválida
    - erro de parsing

    Todas as regras são dirigidas pelo config.yaml.
    """

    fallback_cfg = config.get("fallback", {})

    defaults = fallback_cfg.get("defaults", {})

    texto = " ".join(
        [
            noticia.get("titulo", ""),
            noticia.get("descricao", ""),
            noticia.get("conteudo", ""),
        ]
    ).lower()

    score = noticia.get("score_heuristico")

    try:
        score = float(score)
    except Exception:
        score = None

    # --------------------------------------------------
    # SENTIMENTO
    # --------------------------------------------------

    sentimento_cfg = fallback_cfg.get("sentimento", {})

    positivas = sentimento_cfg.get(
        "positivo_keywords",
        []
    )

    negativas = sentimento_cfg.get(
        "negativo_keywords",
        []
    )

    sentimento = defaults.get(
        "sentimento",
        "neutro"
    )

    if any(p in texto for p in negativas):
        sentimento = "negativo"

    elif any(p in texto for p in positivas):
        sentimento = "positivo"

    # --------------------------------------------------
    # IMPACTO
    # --------------------------------------------------

    impacto_cfg = fallback_cfg.get(
        "impacto_thresholds",
        {}
    )

    impacto_alto = impacto_cfg.get(
        "alto",
        8
    )

    impacto_medio = impacto_cfg.get(
        "medio",
        5
    )

    impacto = defaults.get(
        "impacto",
        "medio"
    )

    if score is not None:

        if score >= impacto_alto:
            impacto = "alto"

        elif score >= impacto_medio:
            impacto = "medio"

        else:
            impacto = "baixo"

    # --------------------------------------------------
    # URGÊNCIA
    # --------------------------------------------------

    urgencia_cfg = fallback_cfg.get(
        "urgencia",
        {}
    )

    urgencia_default = urgencia_cfg.get(
        "default",
        5
    )

    urgencia_max = urgencia_cfg.get(
        "max",
        10
    )

    urgencia = urgencia_default

    urgencia_keywords = fallback_cfg.get(
        "urgencia_keywords",
        {}
    )

    for regra in urgencia_keywords.values():

        palavras = regra.get(
            "palavras",
            []
        )

        valor = regra.get(
            "valor",
            urgencia_default
        )

        if any(p in texto for p in palavras):
            urgencia = max(
                urgencia,
                valor
            )

    if urgencia == urgencia_default and score is not None:

        urgencia = min(
            urgencia_max,
            max(0, int(score))
        )

    # --------------------------------------------------
    # CATEGORIA
    # --------------------------------------------------

    categoria = defaults.get(
        "categoria",
        "outros"
    )

    categorias_cfg = fallback_cfg.get(
        "categorias",
        {}
    )

    for nome_categoria, palavras in categorias_cfg.items():

        if any(p in texto for p in palavras):

            categoria = nome_categoria
            break

    # fallback secundário:
    # ticker relacionado => empresa

    if (
        categoria == "outros"
        and noticia.get("tickers_relacionados")
    ):
        categoria = "empresa"

    # --------------------------------------------------
    # EXPLICAÇÃO
    # --------------------------------------------------

    explicacao = defaults.get(
        "explicacao",
        "Classificação produzida por fallback heurístico."
    )

    # --------------------------------------------------
    # SAÍDA
    # --------------------------------------------------

    return {
        "sentimento": sentimento,
        "impacto": impacto,
        "urgencia": urgencia,
        "categoria": categoria,
        "explicacao": explicacao,
    }