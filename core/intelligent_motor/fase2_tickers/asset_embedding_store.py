import json
import os
import sqlite3
import time
from typing import Dict, List, Optional

from ..fase1_global_filter.embedding_generator import EmbeddingGenerator
from .exceptions import MappingError, PersistenceError


class AssetEmbeddingStore:
    def __init__(self, mapping_path: Optional[str] = None, db_path: Optional[str] = None):
        self._root = os.path.dirname(__file__)
        self.mapping_path = mapping_path or os.path.join(self._root, "ativos_mapeamento.json")
        self.db_path = db_path or os.path.join(self._root, "asset_embeddings.sqlite")
        self._mapping: Dict[str, str] = {}
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._ensure_table()

    def _ensure_table(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS asset_embeddings (
                ticker TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                embedding TEXT NOT NULL,
                updated_at INTEGER
            )
            """
        )
        self._conn.commit()

    def load_mapping(self) -> Dict[str, str]:
        if not os.path.exists(self.mapping_path):
            raise MappingError(f"Mapping file not found: {self.mapping_path}")
        try:
            with open(self.mapping_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            raise MappingError(str(exc))

        if not isinstance(data, dict):
            raise MappingError("Mapping file must contain a JSON object of ticker->description")

        self._mapping = data
        return data

    def generate_and_persist_all(self) -> None:
        if not self._mapping:
            self.load_mapping()

        gen = EmbeddingGenerator.instance()
        cur = self._conn.cursor()

        for ticker, desc in self._mapping.items():
            emb = gen.gerar(desc)
            try:
                cur.execute(
                    "REPLACE INTO asset_embeddings (ticker, description, embedding, updated_at) VALUES (?, ?, ?, ?)",
                    (ticker, desc, json.dumps(emb, ensure_ascii=False), int(time.time())),
                )
            except Exception as exc:
                raise PersistenceError(str(exc))

        self._conn.commit()

    def get_embedding(self, ticker: str) -> Optional[List[float]]:
        cur = self._conn.cursor()
        cur.execute("SELECT embedding FROM asset_embeddings WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None

    def list_tickers(self) -> List[str]:
        if not self._mapping:
            try:
                self.load_mapping()
            except MappingError:
                pass
        return list(self._mapping.keys())
    
    def save(self, ticker: str, embedding: List[float], description: str = "") -> None:
        cur = self._conn.cursor()
        # Se description não for fornecida, tenta buscar do mapeamento carregado
        if not description and ticker in self._mapping:
            description = self._mapping[ticker]
        cur.execute(
            "REPLACE INTO asset_embeddings (ticker, description, embedding, updated_at) VALUES (?, ?, ?, ?)",
            (ticker, description, json.dumps(embedding, ensure_ascii=False), int(time.time()))
        )
        self._conn.commit()



__all__ = ["AssetEmbeddingStore"]
