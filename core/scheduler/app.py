from __future__ import annotations

import logging

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    BackgroundScheduler = None

from setup.settings import MONITOR_INTERVAL_SECONDS
from core.scheduler.jobs import collect_news   # remova cleanup_old_articles se não usar

logger = logging.getLogger("scheduler.app")

def build_scheduler(feed_urls):
    if BackgroundScheduler is None:
        logger.error("APScheduler não instalado. Instale com: pip install apscheduler")
        return None

    scheduler = BackgroundScheduler()
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
    return scheduler

def run_scheduler(feed_urls) -> None:
    scheduler = build_scheduler(feed_urls)
    if scheduler is None:
        logger.error("Não foi possível criar o scheduler. Verifique a instalação do APScheduler.")
        return
    logger.info("Iniciando scheduler em background com %d feed(s)", len(feed_urls))
    scheduler.start()