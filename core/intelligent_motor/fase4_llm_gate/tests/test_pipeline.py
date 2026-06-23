from core.intelligent_motor.fase4_llm_gate.pipeline import classificar_noticia
from core.intelligent_motor.fase4_llm_gate.llm_classifier import LLMClassifier


def test_pipeline_bypass_high_score():
    noticia = {"score_heuristico": 8, "titulo": "t", "descricao": "d"}
    out = classificar_noticia(noticia)
    assert out["relevancia_binaria"] == 1
    assert out["provider_fase4"] == "bypass"


def test_pipeline_bypass_low_score():
    noticia = {"score_heuristico": 2, "titulo": "t", "descricao": "d"}
    out = classificar_noticia(noticia)
    assert out["relevancia_binaria"] == 0
    assert out["provider_fase4"] == "bypass"


def test_pipeline_calls_llm(monkeypatch):
    noticia = {"score_heuristico": 5, "titulo": "t", "descricao": "d", "criterios_ativados": []}

    def fake_classify(self, prompt, timeout_seconds=30):
        return 1

    monkeypatch.setattr(LLMClassifier, "classificar", fake_classify)
    out = classificar_noticia(noticia)
    assert out["relevancia_binaria"] == 1
    assert out["provider_fase4"] in ("openai", "fallback")
