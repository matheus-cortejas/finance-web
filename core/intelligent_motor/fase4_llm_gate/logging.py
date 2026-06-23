import json
import logging as _logging
from datetime import datetime
from typing import Optional, Dict, Any

_logger = _logging.getLogger("fase4")
if not _logger.handlers:
    handler = _logging.StreamHandler()
    handler.setLevel(_logging.DEBUG)
    _logger.addHandler(handler)
_logger.setLevel(_logging.INFO)


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def log_event(level: str, id: Any, fase: str, hash: str, score: Optional[float], decisao: str, tempo_ms: Optional[float], extra: Optional[Dict[str, Any]] = None) -> None:
    event = {
        "timestamp": _now_iso(),
        "id": id,
        "fase": fase,
        "hash": hash,
        "score": score,
        "decisao": decisao,
        "tempo_ms": tempo_ms,
    }
    if extra:
        event.update(extra)

    payload = json.dumps(event, ensure_ascii=False)

    if level.upper() == "INFO":
        _logger.info(payload)
    else:
        _logger.error(payload)


def info_llm_classification(id: Any, hash: str, score: float, decisao: int, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    log_event("INFO", id, "fase4", hash, float(score), str(decisao), tempo_ms, extra)


def info_cache_hit(id: Any, hash: str, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    log_event("INFO", id, "fase4", hash, None, "CACHE_HIT", tempo_ms, extra)


def info_cache_miss(id: Any, hash: str, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    log_event("INFO", id, "fase4", hash, None, "CACHE_MISS", tempo_ms, extra)


def error_llm_fallback(id: Any, hash: str, score: Optional[float], decisao: int, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = {"note": "LLM fallback"}
    if extra:
        payload.update(extra)
    log_event("ERROR", id, "fase4", hash, score, str(decisao), tempo_ms, payload)


__all__ = [
    "log_event",
    "info_llm_classification",
    "info_cache_hit",
    "info_cache_miss",
    "error_llm_fallback",
]
