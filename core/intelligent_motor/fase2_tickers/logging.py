from typing import Any, Dict, Optional
from ..fase1_global_filter.logging import log_event


def ticker_related(noticia_id: Any, ticker: str, score: float, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = {"ticker": ticker, "score": float(score)}
    if extra:
        payload.update(extra)
    log_event("INFO", noticia_id, "fase2", f"asset:{ticker}", float(score), "TICKER_RELATED", tempo_ms, payload)


def no_ticker_related(noticia_id: Any, tempo_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    log_event("INFO", noticia_id, "fase2", "none", None, "NO_TICKER_RELATED", tempo_ms, extra or {})


def ticker_without_embedding(noticia_id: Any, ticker: str, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = {"ticker": ticker}
    if extra:
        payload.update(extra)
    # Treat as warning-level event; use ERROR path in logging module for visibility
    log_event("WARNING", noticia_id, "fase2", f"asset:{ticker}", None, "TICKER_WITHOUT_EMBEDDING", None, payload)


def asset_store_error(noticia_id: Any, ticker: str, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = {"ticker": ticker, "error": message}
    if extra:
        payload.update(extra)
    log_event("ERROR", noticia_id, "fase2", f"asset:{ticker}", None, "ASSET_STORE_ERROR", None, payload)


__all__ = [
    "ticker_related",
    "no_ticker_related",
    "ticker_without_embedding",
    "asset_store_error",
]
