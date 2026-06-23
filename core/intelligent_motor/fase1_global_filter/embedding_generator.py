# embedding_generator.py
import os
import threading
from pathlib import Path
from typing import Optional, Dict, List

import yaml


class EmbeddingGenerator:
    _instance = None
    _lock = threading.Lock()

    def __init__(self, model_name: str):
        self.model_name = model_name
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
        except Exception as exc:
            raise RuntimeError(f"Failed to load embedding model '{model_name}': {exc}")

    @classmethod
    def instance(cls, model_name: Optional[str] = None, config: Optional[Dict] = None) -> "EmbeddingGenerator":
        if cls._instance is not None:
            return cls._instance

        with cls._lock:
            if cls._instance is not None:
                return cls._instance

            # 1. Argumento direto
            if model_name is None and config is not None:
                model_name = config.get("fase1", {}).get("modelo")

            # Resolve caminho relativo baseado no diretório do config.yaml
            if model_name and not os.path.isabs(model_name):
                # O config.yaml está em core/intelligent_motor/
                cfg_dir = Path(__file__).parent.parent
                model_name = str((cfg_dir / model_name).resolve())

            # 2. Variável de ambiente
            if model_name is None:
                model_name = os.environ.get("FASE1_MODELO")

            # 3. Arquivo local (fallback)
            if model_name is None:
                model_name = cls._load_model_name_from_file()
                if model_name and not os.path.isabs(model_name):
                    cfg_dir = Path(__file__).parent.parent
                    model_name = str((cfg_dir / model_name).resolve())

            if model_name is None:
                raise RuntimeError("Não foi possível determinar o nome do modelo de embeddings")

            cls._instance = cls(model_name)
            return cls._instance

    @staticmethod
    def _load_model_name_from_file() -> Optional[str]:
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        try:
            with cfg_path.open("r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
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

        if len(vec) != 384:
            raise RuntimeError(f"Embedding dimensionalidade inesperada: {len(vec)}")

        return vec

__all__ = ["EmbeddingGenerator"]
