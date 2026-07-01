from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.test import TestCase

from core.intelligent_motor.fase5_rich_classification.exceptions import LLMError
from core.intelligent_motor.fase5_rich_classification.llm_classifier import LLMClassifier


class LLMClassifierParseTests(TestCase):

    def test_parse_json_direct(self):
        classifier = LLMClassifier.__new__(LLMClassifier)
        result = classifier._parse_response(
            '{"sentimento": "negativo", "impacto": "alto", "urgencia": 8, "categoria": "empresa", "explicacao": "Teste"}'
        )
        self.assertEqual(result["sentimento"], "negativo")
        self.assertEqual(result["urgencia"], 8)

    def test_parse_json_in_markdown(self):
        classifier = LLMClassifier.__new__(LLMClassifier)
        text = '```json\n{"sentimento": "neutro", "impacto": "medio", "urgencia": 5, "categoria": "outros", "explicacao": "OK"}\n```'
        result = classifier._parse_response(text)
        self.assertEqual(result["sentimento"], "neutro")

    def test_parse_json_embedded_in_text(self):
        classifier = LLMClassifier.__new__(LLMClassifier)
        text = 'Aqui está a classificação: {"sentimento": "positivo", "impacto": "baixo", "urgencia": 3, "categoria": "tecnologia", "explicacao": "Bom"} e mais texto.'
        result = classifier._parse_response(text)
        self.assertEqual(result["sentimento"], "positivo")

    def test_invalid_json_raises_llm_error(self):
        classifier = LLMClassifier.__new__(LLMClassifier)
        with self.assertRaises(LLMError):
            classifier._parse_response("isto não é JSON nem tem JSON")
