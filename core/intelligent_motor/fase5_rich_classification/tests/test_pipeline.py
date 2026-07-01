from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.test import TestCase

from core.intelligent_motor.fase5_rich_classification.pipeline import classificar_noticia_rica


class Fase5PipelineTests(TestCase):

    def test_fase5_skipped_when_irrelevant(self):
        noticia = {"relevancia_binaria": 0, "titulo": "Teste"}
        result = classificar_noticia_rica(noticia, config={})
        self.assertNotIn("sentimento", result)

    def test_llm_success_path_updates_fields(self):
        noticia = {"relevancia_binaria": 1, "titulo": "Teste"}

        mock_classifier = MagicMock()
        mock_classifier.classificar.return_value = {
            "sentimento": "negativo",
            "impacto": "alto",
            "urgencia": 8,
            "categoria": "empresa",
            "explicacao": "Impacto negativo.",
        }

        result = classificar_noticia_rica(noticia, config={"fase5": {}}, classifier=mock_classifier)
        self.assertEqual(result["sentimento"], "negativo")
        self.assertEqual(result["impacto"], "alto")

    def test_llm_failure_falls_back_to_rule_based(self):
        noticia = {
            "relevancia_binaria": 1,
            "titulo": "Petrobras prejuízo",
            "descricao": "Queda no petróleo",
            "conteudo": "",
            "score_heuristico": 3,
            "tickers_relacionados": ["PETR4"],
        }

        mock_classifier = MagicMock()
        mock_classifier.classificar.side_effect = Exception("LLM falhou")

        config = {"fase5": {"fallback": {"defaults": {"sentimento": "neutro", "impacto": "medio", "categoria": "outros", "explicacao": "Fallback."}}}}

        result = classificar_noticia_rica(noticia, config=config, classifier=mock_classifier)
        self.assertIn("sentimento", result)
        self.assertIn(result["sentimento"], ["positivo", "neutro", "negativo"])

    def test_custom_classifier_is_used_when_injected(self):
        noticia = {"relevancia_binaria": 1, "titulo": "Teste"}

        mock_classifier = MagicMock()
        mock_classifier.classificar.return_value = {
            "sentimento": "neutro",
            "impacto": "medio",
            "urgencia": 5,
            "categoria": "outros",
            "explicacao": "Teste.",
        }

        classificar_noticia_rica(noticia, config={"fase5": {}}, classifier=mock_classifier)
        mock_classifier.classificar.assert_called_once()
