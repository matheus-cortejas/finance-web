from .exceptions import ValidationError


def validar_resposta(resposta: dict, config: dict) -> dict:
    """
    Valida a resposta produzida pela LLM ou pelo fallback.

    Retorna o próprio dicionário normalizado caso seja válido.

    Levanta ValidationError caso algum campo seja inválido.
    """

    if not isinstance(resposta, dict):
        raise ValidationError("Resposta não é um dict")

    validation_cfg = config.get("validation", {})
    prompt_cfg = config.get("prompt", {})

    required_fields = validation_cfg.get(
        "required_fields",
        [
            "sentimento",
            "impacto",
            "urgencia",
            "categoria",
            "explicacao",
        ],
    )

    allowed_sentimentos = set(
        prompt_cfg.get(
            "allowed_sentimentos",
            ["positivo", "neutro", "negativo"],
        )
    )

    allowed_impactos = set(
        prompt_cfg.get(
            "allowed_impactos",
            ["baixo", "medio", "alto"],
        )
    )

    allowed_categorias = set(
        prompt_cfg.get(
            "allowed_categorias",
            [
                "resultados",
                "regulacao",
                "commodities",
                "macroeconomia",
                "empresa",
                "tecnologia",
                "outros",
            ],
        )
    )

    urgencia_cfg = validation_cfg.get("urgencia", {})
    urgencia_min = urgencia_cfg.get("min", 0)
    urgencia_max = urgencia_cfg.get("max", 10)

    # --------------------------------------------------
    # Campos obrigatórios
    # --------------------------------------------------

    for campo in required_fields:
        if campo not in resposta:
            raise ValidationError(
                f"Campo obrigatório ausente: {campo}"
            )

    # --------------------------------------------------
    # Sentimento
    # --------------------------------------------------

    sentimento = str(resposta["sentimento"]).strip().lower()

    if sentimento not in allowed_sentimentos:
        raise ValidationError(
            f"Sentimento inválido: {sentimento}"
        )

    # --------------------------------------------------
    # Impacto
    # --------------------------------------------------

    impacto = str(resposta["impacto"]).strip().lower()

    if impacto not in allowed_impactos:
        raise ValidationError(
            f"Impacto inválido: {impacto}"
        )

    # --------------------------------------------------
    # Urgência
    # --------------------------------------------------

    try:
        urgencia = int(resposta["urgencia"])
    except Exception:
        raise ValidationError(
            "Urgencia deve ser um inteiro"
        )

    if not (urgencia_min <= urgencia <= urgencia_max):
        raise ValidationError(
            f"Urgencia fora do intervalo "
            f"{urgencia_min}-{urgencia_max}"
        )

    # --------------------------------------------------
    # Categoria
    # --------------------------------------------------

    categoria = str(resposta["categoria"]).strip().lower()

    if categoria not in allowed_categorias:
        raise ValidationError(
            f"Categoria inválida: {categoria}"
        )

    # --------------------------------------------------
    # Explicação
    # --------------------------------------------------

    explicacao = resposta["explicacao"]

    if not isinstance(explicacao, str):
        raise ValidationError(
            "Explicacao deve ser string"
        )

    explicacao = explicacao.strip()

    if not explicacao:
        raise ValidationError(
            "Explicacao vazia"
        )

    # --------------------------------------------------
    # Normalização
    # --------------------------------------------------

    resposta["sentimento"] = sentimento
    resposta["impacto"] = impacto
    resposta["categoria"] = categoria
    resposta["urgencia"] = urgencia
    resposta["explicacao"] = explicacao

    return resposta