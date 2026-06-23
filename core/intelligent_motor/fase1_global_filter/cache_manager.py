# cache_manager.py
import os
import json
import time
import sqlite3
from typing import Optional, List, Any, Dict

import yaml


class CacheManager:
    """Interface base para gerenciadores de cache."""
    def get(self, key: str) -> Optional[List[float]]:
        raise NotImplementedError()

    def set(self, key: str, value: List[float], ttl: int) -> None:
        raise NotImplementedError()


class RedisCache(CacheManager):
    """Cache Redis com timeouts baixos e reconexão automática."""
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, timeout: int = 2):
        try:
            import redis
            self._client = redis.Redis(
                host=host, port=port, db=db,
                socket_connect_timeout=timeout,
                socket_timeout=timeout,
                retry_on_timeout=False
            )
            self._client.ping()
        except Exception as exc:
            raise RuntimeError(f"Redis unavailable: {exc}")

    def get(self, key: str) -> Optional[List[float]]:
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set(self, key: str, value: List[float], ttl: int) -> None:
        try:
            self._client.setex(key, ttl, json.dumps(value))
        except Exception:
            pass


class SQLiteCache(CacheManager):
    """Cache SQLite com suporte a expiração e thread-safe."""
    def __init__(self, path: Optional[str] = None):
        root = path or os.environ.get("FASE1_SQLITE_PATH")
        if not root:
            root = os.path.join(os.path.dirname(__file__), "fase1_cache.sqlite")
        self._path = root
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._ensure_table()

    def _ensure_table(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at INTEGER
            )
            """
        )
        self._conn.commit()

    def get(self, key: str) -> Optional[List[float]]:
        cur = self._conn.cursor()
        cur.execute("SELECT value, expires_at FROM embeddings WHERE key = ?", (key,))
        row = cur.fetchone()
        if row is None:
            return None
        value_json, expires_at = row
        now = int(time.time())
        if expires_at is not None and expires_at < now:
            cur.execute("DELETE FROM embeddings WHERE key = ?", (key,))
            self._conn.commit()
            return None
        try:
            return json.loads(value_json)
        except Exception:
            return None

    def set(self, key: str, value: List[float], ttl: int) -> None:
        expires_at = int(time.time()) + int(ttl) if ttl else None
        cur = self._conn.cursor()
        cur.execute(
            "REPLACE INTO embeddings (key, value, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), expires_at),
        )
        self._conn.commit()


# ---------- Singleton para o cache manager ----------
_CACHE_MANAGER = None

def get_cache_manager(config: Optional[Dict] = None) -> CacheManager:
    """
    Retorna uma instância singleton do cache manager.
    - Se `config` for fornecida, usa as configurações de cache da fase1 (recomendado para primeira chamada).
    - Caso contrário, tenta carregar do arquivo local (fallback para compatibilidade).
    """
    global _CACHE_MANAGER
    if _CACHE_MANAGER is not None:
        return _CACHE_MANAGER

    # Extrai configuração da fase1
    if config is not None:
        fase1 = config.get("fase1", {})
    else:
        # Fallback: carrega do arquivo local (apenas para compatibilidade com testes)
        cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            cfg = {}
        fase1 = cfg.get("fase1", {})

    backend = os.environ.get("FASE1_CACHE_BACKEND") or fase1.get("cache", {}).get("backend", "redis")

    if backend == "redis":
        try:
            host = os.environ.get("REDIS_HOST", "localhost")
            port = int(os.environ.get("REDIS_PORT", 6379))
            db = int(os.environ.get("REDIS_DB", 0))
            timeout = int(os.environ.get("REDIS_TIMEOUT", 2))
            _CACHE_MANAGER = RedisCache(host=host, port=port, db=db, timeout=timeout)
        except Exception:
            _CACHE_MANAGER = SQLiteCache()
    else:
        _CACHE_MANAGER = SQLiteCache()

    return _CACHE_MANAGER


__all__ = ["CacheManager", "RedisCache", "SQLiteCache", "get_cache_manager"]