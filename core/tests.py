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


class SetoresTests(TestCase):
    def test_classifica_ativos_conhecidos(self):
        from core.intelligent_motor.setores import setor_do_ativo

        self.assertEqual(
            setor_do_ativo("PETR4", "Petrobras petróleo energia combustíveis"),
            "Petróleo e Gás",
        )
        self.assertEqual(
            setor_do_ativo("VALE3", "Vale mineração minério de ferro siderurgia"),
            "Mineração e Siderurgia",
        )
        self.assertEqual(
            setor_do_ativo("YDUQ3", "Yduqs educação ensino superior faculdades"),
            "Educação",
        )

    def test_sem_palavra_chave_vai_para_outros(self):
        from core.intelligent_motor.setores import setor_do_ativo

        self.assertEqual(setor_do_ativo("XPTO", "descrição genérica"), "Outros")


class SeedSetoresTests(TestCase):
    def test_preenche_setor_pela_descricao(self):
        Ativo.objects.create(
            ticker="PETR4",
            nome="Petrobras",
            descricao_embedding="petroleo energia combustíveis offshore",
        )
        Ativo.objects.create(
            ticker="ZZZZ",
            nome="Empresa",
            descricao_embedding="",
        )
        call_command("seed_setores", stdout=StringIO())
        self.assertEqual(
            Ativo.objects.get(ticker="PETR4").setor, "Petróleo e Gás"
        )
        self.assertEqual(Ativo.objects.get(ticker="ZZZZ").setor, "Outros")

    def test_force_sobrescreve(self):
        ativo = Ativo.objects.create(
            ticker="ITUB4",
            nome="Itaú Unibanco",
            descricao_embedding="bancos crédito cartões investimentos",
            setor="Errado",
        )
        call_command("seed_setores", stdout=StringIO())
        ativo.refresh_from_db()
        self.assertEqual(ativo.setor, "Errado")
        call_command("seed_setores", "--force", stdout=StringIO())
        ativo.refresh_from_db()
        self.assertIn(ativo.setor, {"Bancos", "Serviços Financeiros"})


class ImportLabelsTests(TestCase):
    def test_importa_colunas_ampliadas(self):
        noticia = make_noticia()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.csv"
            path.write_text(
                "noticia_id,rel_financeira,rel_alerta,setor,urgencia,"
                "tickers_corretos,tickers_faltantes,confianca,sentimento\n"
                f"{noticia.id},1,1,Petróleo e Gás,alta,petr4|PRIO3,VALE3,3,negativo\n",
                encoding="utf-8",
            )
            call_command("import_labels", str(path), stdout=StringIO())

        label = NewsLabel.objects.get(noticia=noticia)
        self.assertTrue(label.relevancia)
        self.assertTrue(label.relevancia_financeira)
        self.assertEqual(label.setor, "Petróleo e Gás")
        self.assertEqual(label.urgencia, "alta")
        self.assertEqual(label.tickers_corretos, ["PETR4", "PRIO3"])
        self.assertEqual(label.tickers_faltantes, ["VALE3"])
        self.assertTrue(label.tickers_anotados)
        self.assertEqual(label.confianca, 3)
        self.assertEqual(label.sentimento, "negativo")

    def test_tickers_nenhum_marca_anotado(self):
        noticia = make_noticia()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.csv"
            path.write_text(
                "noticia_id,tickers_corretos\n"
                f"{noticia.id},NENHUM\n",
                encoding="utf-8",
            )
            call_command("import_labels", str(path), stdout=StringIO())

        label = NewsLabel.objects.get(noticia=noticia)
        self.assertEqual(label.tickers_corretos, [])
        self.assertTrue(label.tickers_anotados)


