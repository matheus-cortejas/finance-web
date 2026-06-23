from typing import Any, Dict, Optional
from ..fase1_global_filter.logging import log_event


def log_score(noticia_id: Any, score: int, criterios: list, tempo_ms: Optional[float] = None) -> None:
    payload = {"criterios": ",".join(criterios)}
    log_event("INFO", noticia_id, "fase3", "heuristica", float(score), "SCORE", tempo_ms, payload)


def log_error(noticia_id: Any, message: str) -> None:
    log_event("ERROR", noticia_id, "fase3", "heuristica", None, "HEURISTICA_ERROR", None, {"error": message})


__all__ = ["log_score", "log_error"]
