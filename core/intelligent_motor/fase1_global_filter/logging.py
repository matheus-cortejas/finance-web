import json
import logging as _logging
from datetime import datetime
from typing import Optional, Dict, Any

_logger = _logging.getLogger("fase1")
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


def info_accept(id: Any, fase: str, hash: str, score: float, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    log_event("INFO", id, fase, hash, score, "ACCEPT", tempo_ms, extra)


def info_discard(id: Any, fase: str, hash: str, score: float, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    log_event("INFO", id, fase, hash, score, "DISCARD", tempo_ms, extra)


def info_cache_hit(id: Any, fase: str, hash: str, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    log_event("INFO", id, fase, hash, None, "CACHE_HIT", tempo_ms, extra)


def info_cache_miss(id: Any, fase: str, hash: str, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    log_event("INFO", id, fase, hash, None, "CACHE_MISS", tempo_ms, extra)


def error_model(id: Any, fase: str, hash: str, message: str, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = {"error": message}
    if extra:
        payload.update(extra)
    log_event("ERROR", id, fase, hash, None, "MODEL_ERROR", tempo_ms, payload)


def error_cache(id: Any, fase: str, hash: str, message: str, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = {"error": message}
    if extra:
        payload.update(extra)
    log_event("ERROR", id, fase, hash, None, "CACHE_ERROR", tempo_ms, payload)


__all__ = [
    "log_event",
    "info_accept",
    "info_discard",
    "info_cache_hit",
    "info_cache_miss",
    "error_model",
    "error_cache",
]
