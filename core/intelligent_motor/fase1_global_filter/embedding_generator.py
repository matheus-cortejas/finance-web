from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml


class EmbeddingGenerator:
    """Carrega e mantém um modelo de embeddings por nome.

    Diferente da versão anterior (singleton global), aqui cada modelo tem sua
    própria instância. Isso permite comparar modelos de dimensões diferentes
    sem reiniciar o processo.
    """

    _instances: Dict[str, "EmbeddingGenerator"] = {}
    _lock = threading.Lock()

    def __init__(self, model_name: str, device: Optional[str] = None):
        self.model_name = model_name
        self.model_key = hashlib.sha256(model_name.encode("utf-8")).hexdigest()[:16]
        self.device = self.resolve_device(device or self._default_device())
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name, device=self.device)
        except Exception as exc:
            raise RuntimeError(
                f"Falha ao carregar o modelo de embeddings '{model_name}': {exc}"
            ) from exc

        try:
            get_dimension = getattr(
                self._model,
                "get_embedding_dimension",
                None,
            ) or getattr(self._model, "get_sentence_embedding_dimension")
            self.dimension = int(get_dimension())
        except Exception:
            self.dimension = None

    @staticmethod
    def resolve_device(device: Optional[str] = None) -> str:
        """Normaliza o device de execução.

        Aceita ``None``, ``auto``, ``cpu``, ``cuda`` ou ``cuda:0``. Em ``auto``
        escolhe a GPU apenas quando o PyTorch enxerga uma.
        """
        value = (device or "").strip().lower()
        if value in {"", "auto", "default"}:
            try:
                import torch

                return "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                return "cpu"
        return value

    @staticmethod
    def _default_device() -> str:
        try:
            from django.conf import settings

            return getattr(settings, "EMBEDDING_DEVICE", "cpu")
        except Exception:
            return os.environ.get("EMBEDDING_DEVICE", "cpu")

    @classmethod
    def resolve_model_name(
        cls,
        model_name: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> str:
        if model_name is None and config is not None:
            model_name = config.get("fase1", {}).get("modelo")

        if model_name is None:
            model_name = os.environ.get("FASE1_MODELO")

        if model_name is None:
            model_name = cls._load_model_name_from_file()

        if not model_name:
            raise RuntimeError(
                "Não foi possível determinar o nome do modelo de embeddings"
            )

        model_name = str(model_name).strip()
        path = Path(model_name).expanduser()
        if not path.is_absolute():
            cfg_dir = Path(__file__).parent.parent
            candidates = [
                cfg_dir / model_name,
                cfg_dir / "models" / model_name,
                cfg_dir / "models" / path.name,
            ]
            for candidate in candidates:
                if candidate.exists():
                    return str(candidate.resolve())

        return model_name

    @classmethod
    def instance(
        cls,
        model_name: Optional[str] = None,
        config: Optional[Dict] = None,
        device: Optional[str] = None,
    ) -> "EmbeddingGenerator":
        resolved = cls.resolve_model_name(model_name=model_name, config=config)
        effective_device = cls.resolve_device(device or cls._default_device())
        cache_key = f"{resolved}::{effective_device}"

        with cls._lock:
            existing = cls._instances.get(cache_key)
            if existing is not None:
                return existing
            instance = cls(resolved, device=effective_device)
            cls._instances[cache_key] = instance
            return instance

    @classmethod
    def reset(cls) -> None:
        """Descarta os modelos carregados (usado em testes)."""
        with cls._lock:
            cls._instances.clear()

    @staticmethod
    def _load_model_name_from_file() -> Optional[str]:
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        try:
            with cfg_path.open("r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                return cfg.get("fase1", {}).get("modelo")
        except Exception:
            return None

    def gerar(self, texto: str) -> List[float]:
        if not texto:
            raise ValueError("Texto vazio fornecido para geração de embedding")

        emb = self._model.encode(texto, normalize_embeddings=True)
        try:
            vec = emb.tolist()
        except Exception:
            vec = [float(x) for x in emb]

        if self.dimension is None:
            self.dimension = len(vec)
        return vec

    def gerar_lote(
        self,
        textos: Iterable[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ) -> List[List[float]]:
        textos = [texto if texto else " " for texto in textos]
        if not textos:
            return []

        embeddings = self._model.encode(
            textos,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
        )
        try:
            result = embeddings.tolist()
        except Exception:
            result = [[float(x) for x in row] for row in embeddings]

        if self.dimension is None and result:
            self.dimension = len(result[0])
        return result


__all__ = ["EmbeddingGenerator"]
