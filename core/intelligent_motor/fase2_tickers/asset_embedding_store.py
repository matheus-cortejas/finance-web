from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..fase1_global_filter.embedding_generator import EmbeddingGenerator
from .exceptions import MappingError, PersistenceError


class AssetEmbeddingStore:
    """Store de embeddings de ativos, sempre namespaced por modelo.

    A implementação preferencial usa a tabela `pipeline_lab_assetembedding`
    no PostgreSQL. Se o Django/banco não estiver disponível (scripts e testes
    isolados), cai para um SQLite separado por modelo.
    """

    def __init__(
        self,
        mapping_path: Optional[str] = None,
        db_path: Optional[str] = None,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self._root = Path(__file__).parent
        self.model_name = EmbeddingGenerator.resolve_model_name(model_name=model_name)
        self.device = (
            EmbeddingGenerator.resolve_device(device) if device else None
        )
        self.model_key = hashlib.sha256(
            self.model_name.encode("utf-8")
        ).hexdigest()[:16]
        self.mapping_path = mapping_path or str(self._root / "ativos_mapeamento.json")
        self.db_path = db_path or self._default_sqlite_path()
        self._mapping: Dict[str, str] = {}
        self._cache: Optional[Dict[str, List[float]]] = None
        self._matrix_cache = None
        self._sqlite_conn: Optional[sqlite3.Connection] = None
        self._use_db = self._can_use_django()

    # ------------------------------------------------------------------ setup

    def _default_sqlite_path(self) -> str:
        base = os.environ.get("ASSET_EMBEDDINGS_DIR")
        if not base:
            fase1_path = os.environ.get("FASE1_SQLITE_PATH")
            base = (
                str(Path(fase1_path).parent)
                if fase1_path
                else str(self._root)
            )
        Path(base).mkdir(parents=True, exist_ok=True)
        return str(Path(base) / f"asset_embeddings_{self.model_key}.sqlite")

    @staticmethod
    def _can_use_django() -> bool:
        try:
            from pipeline_lab.models import AssetEmbedding

            AssetEmbedding.objects.exists()
            return True
        except Exception:
            return False

    @property
    def sqlite(self) -> sqlite3.Connection:
        if self._sqlite_conn is None:
            self._sqlite_conn = sqlite3.connect(
                self.db_path, check_same_thread=False
            )
            self._ensure_sqlite_table()
        return self._sqlite_conn

    def _ensure_sqlite_table(self) -> None:
        cur = self.sqlite.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS asset_embeddings (
                modelo TEXT NOT NULL,
                ticker TEXT NOT NULL,
                description TEXT NOT NULL,
                embedding TEXT NOT NULL,
                updated_at INTEGER,
                PRIMARY KEY (modelo, ticker)
            )
            """
        )
        self.sqlite.commit()

    # --------------------------------------------------------------- mapping

    def load_mapping(self) -> Dict[str, str]:
        if not os.path.exists(self.mapping_path):
            raise MappingError(f"Mapping file not found: {self.mapping_path}")
        try:
            with open(self.mapping_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            raise MappingError(str(exc))

        if not isinstance(data, dict):
            raise MappingError(
                "Mapping file must contain a JSON object of ticker->description"
            )

        self._mapping = data
        return data

    def _asset_descriptions(
        self, tickers: Optional[Iterable[str]] = None
    ) -> Dict[str, str]:
        try:
            from core.models import Ativo

            qs = Ativo.objects.all()
            if tickers:
                qs = qs.filter(ticker__in=list(tickers))
            rows = qs.values_list("ticker", "nome", "descricao_embedding")
            result = {}
            for ticker, nome, descricao in rows:
                result[ticker] = (
                    (descricao or "").strip() or f"{ticker} {nome}".strip()
                )
            if result:
                return result
        except Exception:
            pass

        if not self._mapping:
            try:
                self.load_mapping()
            except MappingError:
                return {}
        return dict(self._mapping)

    # --------------------------------------------------------------- leitura

    def _load_cache(self) -> Dict[str, List[float]]:
        if self._cache is not None:
            return self._cache

        embeddings: Dict[str, List[float]] = {}
        if self._use_db:
            from pipeline_lab.models import AssetEmbedding

            rows = AssetEmbedding.objects.filter(modelo=self.model_name).values_list(
                "ticker", "embedding"
            )
            embeddings = {
                ticker: [float(x) for x in embedding or []]
                for ticker, embedding in rows
            }
        else:
            cur = self.sqlite.cursor()
            cur.execute(
                "SELECT ticker, embedding FROM asset_embeddings WHERE modelo = ?",
                (self.model_name,),
            )
            for ticker, raw in cur.fetchall():
                try:
                    embeddings[ticker] = json.loads(raw)
                except Exception:
                    continue

        self._cache = embeddings
        return embeddings

    def get_embeddings(
        self, tickers: Optional[Iterable[str]] = None
    ) -> Dict[str, List[float]]:
        cache = self._load_cache()
        if tickers is None:
            return dict(cache)
        return {ticker: cache[ticker] for ticker in tickers if ticker in cache}

    def get_embedding(self, ticker: str) -> Optional[List[float]]:
        return self.get_embeddings([ticker]).get(ticker)

    def get_descriptions(
        self, tickers: Optional[Iterable[str]] = None
    ) -> Dict[str, str]:
        """Texto descritivo de cada ativo (para cross-encoder / LLM da Fase 2)."""
        return self._asset_descriptions(tickers)

    def list_tickers(self) -> List[str]:
        return list(self._load_cache().keys())

    def get_matrix(self, tickers: Iterable[str]):
        """Matriz numpy (n_ativos x dimensão) normalizada, em cache.

        Retorna (tickers_presentes, matriz) ou (None, None) se numpy não
        estiver disponível.
        """
        try:
            import numpy as np
        except Exception:
            return None, None

        tickers = list(tickers)
        key = tuple(tickers)
        if self._matrix_cache and self._matrix_cache[0] == key:
            return self._matrix_cache[1], self._matrix_cache[2]

        embeddings = self.get_embeddings(tickers)
        present = [ticker for ticker in tickers if ticker in embeddings]
        if not present:
            self._matrix_cache = (key, [], None)
            return [], None

        matrix = np.asarray(
            [embeddings[ticker] for ticker in present], dtype=np.float32
        )
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        matrix = matrix / np.clip(norms, 1e-12, None)
        self._matrix_cache = (key, present, matrix)
        return present, matrix

    # --------------------------------------------------------------- escrita

    def save(
        self,
        ticker: str,
        embedding: List[float],
        description: str = "",
    ) -> None:
        if not description:
            description = self._asset_descriptions([ticker]).get(ticker, ticker)

        if self._use_db:
            from pipeline_lab.models import AssetEmbedding

            AssetEmbedding.objects.update_or_create(
                modelo=self.model_name,
                ticker=ticker,
                defaults={
                    "descricao": description,
                    "embedding": embedding,
                    "dimensao": len(embedding),
                },
            )
        else:
            try:
                self.sqlite.execute(
                    """
                    REPLACE INTO asset_embeddings
                        (modelo, ticker, description, embedding, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self.model_name,
                        ticker,
                        description,
                        json.dumps(embedding, ensure_ascii=False),
                        int(time.time()),
                    ),
                )
                self.sqlite.commit()
            except Exception as exc:
                raise PersistenceError(str(exc)) from exc

        if self._cache is not None:
            self._cache[ticker] = embedding
        self._matrix_cache = None

    def generate_and_persist_all(
        self,
        tickers: Optional[Iterable[str]] = None,
        *,
        force: bool = False,
        batch_size: int = 32,
    ) -> int:
        """Gera embeddings para os ativos que ainda não têm registro neste modelo."""
        descriptions = self._asset_descriptions(tickers)
        if not descriptions:
            return 0

        existing = set() if force else set(self._load_cache().keys())
        missing = [
            (ticker, desc)
            for ticker, desc in descriptions.items()
            if ticker not in existing
        ]
        if not missing:
            return 0

        generator = EmbeddingGenerator.instance(
            model_name=self.model_name,
            device=self.device,
        )
        saved = 0
        for start in range(0, len(missing), batch_size):
            chunk = missing[start : start + batch_size]
            vectors = generator.gerar_lote(
                [desc for _, desc in chunk],
                batch_size=batch_size,
            )
            if self._use_db:
                from django.utils import timezone
                from pipeline_lab.models import AssetEmbedding

                now = timezone.now()
                objects = [
                    AssetEmbedding(
                        modelo=self.model_name,
                        ticker=ticker,
                        descricao=desc,
                        embedding=vector,
                        dimensao=len(vector),
                        atualizado_em=now,
                    )
                    for (ticker, desc), vector in zip(chunk, vectors)
                ]
                AssetEmbedding.objects.bulk_create(
                    objects,
                    update_conflicts=True,
                    unique_fields=["modelo", "ticker"],
                    update_fields=[
                        "descricao",
                        "embedding",
                        "dimensao",
                        "atualizado_em",
                    ],
                    batch_size=100,
                )
            else:
                for (ticker, desc), vector in zip(chunk, vectors):
                    self.save(ticker, vector, description=desc)
            saved += len(chunk)

        self._cache = None
        self._matrix_cache = None
        return saved


_STORES: Dict[str, AssetEmbeddingStore] = {}
_STORES_LOCK = threading.Lock()


def get_asset_embedding_store(
    model_name: Optional[str] = None,
    device: Optional[str] = None,
) -> AssetEmbeddingStore:
    resolved = EmbeddingGenerator.resolve_model_name(model_name=model_name)
    effective_device = EmbeddingGenerator.resolve_device(device) if device else ""
    cache_key = f"{resolved}::{effective_device}"
    with _STORES_LOCK:
        store = _STORES.get(cache_key)
        if store is None:
            store = AssetEmbeddingStore(model_name=resolved, device=device)
            _STORES[cache_key] = store
        return store


def reset_asset_embedding_stores() -> None:
    with _STORES_LOCK:
        _STORES.clear()


__all__ = [
    "AssetEmbeddingStore",
    "get_asset_embedding_store",
    "reset_asset_embedding_stores",
]