class BuildAnnotationSampleTests(TestCase):
    def _run_com_classificacoes(self):
        run = ExperimentRun.objects.create(
            nome="amostra", modelo="modelo/fake", total_noticias=6
        )
        # 2 descartadas na Fase 1, 4 mantidas em faixas distintas.
        casos = [
            (False, 1, [], []),
            (False, 0, [], []),
            (True, 1, [], ["PRIO3"]),
            (True, 4, ["PETR4"], ["BRKM5"]),
            (True, 4, [], []),
            (True, 9, ["VALE3"], []),
        ]
        for aprovada, score, encontrados, relacionados in casos:
            n = make_noticia()
            RunClassification.objects.create(
                run=run,
                noticia=n,
                fase1_aprovada=aprovada,
                score_heuristico=score,
                tickers_encontrados=encontrados,
                tickers_relacionados=relacionados,
            )
        return run

    def test_gera_csv_com_candidatos_e_estratos(self):
        run = self._run_com_classificacoes()
        with TemporaryDirectory() as tmp:
            call_command(
                "build_annotation_sample",
                "--run-id",
                run.id,
                "--output",
                tmp,
                "--name",
                "am",
                "--min-explicito",
                "0",
                stdout=StringIO(),
            )
            csv_path = Path(tmp) / "am" / "anotacao.csv"
            self.assertTrue(csv_path.exists())
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 6)
            candidatos = {
                r["noticia_id"]: set(r["candidatos"].split("|"))
                for r in rows
                if r["candidatos"]
            }
            self.assertIn("PETR4", {c for s in candidatos.values() for c in s})
            # União de encontrados + relacionados.
            self.assertIn(
                {"BRKM5", "PETR4"},
                candidatos.values(),
            )
            self.assertTrue((Path(tmp) / "am" / "LEIA-ME.txt").exists())
            self.assertTrue((Path(tmp) / "am" / "diagnostico.csv").exists())


class Fase2MetricsTests(TestCase):
    def test_metricas_por_par(self):
        n1 = make_noticia()
        n2 = make_noticia()
        run = ExperimentRun.objects.create(
            nome="f2", modelo="modelo/fake", total_noticias=2
        )
        NewsLabel.objects.create(
            noticia=n1,
            relevancia=True,
            tickers_anotados=True,
            tickers_corretos=["PETR4"],
            tickers_faltantes=["VALE3"],
        )
        NewsLabel.objects.create(
            noticia=n2,
            relevancia=True,
            tickers_anotados=True,
            tickers_corretos=[],
        )
        RunClassification.objects.create(
            run=run,
            noticia=n1,
            relevancia_binaria=True,
            tickers_relacionados=["PETR4", "BRKM5"],
        )
        RunClassification.objects.create(
            run=run,
            noticia=n2,
            relevancia_binaria=True,
            tickers_relacionados=["PRIO3"],
        )

        metrics = compute_run_metrics(run)
        fase2 = metrics["fase2"]["metricas"]
        # n1: tp=1 (PETR4), fp=1 (BRKM5), fn=1 (VALE3). n2: fp=1 (PRIO3).
        self.assertEqual(fase2["tp"], 1)
        self.assertEqual(fase2["fp"], 2)
        self.assertEqual(fase2["fn"], 1)
        self.assertEqual(metrics["fase2"]["avaliadas"], 2)


