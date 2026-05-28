from __future__ import annotations

import logging

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
except Exception:  # pragma: no cover - optional dependency
    BlockingScheduler = None

from config.settings import MONITOR_INTERVAL_SECONDS
from scheduler.jobs import cleanup_old_articles, collect_news


logger = logging.getLogger(__name__)


def build_scheduler(feed_urls) -> BlockingScheduler:
    if BlockingScheduler is None:
        raise RuntimeError("APScheduler is required to run the monitor scheduler")

    scheduler = BlockingScheduler()
    scheduler.add_job(
        collect_news,
        "interval",
        seconds=MONITOR_INTERVAL_SECONDS,
        args=[feed_urls],
        id="collect_news",
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Job agendado: collect_news a cada %d segundos", MONITOR_INTERVAL_SECONDS)
    scheduler.add_job(
        cleanup_old_articles,
        "interval",
        hours=24,
        id="cleanup_old_articles",
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Job agendado: cleanup_old_articles a cada 24 horas")
    return scheduler


def run_scheduler(feed_urls) -> None:
    scheduler = build_scheduler(feed_urls)
    logger.info("Iniciando scheduler com %d feed(s)", len(feed_urls))
    scheduler.start()