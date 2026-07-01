from __future__ import annotations

import json
import os
import tempfile

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.test import TestCase

from core.intelligent_motor.pipeline_metrics import (
    _resolve_metrics_path,
    classificar_tickers_por_origem,
    invalidar_cache_tickers,
    ler_metricas,
    registrar_metrica,
)


class RegistrarMetricaTests(TestCase):

    def test_metric_written_to_jsonl(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            config = {"metrics": {"path": path}}
            registrar_metrica({"noticia_id": 1, "link": "https://test.com"}, config=config)

            with open(path, "r", encoding="utf-8") as f:
                line = f.readline().strip()
            data = json.loads(line)
            self.assertEqual(data["noticia_id"], 1)
            self.assertIn("registrado_em", data)
        finally:
            os.unlink(path)

    def test_metrics_are_read_correctly(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"noticia_id": 1}\n')
            f.write('{"noticia_id": 2}\n')
            path = f.name
        try:
            result = ler_metricas(path=path)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["noticia_id"], 1)
        finally:
            os.unlink(path)

    def test_empty_metrics_file_returns_empty_list(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            result = ler_metricas(path=path)
            self.assertEqual(result, [])
        finally:
            os.unlink(path)

    def test_invalid_lines_are_ignored(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"noticia_id": 1}\n')
            f.write('NOT VALID JSON\n')
            f.write('{"noticia_id": 2}\n')
            path = f.name
        try:
            result = ler_metricas(path=path)
            self.assertEqual(len(result), 2)
        finally:
            os.unlink(path)


class TickerClassificationTests(TestCase):

    def test_ticker_classification_by_source(self):
        from core.models import Ativo

        Ativo.objects.create(ticker="PETR4", nome="Petrobras", source="b3")
        Ativo.objects.create(ticker="AAPL", nome="Apple", source="sp500")
        Ativo.objects.create(ticker="XYZ1", nome="Unknown", source="outro")

        invalidar_cache_tickers()
        try:
            n_b3, n_sp500, n_outros = classificar_tickers_por_origem(["PETR4", "AAPL", "XYZ1", "UNKNOWN"])
            self.assertEqual(n_b3, 1)
            self.assertEqual(n_sp500, 1)
            self.assertEqual(n_outros, 2)
        finally:
            invalidar_cache_tickers()


class ResolveMetricsPathTests(TestCase):

    def test_resolve_from_config(self):
        path = _resolve_metrics_path({"metrics": {"path": "/custom/metrics.jsonl"}})
        self.assertEqual(path, "/custom/metrics.jsonl")

    def test_resolve_from_env(self):
        os.environ["PIPELINE_METRICS_PATH"] = "/env/metrics.jsonl"
        try:
            path = _resolve_metrics_path({})
            self.assertEqual(path, "/env/metrics.jsonl")
        finally:
            del os.environ["PIPELINE_METRICS_PATH"]

    def test_resolve_default(self):
        os.environ.pop("PIPELINE_METRICS_PATH", None)
        path = _resolve_metrics_path({})
        self.assertEqual(path, "pipeline_metrics.jsonl")
