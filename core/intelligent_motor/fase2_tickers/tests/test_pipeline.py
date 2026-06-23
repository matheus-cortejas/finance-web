import importlib


def _make_vec(pos_index: int, dim: int = 384):
    v = [0.0] * dim
    v[pos_index] = 1.0
    return v


def test_relacionar_tickers(monkeypatch):
    pipeline = importlib.import_module("core.intelligent_motor.fase2_tickers.pipeline")

    emb_ref = _make_vec(0)
    emb_other = _make_vec(1)

    class DummyStore:
        def __init__(self, *a, **k):
            self.map = {"PETR4": emb_ref, "VALE3": emb_other}

        def get_embedding(self, ticker):
            return self.map.get(ticker)

    monkeypatch.setattr(pipeline, "AssetEmbeddingStore", DummyStore)

    noticia = {"id": 1, "embedding_noticia": emb_ref}
    carteira = ["PETR4", "VALE3"]

    tickers = pipeline.relacionar_tickers(noticia, carteira)
    assert tickers == ["PETR4"]
