from core.intelligent_motor.fase3_heuristica.pipeline import avaliar_heuristica


def test_avaliar_heuristica_simple():
    noticia = {
        "id": 1,
        "titulo": "PETR4 despenca após multa",
        "descricao": "",
        "conteudo": "",
        "tickers_relacionados": ["PETR4"],
    }

    res = avaliar_heuristica(noticia)
    assert "score_heuristico" in res
    assert res["score_heuristico"] > 0
    assert "criterios_ativados" in res
