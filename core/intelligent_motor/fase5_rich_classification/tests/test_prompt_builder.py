from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.test import TestCase

from core.intelligent_motor.fase5_rich_classification.prompt_builder import build_prompt


def _base_config():
    return {
        "prompt": {
            "max_content_chars": 800,
            "allowed_categorias": ["empresa", "tecnologia", "outros"],
        }
    }


class PromptBuilderTests(TestCase):

    def test_prompt_contains_required_sections(self):
        noticia = {
            "titulo": "Petrobras anuncia investimento",
            "descricao": "PETR4 amplia refino",
            "conteudo": "A Petrobras anunciou novo investimento.",
            "tickers_relacionados": ["PETR4"],
            "score_heuristico": 8,
            "criterios_ativados": ["ticker", "macro"],
            "relevancia_global": 0.85,
        }
        prompt = build_prompt(noticia, _base_config())

        self.assertIn("Petrobras anuncia investimento", prompt)
        self.assertIn("PETR4", prompt)
        self.assertIn("sentimento", prompt)
        self.assertIn("categoria", prompt)

    def test_prompt_includes_dynamic_fields(self):
        noticia = {
            "titulo": "Teste",
            "descricao": "",
            "conteudo": "",
            "tickers_relacionados": ["VALE3"],
            "score_heuristico": 3,
            "criterios_ativados": [],
            "relevancia_global": 0.6,
        }
        prompt = build_prompt(noticia, _base_config())

        self.assertIn("VALE3", prompt)
        self.assertIn("0.6", prompt)

    def test_prompt_handles_empty_inputs_gracefully(self):
        noticia = {
            "titulo": "",
            "descricao": "",
            "conteudo": "",
        }
        prompt = build_prompt(noticia, _base_config())
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)
