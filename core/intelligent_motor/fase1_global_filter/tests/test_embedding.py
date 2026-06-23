import sys
import importlib
import types

import pytest


def test_embedding_generator_with_dummy_model(monkeypatch, tmp_path):
    # Prepare dummy sentence_transformers module
    dummy = types.SimpleNamespace()

    class DummyModel:
        def __init__(self, name):
            self.name = name

        def encode(self, text, normalize_embeddings=True):
            return [0.0] * 384

    dummy.SentenceTransformer = DummyModel

    monkeypatch.setitem(sys.modules, "sentence_transformers", dummy)

    # Import module under test
    mod = importlib.import_module("core.intelligent_motor.fase1_global_filter.embedding_generator")
    # Reset singleton if present
    mod.EmbeddingGenerator._instance = None

    gen = mod.EmbeddingGenerator.instance()
    vec = gen.gerar("teste")

    assert isinstance(vec, list)
    assert len(vec) == 384
