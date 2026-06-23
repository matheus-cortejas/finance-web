from core.intelligent_motor.fase6_decisor.pipeline import decidir_alerta


def test_pipeline_regra_critica():
    noticia = {
        "relevancia_global": 0.9,
        "score_heuristico": 12,
        "sentimento": "negativo",
        "impacto": "alto",
        "urgencia": 8,
        "categoria": "commodities",
    }

    out = decidir_alerta(noticia)

    assert out["prioridade"] == "critica"
    assert out["regra_disparada"] == "impacto_negativo_alto"
    assert out["acao_sugerida"] == ["email", "push", "dashboard_destacado"]


def test_pipeline_regra_media():
    noticia = {
        "relevancia_global": 0.86,
        "score_heuristico": 4,
        "sentimento": "neutro",
        "impacto": "medio",
        "urgencia": 4,
        "categoria": "macroeconomia",
    }

    out = decidir_alerta(noticia)

    assert out["prioridade"] == "media"
    assert out["regra_disparada"] == "score_heuristico_ou_relevancia"
    assert out["acao_sugerida"] == ["dashboard"]


def test_pipeline_fallback_default():
    noticia = {
        "relevancia_global": 0.1,
        "score_heuristico": 1,
        "sentimento": "neutro",
        "impacto": "baixo",
        "urgencia": 1,
        "categoria": "outros",
    }

    out = decidir_alerta(noticia)

    assert out["prioridade"] == "baixa"
    assert out["acao_sugerida"] == ["historico"]
    assert out["regra_disparada"] == "default"


def test_pipeline_filtro_por_perfil():
    noticia = {
        "relevancia_global": 0.9,
        "score_heuristico": 12,
        "sentimento": "negativo",
        "impacto": "alto",
        "urgencia": 8,
        "categoria": "commodities",
    }

    perfil = {
        "canais_habilitados": ["dashboard"],
        "notificar_apenas_categorias": ["commodities"],
    }

    out = decidir_alerta(noticia, perfil=perfil)

    assert out["prioridade"] == "critica"
    assert out["acao_sugerida"] == ["dashboard_destacado"]


def test_pipeline_categoria_bloqueada():
    noticia = {
        "relevancia_global": 0.9,
        "score_heuristico": 12,
        "sentimento": "negativo",
        "impacto": "alto",
        "urgencia": 8,
        "categoria": "tecnologia",
    }

    perfil = {
        "canais_habilitados": ["email", "push", "dashboard"],
        "notificar_apenas_categorias": ["commodities"],
    }

    out = decidir_alerta(noticia, perfil=perfil)

    assert out["prioridade"] == "baixa"
    assert out["acao_sugerida"] == ["historico"]
