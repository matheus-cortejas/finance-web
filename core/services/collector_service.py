from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.db import IntegrityError, transaction

from core.models import FonteRSS, Noticia
from core.parsers.factory import create_parser

logger = logging.getLogger("collector")

_TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


@dataclass
class FeedResult:
    url: str
    feed_url: str = ""
    entries: int = 0
    criadas: int = 0
    duplicadas: int = 0
    antigas: int = 0
    invalidas: int = 0
    erros: int = 0
    erro: str = ""


@dataclass
class CollectionResult:
    feeds: list[FeedResult] = field(default_factory=list)

    @property
    def criadas(self) -> int:
        return sum(item.criadas for item in self.feeds)

    @property
    def duplicadas(self) -> int:
        return sum(item.duplicadas for item in self.feeds)

    @property
    def erros(self) -> int:
        return sum(item.erros for item in self.feeds)

    def as_dict(self) -> dict:
        return {
            "feeds": [asdict(item) for item in self.feeds],
            "criadas": self.criadas,
            "duplicadas": self.duplicadas,
            "erros": self.erros,
        }


def normalize_link(link: str) -> str:
    """Remove parâmetros de tracking e normaliza esquema/host."""
    if not link:
        return ""
    try:
        parts = urlsplit(link.strip())
    except Exception:
        return link.strip()
    if not parts.scheme or not parts.netloc:
        return link.strip()
    query_items = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(query_items, doseq=True)
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, query, "")
    )


def _safe_raw_data(raw_entry) -> dict | None:
    if raw_entry is None:
        return None
    try:
        json.dumps(raw_entry)
        return raw_entry
    except TypeError:
        return json.loads(json.dumps(raw_entry, default=str))


def _as_utc(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def sync_feeds_from_file(path: str | Path | None = None) -> tuple[int, int]:
    """Garante que as URLs do arquivo de feeds existam em FonteRSS.

    Retorna (criadas, total_lido). É idempotente.
    """
    feed_path = Path(path or settings.DEFAULT_RSS_PATH).expanduser()
    if not feed_path.exists():
        logger.warning("Arquivo de feeds não encontrado: %s", feed_path)
        return 0, 0

    urls = []
    for line in feed_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)

    created = 0
    for url in dict.fromkeys(urls):
        nome = urlsplit(url).netloc or url
        _, was_created = FonteRSS.objects.get_or_create(
            url=url,
            defaults={"nome": nome, "confiabilidade": 0.5, "ativo": True},
        )
        if was_created:
            created += 1

    logger.info("Feeds sincronizados: %d novo(s), %d no arquivo", created, len(urls))
    return created, len(urls)


def get_active_feed_urls() -> list[str]:
    urls = list(
        FonteRSS.objects.filter(ativo=True).values_list("url", flat=True)
    )
    if urls:
        return urls

    # Fallback para o arquivo caso o banco ainda não tenha sido populado.
    sync_feeds_from_file()
    return list(
        FonteRSS.objects.filter(ativo=True).values_list("url", flat=True)
    )


def collect_feed(
    url: str,
    *,
    within_days: int | None = None,
    max_entries: int | None = None,
) -> FeedResult:
    """Coleta um feed e grava as notícias cruas. Não executa o pipeline."""
    result = FeedResult(url=url)
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=within_days)
        if within_days is not None
        else None
    )

    try:
        parsed = create_parser(url).fetch()
    except Exception as exc:
        logger.exception("Falha ao buscar feed %s", url)
        result.erros += 1
        result.erro = str(exc)
        return result

    result.feed_url = parsed.get("href") or url
    entries = parsed.get("entries", [])
    if max_entries is not None:
        entries = entries[:max_entries]
    result.entries = len(entries)

    for entry in entries:
        published = _as_utc(entry.get("published"))
        if cutoff and published < cutoff:
            result.antigas += 1
            continue

        link = normalize_link(entry.get("link") or entry.get("id") or "")
        if not link:
            result.invalidas += 1
            continue

        title = (entry.get("title") or "").strip()
        description = (entry.get("description") or "").strip()
        content = (entry.get("content") or "").strip()
        max_desc = getattr(settings, "ARTICLE_DESCRIPTION_MAX_CHARS", 1000)
        max_content = getattr(settings, "ARTICLE_CONTENT_MAX_CHARS", 20000)
        description = description[:max_desc]
        content = content[:max_content]
        if not description and content:
            description = content[:500]

        now = datetime.now(timezone.utc)
        defaults = {
            "titulo": title,
            "descricao": description,
            "conteudo": content,
            "publicado_em": published,
            "coletado_em": now,
            "feed_url": result.feed_url,
            "impacto": "pendente",
            "raw_data": _safe_raw_data(entry.get("raw")),
            "relevancia_binaria": False,
        }

        try:
            with transaction.atomic():
                _, created = Noticia.objects.get_or_create(
                    link=link, defaults=defaults
                )
        except IntegrityError:
            # Corrida com outro coletor: a URL já existe.
            result.duplicadas += 1
            continue
        except Exception:
            logger.exception("Falha ao salvar notícia %s", link)
            result.erros += 1
            continue

        if created:
            result.criadas += 1
        else:
            result.duplicadas += 1

    logger.info(
        "Feed %s: %d entrada(s), %d nova(s), %d duplicada(s), %d antiga(s), %d erro(s)",
        url,
        result.entries,
        result.criadas,
        result.duplicadas,
        result.antigas,
        result.erros,
    )
    return result


def collect_all(
    feed_urls: list[str] | None = None,
    *,
    within_days: int | None = None,
    max_entries: int | None = None,
) -> CollectionResult:
    urls = feed_urls if feed_urls is not None else get_active_feed_urls()
    result = CollectionResult()
    for url in urls:
        result.feeds.append(
            collect_feed(url, within_days=within_days, max_entries=max_entries)
        )
    logger.info(
        "Coleta concluída: %d feed(s), %d nova(s), %d duplicada(s), %d erro(s)",
        len(result.feeds),
        result.criadas,
        result.duplicadas,
        result.erros,
    )
    return result


def collect_configured_feeds(
    *,
    within_days: int | None = None,
    max_entries: int | None = None,
) -> CollectionResult:
    sync_feeds_from_file()
    return collect_all(within_days=within_days, max_entries=max_entries)
