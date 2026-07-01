from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.test import TestCase

from core.intelligent_motor.fase4_llm_gate.llm_classifier import (
    _extract_decision_and_confidence,
    _extract_first_binary,
    _extract_json_object,
)


class ExtractFirstBinaryTests(TestCase):

    def test_extract_binary_values(self):
        self.assertEqual(_extract_first_binary("0"), 0)
        self.assertEqual(_extract_first_binary("1"), 1)

    def test_extract_yes_no_variants(self):
        self.assertEqual(_extract_first_binary("relevante"), 1)
        self.assertEqual(_extract_first_binary("falso"), 0)
        self.assertEqual(_extract_first_binary("sim"), 1)
        self.assertEqual(_extract_first_binary("não"), 0)

    def test_extract_from_json_payload(self):
        self.assertEqual(_extract_first_binary('{"decision": 1}'), 1)
        self.assertEqual(_extract_first_binary('{"relevancia_binaria": 0}'), 0)

    def test_extract_none_for_empty(self):
        self.assertIsNone(_extract_first_binary(""))
        self.assertIsNone(_extract_first_binary(None))


class ExtractJsonObjectTests(TestCase):

    def test_extract_json_object(self):
        result = _extract_json_object('{"key": "value"}')
        self.assertEqual(result["key"], "value")

    def test_extract_json_from_markdown(self):
        text = '```json\n{"key": "value"}\n```'
        result = _extract_json_object(text)
        self.assertEqual(result["key"], "value")

    def test_extract_json_embedded(self):
        text = 'Text before {"key": "val"} text after'
        result = _extract_json_object(text)
        self.assertEqual(result["key"], "val")

    def test_invalid_returns_none(self):
        self.assertIsNone(_extract_json_object("no json here"))


class ExtractDecisionAndConfidenceTests(TestCase):

    def test_extract_pipe_format(self):
        dec, conf = _extract_decision_and_confidence("1|0.90")
        self.assertEqual(dec, 1)
        self.assertAlmostEqual(conf, 0.9, places=2)

    def test_extract_from_json(self):
        dec, conf = _extract_decision_and_confidence('{"decision": 0, "confidence": 0.85}')
        self.assertEqual(dec, 0)
        self.assertAlmostEqual(conf, 0.85, places=2)

    def test_extract_none_for_empty(self):
        dec, conf = _extract_decision_and_confidence("")
        self.assertIsNone(dec)
        self.assertIsNone(conf)
