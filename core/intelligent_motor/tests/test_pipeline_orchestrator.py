from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.test import TestCase

from core.intelligent_motor.pipeline_orchestrator import processar_noticia_completa


class PipelineOrchestratorTests(TestCase):

    @patch("core.intelligent_motor.pipeline_orchestrator.registrar_metrica")
    @patch("core.intelligent_motor.pipeline_orchestrator.avaliar_relevancia_global", return_value=None)
    @patch("core.intelligent_motor.pipeline_orchestrator.load_global_config", return_value={"fase1": {}})
    def test_fase1_filters_irrelevant_news(self, mock_config, mock_fase1, mock_metrics):
        noticia = {"id": 1, "titulo": "Teste", "descricao": "Desc"}
        result = processar_noticia_completa(noticia, carteira_usuario=[])

        self.assertEqual(result.get("relevancia_binaria"), 0)
        mock_fase1.assert_called_once()

    @patch("core.intelligent_motor.pipeline_orchestrator.registrar_metrica")
    @patch("core.intelligent_motor.pipeline_orchestrator.classificar_noticia")
    @patch("core.intelligent_motor.pipeline_orchestrator.avaliar_heuristica")
    @patch("core.intelligent_motor.pipeline_orchestrator.relacionar_tickers", return_value=[])
    @patch("core.intelligent_motor.pipeline_orchestrator.avaliar_relevancia_global")
    @patch("core.intelligent_motor.pipeline_orchestrator.load_global_config", return_value={"fase1": {}, "fase3": {}, "fase4": {}})
    def test_fase4_blocks_irrelevant_news(self, mock_config, mock_fase1, mock_fase2, mock_fase3, mock_fase4, mock_metrics):
        mock_fase1.return_value = {"id": 1, "relevancia_global": 0.8, "embedding": [0.1] * 384}
        mock_fase3.return_value = {"id": 1, "score_heuristico": 5, "criterios_ativados": []}
        mock_fase4.return_value = {"id": 1, "relevancia_binaria": 0}

        noticia = {"id": 1, "titulo": "Teste"}
        result = processar_noticia_completa(noticia, carteira_usuario=[])

        self.assertEqual(result.get("relevancia_binaria"), 0)

    @patch("core.intelligent_motor.pipeline_orchestrator.registrar_metrica")
    @patch("core.intelligent_motor.pipeline_orchestrator.classificar_noticia_rica")
    @patch("core.intelligent_motor.pipeline_orchestrator.classificar_noticia")
    @patch("core.intelligent_motor.pipeline_orchestrator.avaliar_heuristica")
    @patch("core.intelligent_motor.pipeline_orchestrator.relacionar_tickers", return_value=["PETR4"])
    @patch("core.intelligent_motor.pipeline_orchestrator.avaliar_relevancia_global")
    @patch("core.intelligent_motor.pipeline_orchestrator.load_global_config", return_value={"fase1": {}, "fase3": {}, "fase4": {}, "fase5": {}})
    def test_full_pipeline_success_flow(self, mock_config, mock_fase1, mock_fase2, mock_fase3, mock_fase4, mock_fase5, mock_metrics):
        mock_fase1.return_value = {"id": 1, "relevancia_global": 0.9, "embedding": [0.1] * 384}
        mock_fase3.return_value = {"id": 1, "score_heuristico": 8, "criterios_ativados": ["ticker"]}
        mock_fase4.return_value = {"id": 1, "relevancia_binaria": 1}
        mock_fase5.side_effect = lambda noticia, **kwargs: noticia.update({
            "sentimento": "negativo", "impacto": "alto", "urgencia": 8, "categoria": "empresa"
        }) or noticia

        noticia = {"id": 1, "titulo": "Petrobras anuncia investimento"}
        result = processar_noticia_completa(noticia, carteira_usuario=["PETR4"])

        self.assertEqual(result["relevancia_binaria"], 1)
        self.assertEqual(result["sentimento"], "negativo")

    @patch("core.intelligent_motor.pipeline_orchestrator.registrar_metrica")
    @patch("core.intelligent_motor.pipeline_orchestrator.avaliar_relevancia_global", side_effect=Exception("Model failed"))
    @patch("core.intelligent_motor.pipeline_orchestrator.load_global_config", return_value={"fase1": {}})
    def test_pipeline_handles_unexpected_exception(self, mock_config, mock_fase1, mock_metrics):
        noticia = {"id": 1, "titulo": "Teste"}
        with self.assertRaises(Exception):
            processar_noticia_completa(noticia, carteira_usuario=[])

    @patch("core.intelligent_motor.pipeline_orchestrator.registrar_metrica")
    @patch("core.intelligent_motor.pipeline_orchestrator.classificar_noticia_rica")
    @patch("core.intelligent_motor.pipeline_orchestrator.classificar_noticia")
    @patch("core.intelligent_motor.pipeline_orchestrator.avaliar_heuristica")
    @patch("core.intelligent_motor.pipeline_orchestrator.relacionar_tickers", return_value=["PETR4"])
    @patch("core.intelligent_motor.pipeline_orchestrator.avaliar_relevancia_global")
    @patch("core.intelligent_motor.pipeline_orchestrator.load_global_config", return_value={"fase1": {}, "fase3": {}, "fase4": {}, "fase5": {}})
    def test_orchestrator_does_not_skip_fase5_when_required(self, mock_config, mock_fase1, mock_fase2, mock_fase3, mock_fase4, mock_fase5, mock_metrics):
        mock_fase1.return_value = {"id": 1, "relevancia_global": 0.9, "embedding": [0.1] * 384}
        mock_fase3.return_value = {"id": 1, "score_heuristico": 8, "criterios_ativados": ["ticker"]}
        mock_fase4.return_value = {"id": 1, "relevancia_binaria": 1}
        mock_fase5.side_effect = lambda noticia, **kwargs: noticia.update({
            "sentimento": "negativo", "impacto": "alto", "urgencia": 8, "categoria": "empresa"
        }) or noticia

        noticia = {"id": 1, "titulo": "Petrobras anuncia investimento"}
        result = processar_noticia_completa(noticia, carteira_usuario=["PETR4"])

        mock_fase5.assert_called_once()
        self.assertEqual(result["relevancia_binaria"], 1)
        self.assertEqual(result["sentimento"], "negativo")
        self.assertEqual(result["impacto"], "alto")
        self.assertEqual(result["urgencia"], 8)
        self.assertEqual(result["categoria"], "empresa")
