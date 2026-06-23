from core.intelligent_motor.fase3_heuristica.criterios import (
    avaliar_ticker_explicito,
    avaliar_setor_relacionado,
    avaliar_palavras_macro,
    avaliar_palavras_negativas,
    avaliar_palavras_urgencia,
)


def test_avaliar_ticker_explicito():
    noticia = {"titulo": "Ação PETR4 sobe", "descricao": "", "conteudo": ""}
    ok, found = avaliar_ticker_explicito(noticia)
    assert ok
    assert any("PETR4" in t for t in found)


def test_avaliar_setor_relacionado():
    noticia = {"tickers_relacionados": ["PETR4"]}
    assert avaliar_setor_relacionado(noticia)


def test_palavras_macro_neg_urgencia():
    noticia = {"titulo": "Selic sobe e há prejuízo urgente", "descricao": "", "conteudo": ""}
    assert avaliar_palavras_macro(noticia)
    assert avaliar_palavras_negativas(noticia)
    assert avaliar_palavras_urgencia(noticia)
