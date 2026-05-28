from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from setup.settings import ARTICLE_RETENTION_DAYS


logger = logging.getLogger("scheduler.jobs")


def get_watchlist_assets():
    from core.services.usuario_service import list_watchlist_assets

    return list_watchlist_assets()


def purge_articles_older_than_days(days: int) -> int:
    from core.models import Noticia

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted_count, _ = Noticia.objects.filter(publicado_em__isnull=False, publicado_em__lt=cutoff).delete()
    return deleted_count


def check_feeds_and_report(feed_urls, watch_assets, within_days=None):
    from core.services.noticia_service import check_feeds_and_report as core_check_feeds_and_report

    return core_check_feeds_and_report(feed_urls, watch_assets, within_days=within_days)


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
