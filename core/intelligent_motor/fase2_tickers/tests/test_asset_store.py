import sys
import types
import importlib


def test_asset_store_generate_and_persist(monkeypatch, tmp_path):
    # Prepare dummy sentence_transformers
    dummy = types.SimpleNamespace()

    class DummyModel:
        def __init__(self, name):
            self.name = name

        def encode(self, text, normalize_embeddings=True):
            return [0.0] * 384

    dummy.SentenceTransformer = DummyModel
    monkeypatch.setitem(sys.modules, "sentence_transformers", dummy)

    mod = importlib.import_module("core.intelligent_motor.fase2_tickers.asset_embedding_store")
    mapping_path = tmp_path / "mapping.json"
    mapping_content = {"PETR4": "Petrobras petróleo"}
    mapping_path.write_text(importlib.import_module('json').dumps(mapping_content), encoding="utf-8")

    store = mod.AssetEmbeddingStore(mapping_path=str(mapping_path), db_path=str(tmp_path / "assets.db"))
    data = store.load_mapping()
    assert "PETR4" in data

    store.generate_and_persist_all()
    emb = store.get_embedding("PETR4")
    assert isinstance(emb, list)
    assert len(emb) == 384

    tickers = store.list_tickers()
    assert "PETR4" in tickers
