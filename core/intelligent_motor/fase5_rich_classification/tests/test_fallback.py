from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.test import TestCase

from core.intelligent_motor.fase5_rich_classification.fallback import fallback_classify


def _base_config():
    return {
        "fallback": {
            "defaults": {
                "sentimento": "neutro",
                "impacto": "medio",
                "categoria": "outros",
                "explicacao": "Classificação produzida por fallback heurístico.",
            },
            "sentimento": {
                "positivo_keywords": ["lucro", "alta", "crescimento"],
                "negativo_keywords": ["prejuízo", "queda", "crise"],
            },
            "impacto_thresholds": {"alto": 8, "medio": 5},
            "urgencia": {"default": 5, "max": 10},
            "urgencia_keywords": {
                "urgente": {"palavras": ["urgente", "imediato"], "valor": 9},
            },
            "categorias": {
                "energia": ["petróleo", "combustível"],
                "tecnologia": ["software", "inteligência artificial"],
            },
        }
    }


def _base_noticia(**overrides):
    noticia = {
        "titulo": "Notícia teste",
        "descricao": "Descrição teste",
        "conteudo": "Conteúdo teste",
        "score_heuristico": 5,
    }
    noticia.update(overrides)
    return noticia


class FallbackClassifyTests(TestCase):

    def test_fallback_sentiment_negative(self):
        noticia = _base_noticia(titulo="Empresa anuncia prejuízo")
        result = fallback_classify(noticia, _base_config())
        self.assertEqual(result["sentimento"], "negativo")

    def test_fallback_sentiment_positive(self):
        noticia = _base_noticia(titulo="Empresa reporta lucro recorde")
        result = fallback_classify(noticia, _base_config())
        self.assertEqual(result["sentimento"], "positivo")

    def test_fallback_sentiment_neutral(self):
        noticia = _base_noticia(titulo="Mercado permanece estável")
        result = fallback_classify(noticia, _base_config())
        self.assertEqual(result["sentimento"], "neutro")

    def test_fallback_impact_level_increases_with_score(self):
        noticia_low = _base_noticia(score_heuristico=3)
        noticia_high = _base_noticia(score_heuristico=9)

        result_low = fallback_classify(noticia_low, _base_config())
        result_high = fallback_classify(noticia_high, _base_config())

        impacto_order = {"baixo": 0, "medio": 1, "alto": 2}
        self.assertGreater(impacto_order[result_high["impacto"]], impacto_order[result_low["impacto"]])

    def test_fallback_impact_level_decreases_with_score(self):
        noticia = _base_noticia(score_heuristico=2)
        result = fallback_classify(noticia, _base_config())
        self.assertEqual(result["impacto"], "baixo")

    def test_fallback_handles_missing_score(self):
        noticia = _base_noticia(score_heuristico=None)
        result = fallback_classify(noticia, _base_config())
        self.assertIn(result["impacto"], ["baixo", "medio", "alto"])

    def test_fallback_category_from_tickers(self):
        noticia = _base_noticia(titulo="Mercado geral", tickers_relacionados=["PETR4"])
        result = fallback_classify(noticia, _base_config())
        self.assertEqual(result["categoria"], "empresa")

    def test_fallback_keyword_based_urgency(self):
        noticia = _base_noticia(titulo="URGENTE: queda abrupta")
        result = fallback_classify(noticia, _base_config())
        self.assertGreaterEqual(result["urgencia"], 5)
