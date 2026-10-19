from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

try:
    import dj_database_url
except Exception:  # pragma: no cover - optional dependency
    dj_database_url = None


BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if load_dotenv:
    load_dotenv(PROJECT_ROOT / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str = "") -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-!7*w_xu!*u^j7e)*3-5og_s)qa61#ra+2pc7y+y%4gc2nb!ow3")
DEBUG = _env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
CSRF_TRUSTED_ORIGINS = _env_list("CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core.apps.CoreConfig",
    "pipeline_lab.apps.PipelineLabConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "setup.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [PROJECT_ROOT / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "setup.wsgi.application"
ASGI_APPLICATION = "setup.asgi.application"

DB_PATH = Path(os.getenv("DB_PATH", PROJECT_ROOT / "db.sqlite3"))
DEFAULT_B3_CSV = Path(os.getenv("B3_CSV_PATH", PROJECT_ROOT / "IBOVDia_24-03-26.csv"))
DEFAULT_RSS_PATH = Path(os.getenv("RSS_PATH", PROJECT_ROOT / "rss.txt"))
DEFAULT_ASSETS_JSON_PATH = Path(os.getenv("ASSETS_JSON_PATH", PROJECT_ROOT / "core_ativos.json"))
LOG_FILE_PATH = Path(os.getenv("LOG_FILE_PATH", PROJECT_ROOT / "logs" / "monitor.log"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_USE_CONTENT = _env_bool("OPENAI_USE_CONTENT", False)
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "100"))
ARTICLE_DESCRIPTION_MAX_CHARS = _env_int("ARTICLE_DESCRIPTION_MAX_CHARS", 1200)
ARTICLE_CONTENT_MAX_CHARS = _env_int("ARTICLE_CONTENT_MAX_CHARS", 4000)
ALERT_MIN_PRIORITY = os.getenv("ALERT_MIN_PRIORITY", "media").lower()

# Coleta independente do pipeline. O intervalo do coletor tem default próprio;
# o antigo MONITOR_INTERVAL_SECONDS ficou só no legado.
COLLECTOR_INTERVAL_SECONDS = int(os.getenv("COLLECTOR_INTERVAL_SECONDS", "300"))
ARTICLE_RETENTION_DAYS = int(os.getenv("ARTICLE_RETENTION_DAYS", "1"))

# ---------------------------------------------------------------------------
# Experimento do TCC
# ---------------------------------------------------------------------------
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
EMBEDDING_MODELS = _env_list(
    "EMBEDDING_MODELS",
    "paraphrase-multilingual-MiniLM-L12-v2",
)

# Pasta onde o laboratório guarda modelos locais enviados pela interface.
# Dentro do container ela é um bind mount gravável do projeto.
LAB_MODELS_DIR = Path(
    os.getenv(
        "LAB_MODELS_DIR",
        str(PROJECT_ROOT / "core" / "intelligent_motor" / "models"),
    )
)
# Limite do upload de modelo (compactado) em MB.
LAB_MODEL_UPLOAD_MAX_MB = int(os.getenv("LAB_MODEL_UPLOAD_MAX_MB", "4096"))
EXPERIMENT_WORKER_POLL_SECONDS = int(os.getenv("WORKER_POLL_SECONDS", "10"))
EXPERIMENT_BATCH_SIZE = int(os.getenv("EXPERIMENT_BATCH_SIZE", "16"))
EXPERIMENT_CACHE_ENABLED = _env_bool("EXPERIMENT_CACHE_ENABLED", False)
EXPERIMENT_METRICS_PATH = Path(
    os.getenv("PIPELINE_METRICS_PATH", PROJECT_ROOT / "pipeline_metrics.jsonl")
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_PATH,
    }
}

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL and dj_database_url:
    DATABASES["default"] = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

if DEBUG:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [PROJECT_ROOT / 'static']
STATIC_ROOT = PROJECT_ROOT / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

# Garante que o diretório de log exista antes de o RotatingFileHandler abrir.
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s:%(lineno)d %(message)s",
            "datefmt": "%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_FILE_PATH),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": os.getenv("LOG_LEVEL", "INFO").upper(),
    },
    "loggers": {
        "core": {"level": "DEBUG"},
        "apscheduler": {"level": "WARNING"},
        "django.request": {"level": "INFO"},
    },
}
