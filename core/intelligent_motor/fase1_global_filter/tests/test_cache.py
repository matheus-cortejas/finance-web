import json
import time

from core.intelligent_motor.fase1_global_filter.cache_manager import SQLiteCache


def test_sqlite_cache_hit_miss_and_expiration(tmp_path, monkeypatch):
    path = str(tmp_path / "cache.db")
    cache = SQLiteCache(path=path)

    key = "emb:test"
    value = [0.1, 0.2, 0.3]

    assert cache.get(key) is None

    cache.set(key, value, ttl=10)
    got = cache.get(key)
    assert got == value

    # simulate time after expiration
    original_time = time.time()

    monkeypatch.setattr("time.time", lambda: original_time + 11)
    assert cache.get(key) is None
