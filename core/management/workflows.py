from __future__ import annotations

import logging
import os

from setup.logger import configure_logging
from setup.settings import (
    DEFAULT_B3_CSV,
    DEFAULT_RSS_PATH,
    DEFAULT_ASSETS_JSON_PATH,
    OPENAI_API_KEY,
    OPENAI_MAX_TOKENS,
    OPENAI_MODEL,
    OPENAI_USE_CONTENT,
)
from core.services.acao_service import fetch_sp500_and_store, parse_b3_csv
from core.services.acao_service import load_assets_from_json


logger = logging.getLogger("cli.main")


def load_feeds(path):
    feed_path = os.path.expanduser(os.fspath(path))
    if not os.path.exists(feed_path):
        return []
    with open(feed_path, "r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def _asset_to_dict(asset) -> dict:
    return {
        "id": asset.id,
        "source": asset.source,
        "code": asset.ticker,
        "name": asset.nome,
    }


def _find_assets_by_term(term: str) -> list[dict]:
    from core.models import Ativo

    queryset = Ativo.objects.filter(ticker__icontains=term) | Ativo.objects.filter(nome__icontains=term)
    return [_asset_to_dict(asset) for asset in queryset.distinct()]


def run_monitor_workflow(b3_csv: str | os.PathLike[str] | None = None, rss_path: str | os.PathLike[str] | None = None, interactive: bool = True) -> None:
    from core.models import Ativo
    from core.scheduler.jobs import collect_initial_news

    configure_logging()
    logger.info("Inicializando monitor de notícias")

    # Tenta carregar a partir do JSON primeiro
    json_path = os.path.join(DEFAULT_ASSETS_JSON_PATH.parent, "core_ativos.json")  # ajuste o caminho
    if os.path.exists(json_path):
        logger.info("Carregando ativos do arquivo JSON: %s", json_path)
        load_assets_from_json(json_path)
    else:
        logger.warning("Arquivo JSON não encontrado; recorrendo a fontes externas.")
        # Populando S&P500 (web scraping)
        logger.info("Populando base S&P500")
        try:
            inserted = fetch_sp500_and_store()
            logger.info("S&P500 inseridos: %d", inserted)
        except Exception:
            logger.exception("Falha ao buscar S&P500")

        # Carregando CSV B3
        logger.info("Carregando CSV B3")
        try:
            inserted = parse_b3_csv(os.fspath(b3_csv or DEFAULT_B3_CSV))
            logger.info("B3 inseridos: %d", inserted)
        except Exception:
            logger.exception("Falha ao parsear CSV B3")

    # Resto do workflow (contagem de ativos, feeds, etc.)
    logger.info("Base total de ativos: %d", Ativo.objects.count())
    if interactive:
        logger.info("Modo interativo desativado na refatoração; use a interface Django para registrar ativos")

    feeds = load_feeds(rss_path or DEFAULT_RSS_PATH)
    if not feeds:
        logger.warning("Nenhum feed RSS encontrado; saindo")
        return

    logger.info("Fazendo verificação inicial (último 1 dia) em %d feed(s)", len(feeds))
    reports = collect_initial_news(feeds)
    logger.info("Verificação inicial concluída com %d alerta(s)", len(reports))


def run_scheduler_workflow(rss_path: str | os.PathLike[str] | None = None) -> None:
    from core.scheduler.app import run_scheduler

    configure_logging()
    feeds = load_feeds(rss_path or DEFAULT_RSS_PATH)
    if not feeds:
        logger.warning("Nenhum feed RSS encontrado; saindo")
        return
    logger.info("Iniciando scheduler persistente com %d feed(s)", len(feeds))
    run_scheduler(feeds)