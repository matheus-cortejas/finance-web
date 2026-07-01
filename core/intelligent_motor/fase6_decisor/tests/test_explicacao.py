from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.test import TestCase

from core.intelligent_motor.fase6_decisor.explicacao import gerar_explicacao


class ExplicacaoTests(TestCase):

    def test_generate_explanation_from_rule(self):
        regra = {"nome": "impacto_negativo_alto", "explicacao": "Impacto alto com sentimento negativo."}
        result = gerar_explicacao(regra)
        self.assertEqual(result, "Impacto alto com sentimento negativo.")

    def test_generate_default_explanation_for_critical(self):
        regra = {"nome": "regra_critica", "prioridade": "critica"}
        result = gerar_explicacao(regra)
        self.assertIn("crítica", result.lower())

    def test_generate_default_explanation_for_missing_input(self):
        result = gerar_explicacao(None)
        self.assertIn("histórico", result.lower())
