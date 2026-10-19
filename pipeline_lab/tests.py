from __future__ import annotations

import io
import json
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
