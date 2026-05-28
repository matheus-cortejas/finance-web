from __future__ import annotations

import logging

from config.settings import ARTICLE_RETENTION_DAYS
from database.acao_repo import get_watchlist_assets
from database.noticia_repo import purge_articles_older_than_days
from services.noticia_service import check_feeds_and_report


logger = logging.getLogger(__name__)


def collect_news(feed_urls):
    watch_assets = [dict(asset) for asset in get_watchlist_assets()]
    logger.info("Executando coleta recorrente com %d ativo(s) na watchlist", len(watch_assets))
    reports = check_feeds_and_report(feed_urls, watch_assets, within_days=None)
    logger.info("Coleta recorrente concluída com %d alerta(s)", len(reports))
    return reports


def collect_initial_news(feed_urls):
    watch_assets = [dict(asset) for asset in get_watchlist_assets()]
    logger.info("Executando coleta inicial com janela de %d dia(s)", ARTICLE_RETENTION_DAYS)
    reports = check_feeds_and_report(feed_urls, watch_assets, within_days=ARTICLE_RETENTION_DAYS)
    logger.info("Coleta inicial concluída com %d alerta(s)", len(reports))
    return reports


def cleanup_old_articles() -> int:
    deleted = purge_articles_older_than_days(ARTICLE_RETENTION_DAYS)
    logger.info("Limpeza de artigos antigos removeu %d registro(s)", deleted)
    return deleted
