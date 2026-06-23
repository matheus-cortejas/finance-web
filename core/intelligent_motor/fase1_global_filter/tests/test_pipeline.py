import importlib
import types

from core.intelligent_motor.fase1_global_filter.pipeline import avaliar_relevancia_global


class DummyGenerator:
    def __init__(self, emb_noticia, emb_ref):
        self.emb_noticia = emb_noticia
        self.emb_ref = emb_ref

    def gerar(self, texto: str):
        if "Análise financeira" in texto or "financeiro" in texto:
            return self.emb_ref
        return self.emb_noticia


def test_pipeline_accept_and_discard(monkeypatch, tmp_path):
    # Prepare deterministic embeddings
    emb_ref = [1.0, 0.0, 0.0]
    emb_same = [1.0, 0.0, 0.0]
    emb_orth = [0.0, 1.0, 0.0]

    # Monkeypatch EmbeddingGenerator.instance to return DummyGenerator
    mod = importlib.import_module("core.intelligent_motor.fase1_global_filter.embedding_generator")
    mod.EmbeddingGenerator._instance = None

    dummy_gen = DummyGenerator(emb_same, emb_ref)
    monkeypatch.setattr(mod.EmbeddingGenerator, "instance", classmethod(lambda cls: dummy_gen))

    # Monkeypatch cache manager to use sqlite in tmp
    cache_mod = importlib.import_module("core.intelligent_motor.fase1_global_filter.cache_manager")
    monkeypatch.setattr(cache_mod, "get_cache_manager", lambda: cache_mod.SQLiteCache(path=str(tmp_path / "c.db")))

    noticia = {"id": 1, "titulo": "Taxa Selic sobe", "descricao": "Aumento de juros", "conteudo": ""}
    res = avaliar_relevancia_global(noticia)
    assert isinstance(res, dict)
    assert res["id"] == 1

    # Now test discard by using orthogonal embedding
    dummy_gen2 = DummyGenerator(emb_orth, emb_ref)
    monkeypatch.setattr(mod.EmbeddingGenerator, "instance", classmethod(lambda cls: dummy_gen2))

    noticia2 = {"id": 2, "titulo": "Receita de bolo", "descricao": "Culinária", "conteudo": ""}
    res2 = avaliar_relevancia_global(noticia2)
    assert res2 is None