class Fase2GatingTests(TestCase):
    """Estratégias A1 (setor) e A2 (setor + lexical) da Fase 2."""

    EMBS = {
        "PETR4": [1.0, 0.0, 0.0],
        "BRKM5": [0.8, 0.6, 0.0],
        "VALE3": [0.6, 0.8, 0.0],
        "DOW": [0.5, 0.866, 0.0],
        "ITUB4": [1.0, 0.0, 0.0],
    }
    SETORES = {
        "PETR4": "Petróleo e Gás",
        "BRKM5": "Químicos e Petroquímica",
        "VALE3": "Mineração e Siderurgia",
        "DOW": "Químicos e Petroquímica",
        "ITUB4": "Bancos",
    }

    def _run(self, fase2, texto, carteira, setores=None):
        from core.intelligent_motor.fase2_tickers import pipeline

        embeddings = {t: self.EMBS[t] for t in carteira}

        class DummyStore:
            def get_matrix(self, tickers):
                return (None, None)

            def get_embeddings(self, tickers):
                return {t: embeddings[t] for t in tickers if t in embeddings}

        noticia = {
            "id": 1,
            "titulo": texto,
            "descricao": "",
            "conteudo": "",
            "embedding_noticia": [1.0, 0.0, 0.0],
        }
        with patch.object(
            pipeline, "get_asset_embedding_store", return_value=DummyStore()
        ):
            return pipeline.relacionar_tickers(
                noticia,
                carteira,
                config={"fase2": fase2},
                setores_ativos=setores if setores is not None else {},
            )

    def test_a0_baseline_traz_vizinhos_espurios(self):
        resultado = self._run(
            {"threshold_similaridade": 0.35, "estrategia": "similaridade"},
            "Petrobras anuncia resultados",
            ["PETR4", "BRKM5", "VALE3", "DOW"],
        )
        self.assertIn("BRKM5", resultado)
        self.assertIn("VALE3", resultado)
        self.assertIn("DOW", resultado)

    def test_a1_gating_por_setor_remove_espurios(self):
        resultado = self._run(
            {"threshold_similaridade": 0.35, "estrategia": "similaridade_setor"},
            "Petrobras PETR4 amplia produção de petróleo",
            ["PETR4", "BRKM5", "VALE3", "DOW"],
            self.SETORES,
        )
        self.assertEqual(resultado, ["PETR4"])

    def test_a1_sem_setor_detectado_cai_para_todos(self):
        resultado = self._run(
            {"threshold_similaridade": 0.35, "estrategia": "similaridade_setor"},
            "Notícia genérica sobre o dia",
            ["PETR4", "BRKM5", "VALE3", "DOW"],
            self.SETORES,
        )
        self.assertEqual(len(resultado), 4)

    def test_a2_forca_ticker_citado_fora_do_setor(self):
        fase2 = {
            "threshold_similaridade": 0.35,
            "estrategia": "similaridade_setor_lexical",
            "peso_lexical": 0.1,
        }
        texto = "Itaú ITUB4 eleva aposta e cita PETR4"
        carteira = ["ITUB4", "PETR4", "BRKM5"]
        a1 = self._run({**fase2, "estrategia": "similaridade_setor"}, texto, carteira, self.SETORES)
        a2 = self._run(fase2, texto, carteira, self.SETORES)
        self.assertNotIn("PETR4", a1)  # setor detectado (Bancos) excluiria PETR4
        self.assertIn("PETR4", a2)  # ...mas o guarda lexical mantém

    def test_top_k_limita_resultados(self):
        resultado = self._run(
            {
                "threshold_similaridade": 0.35,
                "estrategia": "similaridade",
                "top_k": 2,
            },
            "Petrobras anuncia resultados",
            ["PETR4", "BRKM5", "VALE3", "DOW"],
        )
        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0], "PETR4")

    def test_funcoes_puras_do_gating(self):
        from core.intelligent_motor.fase2_tickers.gating import (
            aplicar_estrategia,
            filtrar_por_setor,
            tickers_lexicais,
        )

        noticia = {"titulo": "Petrobras PETR4", "descricao": "", "conteudo": ""}
        self.assertEqual(tickers_lexicais(noticia), ["PETR4"])
        self.assertEqual(
            filtrar_por_setor(
                ["PETR4", "VALE3", "XPTO"],
                {"PETR4": "Petróleo e Gás", "VALE3": "Mineração e Siderurgia"},
                {"Petróleo e Gás"},
            ),
            ["PETR4", "XPTO"],  # XPTO sem setor = curinga
        )
        self.assertEqual(
            aplicar_estrategia("similaridade", ["PETR4", "VALE3"], noticia, {}),
            ["PETR4", "VALE3"],
        )
