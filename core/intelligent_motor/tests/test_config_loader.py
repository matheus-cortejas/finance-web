from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.test import TestCase

from core.intelligent_motor.config_loader import _substituir_env, load_global_config


class SubstituirEnvTests(TestCase):

    def test_env_variable_replacement(self):
        os.environ["TEST_VAR_XYZ"] = "replaced_value"
        try:
            result = _substituir_env({"key": "${TEST_VAR_XYZ}"})
            self.assertEqual(result["key"], "replaced_value")
        finally:
            del os.environ["TEST_VAR_XYZ"]

    def test_missing_env_variable_keeps_placeholder(self):
        result = _substituir_env({"key": "${NONEXISTENT_VAR_12345}"})
        self.assertEqual(result["key"], "${NONEXISTENT_VAR_12345}")

    def test_recursive_config_parsing(self):
        os.environ["NESTED_VAL"] = "nested_ok"
        try:
            data = {
                "level1": {
                    "level2": ["${NESTED_VAL}", "static"],
                }
            }
            result = _substituir_env(data)
            self.assertEqual(result["level1"]["level2"][0], "nested_ok")
            self.assertEqual(result["level1"]["level2"][1], "static")
        finally:
            del os.environ["NESTED_VAL"]


class LoadGlobalConfigTests(TestCase):

    def test_global_config_structure_valid(self):
        config = load_global_config()
        self.assertIsInstance(config, dict)
        self.assertIn("fase1", config)
        self.assertIn("fase6", config)
