from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.test import TestCase

from core.intelligent_motor.fase5_rich_classification.exceptions import ValidationError
from core.intelligent_motor.fase5_rich_classification.validator import validar_resposta


def _base_config():
    return {
        "prompt": {
            "allowed_sentimentos": ["positivo", "neutro", "negativo"],
            "allowed_impactos": ["baixo", "medio", "alto"],
            "allowed_categorias": ["resultados", "regulacao", "commodities", "macroeconomia", "empresa", "tecnologia", "outros"],
        },
        "validation": {
            "urgencia": {"min": 0, "max": 10},
        },
    }


def _valid_resposta():
    return {
        "sentimento": "negativo",
        "impacto": "alto",
        "urgencia": 8,
        "categoria": "empresa",
        "explicacao": "Notícia negativa sobre a empresa.",
    }


class ValidatorTests(TestCase):

    def test_valid_response_passes_validation(self):
        result = validar_resposta(_valid_resposta(), _base_config())
        self.assertEqual(result["sentimento"], "negativo")
        self.assertEqual(result["urgencia"], 8)

    def test_missing_required_field_raises_error(self):
        data = _valid_resposta()
        del data["categoria"]
        with self.assertRaises(ValidationError):
            validar_resposta(data, _base_config())

    def test_invalid_enum_values_raise_error(self):
        data = _valid_resposta()
        data["sentimento"] = "fantástico"
        with self.assertRaises(ValidationError):
            validar_resposta(data, _base_config())

    def test_urgency_out_of_range_rejected(self):
        data = _valid_resposta()
        data["urgencia"] = 15
        with self.assertRaises(ValidationError):
            validar_resposta(data, _base_config())

    def test_empty_explicacao_rejected(self):
        data = _valid_resposta()
        data["explicacao"] = ""
        with self.assertRaises(ValidationError):
            validar_resposta(data, _base_config())

    def test_invalid_categoria_rejected(self):
        data = _valid_resposta()
        data["categoria"] = "crypto"
        with self.assertRaises(ValidationError):
            validar_resposta(data, _base_config())

    def test_boundary_values_allowed(self):
        data = _valid_resposta()
        data["urgencia"] = 0
        result = validar_resposta(data, _base_config())
        self.assertEqual(result["urgencia"], 0)

        data["urgencia"] = 10
        result = validar_resposta(data, _base_config())
        self.assertEqual(result["urgencia"], 10)
