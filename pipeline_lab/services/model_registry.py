from __future__ import annotations

import hashlib
import os
import re
import shutil
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from pipeline_lab.models import AssetEmbedding, LabModel

# Arquivos que indicam que a pasta é um modelo do sentence-transformers.
MODEL_FILE_HINTS = {
    "config.json",
    "modules.json",
    "config_sentence_transformers.json",
    "sentence_bert_config.json",
    "pytorch_model.bin",
    "model.safetensors",
    "tf_model.h5",
    "model.onnx",
}

LOCAL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,120}$")
HF_NAME_RE = re.compile(r"^[A-Za-z0-9._\-]+/[A-Za-z0-9._\-]+$")

MAX_ARCHIVE_MEMBERS = 50_000


# --------------------------------------------------------------------- helpers


def models_root() -> Path:
    root = Path(
        getattr(
            settings,
            "LAB_MODELS_DIR",
            Path(settings.BASE_DIR) / "core" / "intelligent_motor" / "models",
        )
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def max_upload_bytes() -> int:
    return int(getattr(settings, "LAB_MODEL_UPLOAD_MAX_MB", 4096)) * 1024 * 1024


def slug_local_name(value: str) -> str:
    name = re.sub(r"\s+", "-", (value or "").strip())
    name = re.sub(r"[^A-Za-z0-9._\-]+", "-", name).strip("-_.")
    return name[:120]


def validate_local_name(name: str) -> str:
    slug = slug_local_name(name)
    if not slug or not LOCAL_NAME_RE.match(slug):
        raise ValidationError(
            "Nome inválido. Use letras, números, ponto, hífen ou underline."
        )
    return slug


def validate_hf_name(name: str) -> str:
    value = (name or "").strip()
    if not HF_NAME_RE.match(value):
        raise ValidationError(
            "ID do Hugging Face inválido. Use o formato 'org/modelo'."
        )
    return value


def local_path_for(model: LabModel) -> Optional[Path]:
    if not model.e_local:
        return None
    return models_root() / model.nome


def local_model_exists(model: LabModel) -> bool:
    path = local_path_for(model)
    return bool(path and path.is_dir())


# ------------------------------------------------------------------ extraction


def _assert_safe_member(name: str) -> None:
    if not name:
        return
    if "\\" in name:
        raise ValidationError(f"Caminho inválido no arquivo compactado: {name!r}")
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValidationError(f"Caminho inseguro no arquivo compactado: {name!r}")
    if re.match(r"^[A-Za-z]:", name):
        raise ValidationError(f"Caminho absoluto no arquivo compactado: {name!r}")


def _extract_zip(archive: Path, dest: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise ValidationError("Arquivo compactado com arquivos demais.")
        for info in infos:
            _assert_safe_member(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValidationError(
                    f"Links simbólicos não são permitidos: {info.filename!r}"
                )
        zf.extractall(dest)


def _extract_tar(archive: Path, dest: Path) -> None:
    with tarfile.open(archive) as tf:
        members = tf.getmembers()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise ValidationError("Arquivo compactado com arquivos demais.")
        for member in members:
            _assert_safe_member(member.name)
            if member.issym() or member.islnk():
                raise ValidationError(
                    f"Links não são permitidos: {member.name!r}"
                )
        tf.extractall(dest, filter="data")


def _detect_kind(filename: str) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".zip"):
        return "zip"
    if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "tar"
    raise ValidationError("Envie um arquivo .zip, .tar.gz ou .tgz.")


def _find_model_dir(extract_dir: Path) -> Path:
    entries = [
        item for item in extract_dir.iterdir() if item.name not in {"__MACOSX"}
    ]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extract_dir


def _looks_like_model(path: Path) -> bool:
    try:
        names = {item.name for item in path.iterdir()}
    except OSError:
        return False
    return bool(names & MODEL_FILE_HINTS)


# --------------------------------------------------------------------- actions


def install_archive(
    uploaded_file,
    *,
    nome: str = "",
    descricao: str = "",
    user=None,
    sobrescrever: bool = False,
) -> LabModel:
    """Extrai e instala um modelo local enviado pela interface."""
    if uploaded_file is None:
        raise ValidationError("Selecione um arquivo compactado do modelo.")

    size = getattr(uploaded_file, "size", 0) or 0
    limit = max_upload_bytes()
    if size and size > limit:
        raise ValidationError(
            f"Arquivo de {size / 1024 / 1024:.0f} MB acima do limite de "
            f"{limit / 1024 / 1024:.0f} MB. Ajuste LAB_MODEL_UPLOAD_MAX_MB."
        )

    kind = _detect_kind(uploaded_file.name)
    raw_name = nome or Path(uploaded_file.name).name
    for suffix in (".tar.gz", ".tgz", ".zip"):
        if raw_name.lower().endswith(suffix):
            raw_name = raw_name[: -len(suffix)]
            break
    slug = validate_local_name(raw_name)

    root = models_root()
    workdir = Path(tempfile.mkdtemp(prefix=".lab-upload-", dir=root))
    try:
        archive = workdir / f"model.{ 'tar.gz' if kind == 'tar' else 'zip' }"
        with archive.open("wb") as handle:
            for chunk in uploaded_file.chunks():
                handle.write(chunk)

        extract_dir = workdir / "extract"
        extract_dir.mkdir()
        if kind == "zip":
            _extract_zip(archive, extract_dir)
        else:
            _extract_tar(archive, extract_dir)

        model_dir = _find_model_dir(extract_dir)
        if not _looks_like_model(model_dir):
            raise ValidationError(
                "O arquivo não parece um modelo do sentence-transformers "
                "(esperado config.json, modules.json, model.safetensors etc.)."
            )

        target = root / slug
        backup: Optional[Path] = None
        if target.exists():
            if not sobrescrever:
                raise ValidationError(
                    f"Já existe o modelo local '{slug}'. Marque 'sobrescrever' "
                    "ou escolha outro nome."
                )
            backup = root / f".lab-old-{slug}-{int(time.time())}"
            shutil.move(str(target), str(backup))

        try:
            shutil.move(str(model_dir), str(target))
        except Exception:
            if backup is not None and backup.exists():
                shutil.move(str(backup), str(target))
            raise
        finally:
            if backup is not None and backup.exists():
                shutil.rmtree(backup, ignore_errors=True)

        model, _ = LabModel.objects.update_or_create(
            nome=slug,
            defaults={
                "origem": LabModel.ORIGEM_UPLOAD,
                "descricao": descricao or "",
                "dimensao": None,
                "erro_teste": "",
                "testado_em": None,
                "ativo": True,
                "criado_por": user if getattr(user, "pk", None) else None,
            },
        )
        # Pesos novos invalidam embeddings antigos com o mesmo nome.
        clear_asset_embeddings(model)
        return model
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def register_huggingface(nome: str, *, descricao: str = "", user=None) -> LabModel:
    value = validate_hf_name(nome)
    model, _ = LabModel.objects.update_or_create(
        nome=value,
        defaults={
            "origem": LabModel.ORIGEM_HUGGINGFACE,
            "descricao": descricao or "",
            "ativo": True,
            "criado_por": user if getattr(user, "pk", None) else None,
        },
    )
    return model


def scan_local_models(*, user=None) -> int:
    """Registra no catálogo as pastas de modelo que já existem no disco."""
    root = models_root()
    criados = 0
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        _, created = LabModel.objects.get_or_create(
            nome=child.name,
            defaults={
                "origem": LabModel.ORIGEM_LOCAL,
                "ativo": True,
                "criado_por": user if getattr(user, "pk", None) else None,
            },
        )
        if created:
            criados += 1
    return criados


def test_model_load(model: LabModel, *, device: Optional[str] = None) -> None:
    """Carrega o modelo para validar e registrar a dimensão real."""
    from core.intelligent_motor.fase1_global_filter.embedding_generator import (
        EmbeddingGenerator,
    )

    try:
        generator = EmbeddingGenerator.instance(
            model_name=model.nome,
            device=device,
        )
        model.dimensao = generator.dimension
        model.erro_teste = ""
        model.ativo = True
    except Exception as exc:  # noqa: BLE001 - mostrado ao usuário
        model.erro_teste = str(exc)[:4000]
    model.testado_em = timezone.now()
    model.save(
        update_fields=[
            "dimensao",
            "erro_teste",
            "ativo",
            "testado_em",
            "atualizado_em",
        ]
    )


def clear_asset_embeddings(model: LabModel) -> int:
    """Apaga os embeddings de ativos gerados para este modelo."""
    alvos = {model.nome}
    try:
        from core.intelligent_motor.fase1_global_filter.embedding_generator import (
            EmbeddingGenerator,
        )

        alvos.add(EmbeddingGenerator.resolve_model_name(model.nome))
    except Exception:
        pass

    total = AssetEmbedding.objects.filter(modelo__in=list(alvos)).count()
    AssetEmbedding.objects.filter(modelo__in=list(alvos)).delete()

    # Fallback em SQLite, usado quando o Django não está disponível.
    base = os.environ.get("ASSET_EMBEDDINGS_DIR")
    if not base:
        fase1_path = os.environ.get("FASE1_SQLITE_PATH")
        if fase1_path:
            base = str(Path(fase1_path).parent)
    if base:
        for alvo in alvos:
            key = hashlib.sha256(alvo.encode("utf-8")).hexdigest()[:16]
            candidate = Path(base) / f"asset_embeddings_{key}.sqlite"
            if candidate.exists():
                candidate.unlink()
    return total


def delete_local_model(model: LabModel, *, apagar_embeddings: bool = True) -> None:
    if not model.e_local:
        raise ValidationError("Só é possível excluir modelos locais.")
    root = models_root().resolve()
    target = (root / model.nome).resolve()
    if target == root or root not in target.parents:
        raise ValidationError("Caminho fora da pasta de modelos.")
    if target.exists():
        shutil.rmtree(target)
    if apagar_embeddings:
        clear_asset_embeddings(model)
    model.delete()
