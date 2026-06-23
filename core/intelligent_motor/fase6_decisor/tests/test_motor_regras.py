from core.intelligent_motor.fase6_decisor.motor_regras import avaliar_regras


def test_regra_igualdade_simples():
    regras = [
        {
            "nome": "impacto_alto",
            "condicoes": {"impacto": "alto"},
            "prioridade": "alta",
            "acoes": ["dashboard"],
            "explicacao": "impacto alto",
        },
        {"nome": "default", "condicoes": {}, "prioridade": "baixa", "acoes": ["historico"], "explicacao": "default"},
    ]

    resultado = avaliar_regras({"impacto": "alto"}, regras)

    assert resultado["nome"] == "impacto_alto"
    assert resultado["prioridade"] == "alta"


def test_regra_intervalo_minimo():
    regras = [
        {
            "nome": "urgencia_alta",
            "condicoes": {"urgencia": {"min": 8}},
            "prioridade": "alta",
            "acoes": ["push"],
            "explicacao": "urgencia alta",
        }
    ]

    resultado = avaliar_regras({"urgencia": 8}, regras)

    assert resultado["nome"] == "urgencia_alta"


def test_regra_intervalo_maximo():
    regras = [
        {
            "nome": "urgencia_media",
            "condicoes": {"urgencia": {"min": 4, "max": 6}},
            "prioridade": "media",
            "acoes": ["dashboard"],
            "explicacao": "urgencia media",
        }
    ]

    resultado = avaliar_regras({"urgencia": 5}, regras)

    assert resultado["nome"] == "urgencia_media"


def test_regra_operador_and():
    regras = [
        {
            "nome": "critica",
            "condicoes": {"e": [{"impacto": "alto"}, {"sentimento": "negativo"}]},
            "prioridade": "critica",
            "acoes": ["email"],
            "explicacao": "critica",
        }
    ]

    resultado = avaliar_regras({"impacto": "alto", "sentimento": "negativo"}, regras)

    assert resultado["nome"] == "critica"


def test_regra_operador_or():
    regras = [
        {
            "nome": "alta",
            "condicoes": {"ou": [{"impacto": "alto"}, {"urgencia": {"min": 8}}]},
            "prioridade": "alta",
            "acoes": ["dashboard"],
            "explicacao": "alta",
        }
    ]

    resultado = avaliar_regras({"urgencia": 8}, regras)

    assert resultado["nome"] == "alta"


def test_primeira_regra_valida_tem_prioridade():
    regras = [
        {
            "nome": "primeira",
            "condicoes": {"impacto": "alto"},
            "prioridade": "alta",
            "acoes": ["dashboard"],
            "explicacao": "primeira",
        },
        {
            "nome": "segunda",
            "condicoes": {"impacto": "alto"},
            "prioridade": "critica",
            "acoes": ["email"],
            "explicacao": "segunda",
        },
    ]

    resultado = avaliar_regras({"impacto": "alto"}, regras)

    assert resultado["nome"] == "primeira"
    assert resultado["prioridade"] == "alta"


def test_regra_default():
    regras = [
        {
            "nome": "default",
            "condicoes": {},
            "prioridade": "baixa",
            "acoes": ["historico"],
            "explicacao": "default",
        }
    ]

    resultado = avaliar_regras({"impacto": "baixo"}, regras)

    assert resultado["nome"] == "default"
    assert resultado["prioridade"] == "baixa"
