from __future__ import annotations

import importlib.util
import io
import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.intelligent_motor.fase1_global_filter.embedding_generator import (
    EmbeddingGenerator,
)
from core.models import Noticia
from pipeline_lab.models import (
    AssetEmbedding,
    ExperimentRun,
    LabModel,
    RunClassification,
)
from pipeline_lab.services.model_registry import (
    clear_asset_embeddings,
    delete_local_model,
    install_archive,
    validate_hf_name,
    validate_local_name,
)


def _zip_bytes(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buffer.getvalue()


class ModelRegistryTests(TestCase):
    def test_validate_local_name_slug(self):
        self.assertEqual(validate_local_name("Meu Modelo!"), "Meu-Modelo")
        sanitizado = validate_local_name("../../etc/passwd")
        self.assertNotIn("/", sanitizado)
        self.assertNotIn("..", sanitizado)
        with self.assertRaises(ValidationError):
            validate_local_name("...")

    def test_validate_hf_name(self):
        self.assertEqual(validate_hf_name("BAAI/bge-m3"), "BAAI/bge-m3")
        with self.assertRaises(ValidationError):
            validate_hf_name("sem-namespace")

    def test_install_archive_extrai_e_registra(self):
        with TemporaryDirectory() as tmp:
            with override_settings(LAB_MODELS_DIR=Path(tmp)):
                upload = SimpleUploadedFile(
                    "modelo.zip",
                    _zip_bytes(
                        {
                            "modelo/config.json": "{}",
                            "modelo/model.safetensors": "pesos",
                        }
                    ),
                    content_type="application/zip",
                )
                model = install_archive(upload, nome="meu-modelo")
                self.assertEqual(model.nome, "meu-modelo")
                self.assertTrue((Path(tmp) / "meu-modelo" / "config.json").exists())
                self.assertEqual(LabModel.objects.count(), 1)

    def test_install_archive_rejeita_caminho_inseguro(self):
        with TemporaryDirectory() as tmp:
            with override_settings(LAB_MODELS_DIR=Path(tmp)):
                upload = SimpleUploadedFile(
                    "malicioso.zip",
                    _zip_bytes({"../evil.txt": "x", "config.json": "{}"}),
                    content_type="application/zip",
                )
                with self.assertRaises(ValidationError):
                    install_archive(upload, nome="malicioso")

    def test_install_archive_rejeita_zip_sem_modelo(self):
        with TemporaryDirectory() as tmp:
            with override_settings(LAB_MODELS_DIR=Path(tmp)):
                upload = SimpleUploadedFile(
                    "qualquer.zip",
                    _zip_bytes({"leiame.txt": "não é modelo"}),
                    content_type="application/zip",
                )
                with self.assertRaises(ValidationError):
                    install_archive(upload, nome="qualquer")

    def test_install_archive_sem_sobrescrever_falha(self):
        with TemporaryDirectory() as tmp:
            with override_settings(LAB_MODELS_DIR=Path(tmp)):
                conteudo = _zip_bytes({"config.json": "{}"})
                install_archive(
                    SimpleUploadedFile("a.zip", conteudo), nome="dup"
                )
                with self.assertRaises(ValidationError):
                    install_archive(
                        SimpleUploadedFile("a.zip", conteudo), nome="dup"
                    )

    def test_delete_local_model_remove_pasta(self):
        with TemporaryDirectory() as tmp:
            with override_settings(LAB_MODELS_DIR=Path(tmp)):
                upload = SimpleUploadedFile(
                    "modelo.zip",
                    _zip_bytes({"config.json": "{}", "model.safetensors": "x"}),
                    content_type="application/zip",
                )
                model = install_archive(upload, nome="temp")
                self.assertTrue((Path(tmp) / "temp").exists())
                delete_local_model(model)
                self.assertFalse((Path(tmp) / "temp").exists())
                self.assertFalse(LabModel.objects.exists())

    def test_clear_asset_embeddings(self):
        model = LabModel.objects.create(nome="meu-modelo", origem=LabModel.ORIGEM_LOCAL)
        AssetEmbedding.objects.create(
            modelo="meu-modelo", ticker="PETR4", embedding=[0.1], dimensao=1
        )
        total = clear_asset_embeddings(model)
        self.assertEqual(total, 1)
        self.assertFalse(AssetEmbedding.objects.exists())


class DeviceTests(TestCase):
    def test_resolve_device_normaliza(self):
        self.assertEqual(EmbeddingGenerator.resolve_device("cpu"), "cpu")
        self.assertEqual(EmbeddingGenerator.resolve_device("CUDA:0"), "cuda:0")
        self.assertEqual(EmbeddingGenerator.resolve_device(""), "cpu")


class ExportOnlyRunTests(TestCase):
    def test_only_run_exige_run_id(self):
        with self.assertRaises(CommandError):
            call_command("export_dataset", only_run=True)

    def test_only_run_filtra_noticias_da_execucao(self):
        from django.utils import timezone

        now = timezone.now()
        dentro = Noticia.objects.create(
            link="https://example.com/dentro",
            titulo="Dentro",
            conteudo="conteudo",
            publicado_em=now,
        )
        fora = Noticia.objects.create(
            link="https://example.com/fora",
            titulo="Fora",
            conteudo="conteudo",
            publicado_em=now,
        )
        run = ExperimentRun.objects.create(modelo="modelo-teste", total_noticias=1)
        RunClassification.objects.create(run=run, noticia=dentro)

        with TemporaryDirectory() as tmp:
            call_command(
                "export_dataset",
                output=tmp,
                name="saida",
                run_id=run.id,
                only_run=True,
                sample_size=10,
            )
            destino = Path(tmp) / "saida"
            linhas = (destino / "noticias.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(linhas), 1)
            registro = json.loads(linhas[0])
            self.assertEqual(registro["id"], dentro.id)
            self.assertIsNotNone(registro["run"])
            self.assertNotEqual(registro["id"], fora.id)


class ModelsPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "staff", password="senha-teste", is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_models_page_requer_staff_e_renderiza(self):
        response = self.client.get(reverse("pipeline_lab_models"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Catálogo")

    def test_home_renderiza_seletor_de_device(self):
        response = self.client.get(reverse("pipeline_lab_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="device"')


class RunParamsTests(TestCase):
    def test_defaults_refletem_config(self):
        from pipeline_lab.services import run_params

        padroes = run_params.defaults()
        self.assertIn("threshold_relevancia", padroes["fase1"])
        self.assertIn("threshold_similaridade", padroes["fase2"])
        self.assertEqual(len(padroes["fase3"]["pesos"]), len(run_params.PESOS_FASE3))
        self.assertIn("score_aprovacao_direta", padroes["fase4"])

    def test_effective_faz_merge_sem_mutar_defaults(self):
        from pipeline_lab.services.run_params import defaults, effective

        base_rel = defaults()["fase1"]["threshold_relevancia"]
        eff = effective({"fase1": {"threshold_relevancia": base_rel + 0.1}})
        self.assertAlmostEqual(eff["fase1"]["threshold_relevancia"], base_rel + 0.1)
        # O default global precisa continuar intacto.
        self.assertAlmostEqual(defaults()["fase1"]["threshold_relevancia"], base_rel)

    def test_build_overrides_vazio_sem_diferencas(self):
        from pipeline_lab.services.run_params import build_overrides

        self.assertEqual(build_overrides({}), {})

    def test_build_overrides_le_valores_do_formulario(self):
        from pipeline_lab.services.run_params import build_overrides

        overrides = build_overrides(
            {
                "fase1_threshold": "0,55",
                "fase3_ticker_explicito": "9",
                "fase4_aprovacao": "8",
            }
        )
        self.assertAlmostEqual(overrides["fase1"]["threshold_relevancia"], 0.55)
        self.assertEqual(overrides["fase3"]["pesos"]["ticker_explicito"], 9)
        self.assertEqual(overrides["fase4"]["score_aprovacao_direta"], 8)

    def test_build_overrides_com_centroides(self):
        from pipeline_lab.services.run_params import build_overrides

        overrides = build_overrides({"fase1_centroides": "um\n  dois  \n"})
        self.assertEqual(
            overrides["fase1"]["centroides_referencia"], ["um", "dois"]
        )

    def test_validate_rejeita_cortes_incoerentes(self):
        from pipeline_lab.services.run_params import validate_overrides

        with self.assertRaises(ValidationError):
            validate_overrides(
                {
                    "fase4": {
                        "score_rejeicao_direta": 5,
                        "faixa_llm": {"minimo": 3},
                    }
                }
            )

    def test_validate_rejeita_threshold_fora_da_faixa(self):
        from pipeline_lab.services.run_params import validate_overrides

        with self.assertRaises(ValidationError):
            validate_overrides({"fase1": {"threshold_relevancia": 1.5}})


class CreateRunOverridesTests(TestCase):
    def test_create_run_persiste_overrides_e_efetivo(self):
        from pipeline_lab.services.experiments import create_run

        run = create_run(
            modelo="modelo-teste",
            overrides={"fase1": {"threshold_relevancia": 0.55}},
        )
        self.assertEqual(
            run.config["overrides"], {"fase1": {"threshold_relevancia": 0.55}}
        )
        self.assertAlmostEqual(
            run.config["efetivo"]["fase1"]["threshold_relevancia"], 0.55
        )
        # Sem override explícito, o valor do config.yaml permanece.
        from pipeline_lab.services.run_params import defaults

        self.assertAlmostEqual(
            run.config["efetivo"]["fase2"]["threshold_similaridade"],
            defaults()["fase2"]["threshold_similaridade"],
        )

    def test_create_run_rejeita_overrides_invalidos(self):
        from pipeline_lab.services.experiments import create_run

        with self.assertRaises(ValidationError):
            create_run(
                modelo="modelo-teste",
                overrides={"fase1": {"threshold_relevancia": 2.0}},
            )


class RunDetailParamsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "staff3", password="senha-teste", is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.run = ExperimentRun.objects.create(
            modelo="modelo-teste",
            config={
                "efetivo": {
                    "fase1": {"threshold_relevancia": 0.55},
                    "fase2": {"threshold_similaridade": 0.35},
                },
                "overrides": {"fase1": {"threshold_relevancia": 0.55}},
            },
        )

    def test_run_detail_mostra_parametros_e_graficos(self):
        response = self.client.get(
            reverse("pipeline_lab_run_detail", args=[self.run.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Parâmetros efetivos")
        self.assertContains(response, "Gráficos do artigo")

    def test_home_mostra_painel_avancado(self):
        response = self.client.get(reverse("pipeline_lab_home"))
        self.assertContains(response, "Parâmetros avançados")
        self.assertContains(response, 'name="fase3_ticker_explicito"')


_HAS_CHARTS = bool(importlib.util.find_spec("pandas")) and bool(
    importlib.util.find_spec("matplotlib")
)


@unittest.skipUnless(_HAS_CHARTS, "pandas/matplotlib ausentes")
class GenerateRunChartsTests(TestCase):
    def test_gera_artefatos_so_da_execucao(self):
        run = ExperimentRun.objects.create(
            modelo="modelo-teste",
            status=ExperimentRun.STATUS_DONE,
            total_noticias=2,
        )
        base = {
            "n_tickers_b3": 1,
            "n_tickers_sp500": 0,
            "n_tickers_outros": 0,
            "sentimento": "positivo",
            "impacto": "alto",
            "categoria": "resultados",
            "fase1_tempo_s": 0.1,
            "fase2_tempo_s": 0.1,
            "fase3_tempo_s": 0.1,
            "fase4_tempo_s": 0.1,
            "fase5_tempo_s": 0.1,
            "t_total_s": 0.5,
        }
        linhas = [
            dict(base, run_id=run.id, noticia_id=1, fase1_aprovada=True,
                 relevancia_global=0.9, score_heuristico=5,
                 provider_fase4="openai", relevancia_binaria=1),
            dict(base, run_id=run.id, noticia_id=2, fase1_aprovada=False,
                 relevancia_global=0.1, score_heuristico=None,
                 provider_fase4=None, relevancia_binaria=0),
            dict(base, run_id=999, noticia_id=3, fase1_aprovada=True,
                 relevancia_global=0.9, score_heuristico=5,
                 provider_fase4="bypass", relevancia_binaria=1),
        ]
        with TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.jsonl"
            metrics_path.write_text(
                "\n".join(json.dumps(linha) for linha in linhas),
                encoding="utf-8",
            )
            output = Path(tmp) / "out"
            call_command(
                "generate_run_charts",
                run_id=run.id,
                metrics_path=str(metrics_path),
                output=str(output),
                verbosity=0,
            )
            self.assertTrue((output / "metricas.csv").exists())
            self.assertTrue((output / "resumo.txt").exists())
            self.assertTrue((output / "fig_score_heuristico.png").exists())
            # A linha do run 999 não pode entrar nas métricas desta execução.
            conteudo = (output / "metricas.csv").read_text(encoding="utf-8")
            self.assertNotIn("999", conteudo)
