from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase

from core.intelligent_motor.fase2_tickers.asset_embedding_store import (
    AssetEmbeddingStore,
    get_asset_embedding_store,
    reset_asset_embedding_stores,
)
from core.intelligent_motor.fase4_llm_gate.pipeline import classificar_noticia
from core.intelligent_motor.fase5_rich_classification.pipeline import (
    classificar_noticia_rica,
)
from core.models import Ativo, FonteRSS, Noticia
from core.services.collector_service import (
    collect_feed,
    normalize_link,
    sync_feeds_from_file,
)
from pipeline_lab.models import (
    AssetEmbedding,
    ExperimentRun,
    NewsLabel,
    RunClassification,
)
from pipeline_lab.services.experiments import build_noticias_queryset, create_run
from pipeline_lab.services.metrics import compute_run_metrics


def make_noticia(**overrides) -> Noticia:
    now = datetime.now(timezone.utc)
    data = {
        "link": f"https://example.com/{uuid4().hex}",
        "titulo": "Notícia de teste",
        "descricao": "Descrição de teste",
        "conteudo": "Conteúdo de teste",
        "publicado_em": now,
        "coletado_em": now,
        "feed_url": "https://example.com/feed/",
    }
    data.update(overrides)
    return Noticia.objects.create(**data)


