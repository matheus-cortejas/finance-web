from core.intelligent_motor.fase3_heuristica.pipeline import avaliar_heuristica
from core.intelligent_motor.config_loader import load_global_config


def test_avaliar_heuristica_simple():
    config = load_global_config()
    noticia = {
        "id": 1,
        "titulo": "PETR4 despenca após multa",
        "descricao": "",
        "conteudo": "",
        "tickers_relacionados": ["PETR4"],
    }

    res = avaliar_heuristica(noticia, config=config)
    assert "score_heuristico" in res
    assert res["score_heuristico"] > 0
    assert "criterios_ativados" in res
