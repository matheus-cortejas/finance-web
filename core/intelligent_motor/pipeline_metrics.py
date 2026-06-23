# pipeline_metrics.py
"""
Módulo auxiliar de instrumentação do Motor Inteligente.

Objetivo: registrar, de forma não-invasiva, métricas de execução de cada
notícia processada pelo pipeline_orchestrator (tempos por fase, scores,
decisões de cada fase, etc.), para uso posterior em análises e gráficos
do artigo (ENIAC/PSI).

Cada chamada a `processar_noticia_completa` gera UMA linha em um arquivo
JSON Lines (uma notícia = um JSON por linha), o que facilita tanto a
leitura incremental quanto a conversão posterior para CSV/DataFrame
(ver export_metrics.py).

O módulo foi escrito para não quebrar caso seja usado fora do contexto
Django (ex.: em testes/scripts), e para não interromper o pipeline caso
a escrita em disco falhe por qualquer motivo.
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Iterable, List, Tuple

_write_lock = threading.Lock()

DEFAULT_METRICS_FILENAME = "pipeline_metrics.jsonl"

# Possíveis variações de string usadas para indicar a origem do ativo
# (ajuste aqui se o seu campo `Ativo.source` usar outros valores).
_B3_LABELS = {"b3"}
_SP500_LABELS = {"sp500", "s&p500", "snp500", "s&p 500"}


def _resolve_metrics_path(config: Dict[str, Any] = None) -> str:
    """
    Resolve o caminho do arquivo de métricas.

    Prioridade:
      1) config["metrics"]["path"], se definido em config/*.yaml
      2) variável de ambiente PIPELINE_METRICS_PATH
      3) arquivo padrão na raiz do projeto (DEFAULT_METRICS_FILENAME)
    """
    metrics_cfg = (config or {}).get("metrics", {}) or {}
    path = metrics_cfg.get("path") or os.environ.get(
        "PIPELINE_METRICS_PATH", DEFAULT_METRICS_FILENAME
    )
    return path


def registrar_metrica(metrica: Dict[str, Any], config: Dict[str, Any] = None) -> None:
    """
    Acrescenta um registro (dict) ao arquivo JSONL de métricas.

    Falhas de I/O são silenciadas (apenas logadas em stderr) para que a
    instrumentação NUNCA derrube o processamento real de uma notícia.
    """
    registro = dict(metrica)
    registro.setdefault("registrado_em", datetime.now(timezone.utc).isoformat())

    path = _resolve_metrics_path(config)
    linha = json.dumps(registro, ensure_ascii=False, default=str)

    try:
        with _write_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(linha + "\n")
    except OSError as exc:  # pragma: no cover - defensivo
        print(f"[pipeline_metrics] Falha ao gravar métrica: {exc}")


# ---------------------------------------------------------------------------
# Classificação de tickers por origem (B3 / S&P500), usada para reportar
# cobertura do universo de ativos na Fase 2.
# ---------------------------------------------------------------------------

_TICKER_SOURCE_CACHE: Dict[str, str] = None  # type: ignore
_TICKER_SOURCE_LOCK = threading.Lock()


def _carregar_mapa_tickers() -> Dict[str, str]:
    """
    Carrega (uma única vez, com cache em memória) o mapeamento
    ticker -> origem ('b3' | 'sp500' | outro), a partir do modelo Ativo.

    Se o Django não estiver configurado/disponível (ex.: rodando fora do
    contexto da app), retorna um dicionário vazio sem lançar exceção.
    """
    global _TICKER_SOURCE_CACHE
    if _TICKER_SOURCE_CACHE is not None:
        return _TICKER_SOURCE_CACHE

    with _TICKER_SOURCE_LOCK:
        if _TICKER_SOURCE_CACHE is not None:
            return _TICKER_SOURCE_CACHE

        mapa: Dict[str, str] = {}
        try:
            from ..models import Ativo  # import tardio: evita custo/erro fora do Django

            for ticker, source in Ativo.objects.values_list("ticker", "source"):
                mapa[ticker] = (source or "").strip().lower()
        except Exception as exc:  # pragma: no cover - defensivo
            print(f"[pipeline_metrics] Não foi possível carregar Ativo.objects: {exc}")
            mapa = {}

        _TICKER_SOURCE_CACHE = mapa
        return mapa


def invalidar_cache_tickers() -> None:
    """Permite forçar releitura do mapeamento ticker->origem (ex.: após popular_ativos)."""
    global _TICKER_SOURCE_CACHE
    with _TICKER_SOURCE_LOCK:
        _TICKER_SOURCE_CACHE = None


def classificar_tickers_por_origem(tickers: Iterable[str]) -> Tuple[int, int, int]:
    """
    Recebe a lista de tickers_relacionados (Fase 2) e retorna a contagem
    (n_b3, n_sp500, n_outros), com base no campo `Ativo.source`.

    Tickers não encontrados no mapeamento são contados em `n_outros`.
    """
    mapa = _carregar_mapa_tickers()
    n_b3 = n_sp500 = n_outros = 0

    for ticker in tickers:
        origem = mapa.get(ticker)
        if origem in _B3_LABELS:
            n_b3 += 1
        elif origem in _SP500_LABELS:
            n_sp500 += 1
        else:
            n_outros += 1

    return n_b3, n_sp500, n_outros


# ---------------------------------------------------------------------------
# Utilidades de leitura (úteis em scripts/notebooks de análise)
# ---------------------------------------------------------------------------

def ler_metricas(path: str = None, config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Lê o arquivo JSONL de métricas e retorna uma lista de dicionários.
    Linhas inválidas são ignoradas (com aviso).
    """
    path = path or _resolve_metrics_path(config)
    registros: List[Dict[str, Any]] = []

    if not os.path.exists(path):
        return registros

    with open(path, "r", encoding="utf-8") as f:
        for i, linha in enumerate(f, start=1):
            linha = linha.strip()
            if not linha:
                continue
            try:
                registros.append(json.loads(linha))
            except json.JSONDecodeError:
                print(f"[pipeline_metrics] Linha {i} inválida em {path}, ignorada.")

    return registros
