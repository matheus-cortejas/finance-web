from __future__ import annotations

import logging
import os
import sys
import threading

from setup.settings import (
    DEFAULT_B3_CSV,
    DEFAULT_RSS_PATH,
    START_MONITOR_ON_SERVER,
    START_SCHEDULER_ON_SERVER,
)
from core.management.workflows import run_monitor_workflow, run_scheduler_workflow


logger = logging.getLogger("startup")
_startup_lock = threading.Lock()
_monitor_started = False
_scheduler_started = False


def _should_start_background_monitor() -> bool:
    if not START_MONITOR_ON_SERVER:
        return False
    if any(part == "test" or part == "discover" or "unittest" in part or "test_" in part for part in sys.argv):
        return False
    if "runserver" not in sys.argv:
        return False
    if os.environ.get("RUN_MAIN") == "true":
        return True
    return "--noreload" in sys.argv


def _run_background_monitor() -> None:
    try:
        run_monitor_workflow(b3_csv=DEFAULT_B3_CSV, rss_path=DEFAULT_RSS_PATH, interactive=False)
    except Exception:
        logger.exception("Falha ao iniciar o monitor em background")


def start_background_monitor() -> bool:
    global _monitor_started

    if not _should_start_background_monitor():
        return False

    with _startup_lock:
        if _monitor_started:
            return False
        _monitor_started = True

    thread = threading.Thread(target=_run_background_monitor, name="monitor-bootstrap", daemon=True)
    thread.start()
    logger.info("Monitor em background iniciado")
    return True


def _should_start_background_scheduler() -> bool:
    if not START_SCHEDULER_ON_SERVER:
        return False
    if any(part == "test" or part == "discover" or "unittest" in part or "test_" in part for part in sys.argv):
        return False
    if "runserver" not in sys.argv:
        return False
    if os.environ.get("RUN_MAIN") == "true":
        return True
    return "--noreload" in sys.argv


def _run_background_scheduler() -> None:
    try:
        run_scheduler_workflow(rss_path=DEFAULT_RSS_PATH)
    except Exception:
        logger.exception("Falha ao iniciar o scheduler em background")


def start_background_scheduler() -> bool:
    global _scheduler_started

    if not _should_start_background_scheduler():
        return False

    with _startup_lock:
        if _scheduler_started:
            return False
        _scheduler_started = True

    thread = threading.Thread(target=_run_background_scheduler, name="scheduler-bootstrap", daemon=True)
    thread.start()
    logger.info("Scheduler em background iniciado")
    return True