class CollectorServiceTests(TestCase):
    def test_normalize_link_remove_tracking_e_fragmento(self):
        self.assertEqual(
            normalize_link(
                "HTTPS://Example.COM/noticia?utm_source=x&b=1&fbclid=abc#topo"
            ),
            "https://example.com/noticia?b=1",
        )

    def test_collect_feed_persiste_cru_e_deduplica(self):
        now = datetime.now(timezone.utc)
        parser = MagicMock()
        parser.fetch.return_value = {
            "href": "https://feed.test/rss",
            "entries": [
                {
                    "link": "https://example.com/nova?utm_source=feed",
                    "title": "Nova",
                    "description": "Desc",
                    "content": "Conteúdo",
                    "published": now,
                    "raw": {"id": "1"},
                },
                {
                    "link": "https://example.com/antiga",
                    "title": "Antiga",
                    "description": "Desc",
                    "content": "Conteúdo",
                    "published": now - timedelta(days=10),
                    "raw": {"id": "2"},
                },
            ],
        }

        with patch(
            "core.services.collector_service.create_parser",
            return_value=parser,
        ):
            result = collect_feed("https://feed.test/rss", within_days=2)
            self.assertEqual(result.criadas, 1)
            self.assertEqual(result.antigas, 1)

            noticia = Noticia.objects.get()
            self.assertEqual(noticia.link, "https://example.com/nova")
            self.assertIsNotNone(noticia.coletado_em)
            self.assertEqual(noticia.raw_data, {"id": "1"})
            self.assertEqual(noticia.feed_url, "https://feed.test/rss")

            again = collect_feed("https://feed.test/rss", within_days=2)
            self.assertEqual(again.criadas, 0)
            self.assertEqual(again.duplicadas, 1)
            self.assertEqual(Noticia.objects.count(), 1)

    def test_sync_feeds_from_file_e_idempotente(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "rss.txt"
            path.write_text(
                "# comentário\nhttps://a.example/feed/\n\nhttps://b.example/feed/\n",
                encoding="utf-8",
            )

            created, total = sync_feeds_from_file(path)
            self.assertEqual(created, 2)
            self.assertEqual(total, 2)
            self.assertEqual(FonteRSS.objects.count(), 2)

            created_again, _ = sync_feeds_from_file(path)
            self.assertEqual(created_again, 0)
            self.assertEqual(FonteRSS.objects.count(), 2)


class ExportDatasetTests(TestCase):
    def setUp(self):
        self.com_conteudo = make_noticia(
            titulo="Com conteúdo", conteudo="Texto completo"
        )
        self.sem_conteudo = make_noticia(
            titulo="Sem conteúdo", conteudo=""
        )
        self.outra = make_noticia(titulo="Outra", conteudo="Mais texto")
        NewsLabel.objects.create(
            noticia=self.com_conteudo,
            relevancia=True,
            sentimento="positivo",
            impacto="alto",
            categoria="empresa",
            anotador="teste",
        )

    def test_exporta_jsonl_manifest_e_csv(self):
        with TemporaryDirectory() as tmp:
            call_command(
                "export_dataset",
                output=tmp,
                name="ds",
                sample_size=2,
                stdout=StringIO(),
            )
            output = Path(tmp) / "ds"

            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["total_noticias"], 3)
            self.assertEqual(manifest["com_conteudo"], 2)
            self.assertEqual(manifest["com_label"], 1)
            self.assertIn("sha256", manifest["arquivos"]["noticias"])

            lines = (output / "noticias.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(lines), 3)
            first = json.loads(lines[0])
            self.assertIn("classificacao_legada", first)
            self.assertEqual(first["label"]["relevancia"], True)

            with (output / "annotation_sample.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)

    def test_amostra_prioriza_noticias_com_conteudo(self):
        with TemporaryDirectory() as tmp:
            call_command(
                "export_dataset",
                output=tmp,
                name="ds",
                sample_size=1,
                stdout=StringIO(),
            )
            with (Path(tmp) / "ds" / "annotation_sample.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["conteudo"])


class ExperimentServiceTests(TestCase):
    def test_create_run_respeita_limite(self):
        for _ in range(3):
            make_noticia()
        run = create_run(
            modelo="modelo/fake",
            nome="teste",
            limite=2,
            stop_after=1,
            usar_llm=False,
        )
        self.assertEqual(run.status, ExperimentRun.STATUS_PENDING)
        self.assertEqual(run.total_noticias, 2)
        self.assertEqual(run.config["stop_after"], 1)
        self.assertFalse(run.config["usar_llm"])
        self.assertEqual(build_noticias_queryset(run.config).count(), 2)

    def test_claim_pending_run(self):
        from pipeline_lab.services.experiments import claim_pending_run

        run = create_run(modelo="modelo/fake", limite=1, stop_after=1)
        claimed = claim_pending_run(run.id)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.status, ExperimentRun.STATUS_RUNNING)
        self.assertIsNotNone(claimed.iniciado_em)

    def test_compute_metrics_com_labels(self):
        n1 = make_noticia()
        n2 = make_noticia()
        run = ExperimentRun.objects.create(
            nome="métricas",
            modelo="modelo/fake",
            total_noticias=2,
        )
        NewsLabel.objects.create(noticia=n1, relevancia=True)
        NewsLabel.objects.create(noticia=n2, relevancia=False)

        RunClassification.objects.create(
            run=run,
            noticia=n1,
            fase1_aprovada=True,
            relevancia_global=0.9,
            score_heuristico=10,
            relevancia_binaria=True,
        )
        RunClassification.objects.create(
            run=run,
            noticia=n2,
            fase1_aprovada=False,
            relevancia_global=0.1,
            score_heuristico=1,
            relevancia_binaria=False,
        )

        metrics = compute_run_metrics(run)
        self.assertEqual(metrics["labeled_total"], 2)
        self.assertEqual(metrics["fase1"]["metricas"]["f1"], 1.0)
        self.assertEqual(metrics["fase4"]["metricas"]["f1"], 1.0)
        self.assertEqual(
            metrics["score_heuristico"]["best"]["f1"], 1.0
        )
        self.assertEqual(metrics["cobertura"], 1.0)

    def test_compute_metrics_sem_labels(self):
        make_noticia()
        run = ExperimentRun.objects.create(
            nome="sem labels",
            modelo="modelo/fake",
            total_noticias=1,
        )
        metrics = compute_run_metrics(run)
        self.assertEqual(metrics["labeled_total"], 0)
        self.assertEqual(metrics["fase1"]["metricas"]["total"], 0)


class AssetEmbeddingStoreTests(TestCase):
    def tearDown(self):
        reset_asset_embedding_stores()
        AssetEmbedding.objects.filter(modelo="modelo/teste").delete()

    def test_save_e_matrix(self):
        store = AssetEmbeddingStore(model_name="modelo/teste")
        store.save("AAA", [1.0, 0.0, 0.0], description="Ativo A")
        store.save("BBB", [0.0, 1.0, 0.0], description="Ativo B")

        present, matrix = store.get_matrix(["AAA", "BBB"])
        self.assertEqual(present, ["AAA", "BBB"])
        self.assertEqual(matrix.shape, (2, 3))

        vector = matrix[0]
        self.assertAlmostEqual(float(vector[0]), 1.0, places=5)
        self.assertAlmostEqual(float(vector[1]), 0.0, places=5)

        self.assertIs(
            get_asset_embedding_store("modelo/teste"),
            get_asset_embedding_store("modelo/teste"),
        )


class NoLLMPipelineTests(TestCase):
    def test_fase4_sem_llm_usa_fallback(self):
        result = classificar_noticia(
            {"score_heuristico": 4, "titulo": "Teste"},
            config={
                "fase4": {
                    "faixa_llm": {"minimo": 3, "maximo": 6},
                    "fallback_resultado": 1,
                }
            },
            usar_llm=False,
        )
        self.assertEqual(result["relevancia_binaria"], 1)
        self.assertEqual(result["provider_fase4"], "heuristica")
        self.assertEqual(result["status_fase4"], "sem_llm")

    def test_fase5_sem_llm_usa_fallback_heuristico(self):
        result = classificar_noticia_rica(
            {
                "relevancia_binaria": 1,
                "titulo": "Empresa anuncia lucro",
                "descricao": "Resultado positivo",
                "conteudo": "",
                "score_heuristico": 4,
                "tickers_relacionados": [],
            },
            config={"fase5": {}},
            usar_llm=False,
        )
        self.assertEqual(result["provider_fase5"], "heuristica")
        self.assertTrue(result["fallback_fase5"])
        self.assertIn(result["sentimento"], {"positivo", "negativo", "neutro"})


class PipelineLabWebTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", password="x", is_staff=True
        )
        self.user = User.objects.create_user(username="user", password="x")

    def test_home_exige_staff(self):
        client = Client()
        client.force_login(self.user)
        response = client.get("/lab/")
        self.assertEqual(response.status_code, 302)

        client.force_login(self.staff)
        response = client.get("/lab/")
        self.assertEqual(response.status_code, 200)

    def test_criar_e_cancelar_run_pela_web(self):
        make_noticia()
        client = Client()
        client.force_login(self.staff)

        response = client.post(
            "/lab/runs/create/",
            {
                "modelo": "modelo/fake",
                "nome": "web",
                "limite": "1",
                "stop_after": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        run = ExperimentRun.objects.latest("id")
        self.assertEqual(run.status, ExperimentRun.STATUS_PENDING)

        response = client.post(f"/lab/runs/{run.id}/cancel/")
        self.assertEqual(response.status_code, 302)
        run.refresh_from_db()
        self.assertEqual(run.status, ExperimentRun.STATUS_CANCELLED)
