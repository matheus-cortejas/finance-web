from __future__ import annotations

import os
from pathlib import Path

try:
	from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
	load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if load_dotenv:
	load_dotenv(PROJECT_ROOT / ".env")

DB_PATH = Path(os.getenv("DB_PATH", PROJECT_ROOT / "data.db"))
DEFAULT_B3_CSV = Path(os.getenv("B3_CSV_PATH", PROJECT_ROOT / "IBOVDia_24-03-26.csv"))
DEFAULT_RSS_PATH = Path(os.getenv("RSS_PATH", PROJECT_ROOT / "rss.txt"))
LOG_FILE_PATH = Path(os.getenv("LOG_FILE_PATH", PROJECT_ROOT / "logs" / "monitor.log"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
OPENAI_USE_CONTENT = os.getenv("OPENAI_USE_CONTENT", "false").lower() in {"1", "true", "yes", "on"}
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "100"))

MONITOR_INTERVAL_SECONDS = int(os.getenv("MONITOR_INTERVAL_SECONDS", "300"))
ARTICLE_RETENTION_DAYS = int(os.getenv("ARTICLE_RETENTION_DAYS", "1"))
