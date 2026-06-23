from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency
    yaml = None

from ..fase1_global_filter.cache_manager import get_cache_manager


def _load_config() -> dict:
    cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if yaml and os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        except Exception:
            return {}
    return {}


def prompt_hash(prompt: str) -> str:
    h = hashlib.sha256()
    h.update((prompt or "").encode("utf-8"))
    return h.hexdigest()


def cache_enabled() -> bool:
    cfg = _load_config()
    return bool(cfg.get("fase4", {}).get("cache", {}).get("enabled", True))


def cache_ttl() -> int:
    cfg = _load_config()
    return int(cfg.get("fase4", {}).get("cache", {}).get("ttl_segundos", 86400))


def _make_key(hash_hex: str) -> str:
    return f"fase4:decision:{hash_hex}"


def get_cached_decision(prompt: str) -> int | None:
    try:
        mgr = get_cache_manager()
    except Exception:
        return None
    key = _make_key(prompt_hash(prompt))
    try:
        val = mgr.get(key)
    except Exception:
        return None
    if val is None:
        return None
    # val can be dict, list, int, etc.
    if isinstance(val, dict):
        v = val.get("decision")
        try:
            return int(v)
        except Exception:
            return None
    if isinstance(val, list) and val:
        try:
            return int(val[0])
        except Exception:
            return None
    try:
        return int(val)
    except Exception:
        return None


def set_cached_decision(prompt: str, decision: int, ttl: int | None = None) -> None:
    try:
        mgr = get_cache_manager()
    except Exception:
        return None
    key = _make_key(prompt_hash(prompt))
    payload: Any = {"decision": int(decision), "ts": int(time.time())}
    try:
        mgr.set(key, payload, int(ttl) if ttl is not None else cache_ttl())
    except Exception:
        return None


__all__ = ["prompt_hash", "get_cached_decision", "set_cached_decision", "cache_enabled", "cache_ttl"]
