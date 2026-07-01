from core.intelligent_motor.fase3_heuristica.criterios import (
    avaliar_ticker_explicito,
    avaliar_setor_relacionado,
    avaliar_palavras_macro,
    avaliar_palavras_negativas,
    avaliar_palavras_urgencia,
)
from core.intelligent_motor.config_loader import load_global_config


def test_avaliar_ticker_explicito():
    noticia = {"titulo": "Ação PETR4 sobe", "descricao": "", "conteudo": ""}
    ok, found = avaliar_ticker_explicito(noticia)
    assert ok
    assert any("petr4" in t.lower() for t in found)


def test_avaliar_setor_relacionado():
    noticia = {"tickers_relacionados": ["PETR4"]}
    assert avaliar_setor_relacionado(noticia)


def test_palavras_macro_neg_urgencia():
    config = load_global_config()
    noticia = {"titulo": "Selic sobe e há prejuízo urgente", "descricao": "", "conteudo": ""}
    assert avaliar_palavras_macro(noticia, config=config)
    assert avaliar_palavras_negativas(noticia, config=config)
    assert avaliar_palavras_urgencia(noticia, config=config)
