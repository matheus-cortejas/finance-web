from __future__ import annotations

import os
import logging
from logging.handlers import RotatingFileHandler

from config.settings import LOG_FILE_PATH


def configure_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()
    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s:%(lineno)d %(message)s")

    root_logger.setLevel(level)
    if not any(isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler) for handler in root_logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    if not any(
        isinstance(handler, RotatingFileHandler) and getattr(handler, "baseFilename", "") == str(LOG_FILE_PATH)
        for handler in root_logger.handlers
    ):
        file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    if os.getenv("LOG_LEVEL"):
        logging.getLogger().setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), level))
