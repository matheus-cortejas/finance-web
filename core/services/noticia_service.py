from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from core.models import Alerta, Ativo, Carteira, Noticia
from core.llm.relevance import is_relevant
from core.parsers.factory import create_parser


logger = logging.getLogger("services.noticia_service")


def _parse_date(entry) -> datetime:
    published = entry.get("published")
    if isinstance(published, datetime):
        return published
    return datetime.now(timezone.utc)


def _find_matches_in_text(text: str, watch_terms: dict) -> list[tuple[str, str]]:
    text_lower = text.lower()
    matches = []
    for code, meta in watch_terms.items():
        name = meta.get("name", "")
        if re.search(r"\b" + re.escape(code.lower()) + r"\b", text_lower):
            matches.append((code, name))
            continue
        if name and name.lower() in text_lower:
            matches.append((code, name))
    return matches


def _unique_matches(*match_groups: list[tuple[str, str]]) -> list[tuple[str, str]]:
    unique = []
    seen_codes = set()
    for group in match_groups:
        for code, name in group:
            if code in seen_codes:
                continue
            seen_codes.add(code)
            unique.append((code, name))
    return unique


def seen_article(link: str) -> bool:
    return Noticia.objects.filter(link=link).exists()


def mark_article_seen(link: str, published_ts: int | None = None) -> None:
    published_at = datetime.fromtimestamp(published_ts, tz=timezone.utc) if published_ts is not None else None
    Noticia.objects.get_or_create(
        link=link,
        defaults={
            "titulo": "",
            "descricao": "",
            "publicado_em": published_at,
            "feed_url": "",
            "impacto": "pendente",
        },
    )


def save_article(
    link: str,
    title: str,
    description: str,
    published_ts: int | None = None,
    feed_url: str | None = None,
) -> int | None:
    published_at = datetime.fromtimestamp(published_ts, tz=timezone.utc) if published_ts is not None else None
    article, _ = Noticia.objects.update_or_create(
        link=link,
        defaults={
            "titulo": title,
            "descricao": description,
            "publicado_em": published_at,
            "feed_url": feed_url or "",
            "impacto": "pendente",
        },
    )
    return article.id


def link_article_match(article_id: int, asset_id: int) -> None:
    article = Noticia.objects.filter(id=article_id).first()
    asset = Ativo.objects.filter(id=asset_id).first()
    if not article or not asset:
        return

    for carteira in Carteira.objects.filter(ativos=asset).select_related("usuario"):
        Alerta.objects.get_or_create(usuario=carteira.usuario, noticia=article, ativo=asset)


def check_feeds_and_report(feed_urls, watch_assets, within_days=None):
    watch_terms = {asset["code"]: {"name": asset.get("name", ""), "id": asset.get("id")} for asset in watch_assets}
    cutoff = None
    if within_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)

    reports = []
    for url in feed_urls:
        logger.info("Coletando feed RSS: %s", url)
        parser = create_parser(url)
        parsed = parser.fetch()
        feed_url = parsed.get("href", url)
        entries = parsed.get("entries", [])
        logger.debug("Feed %s retornou %d entrie(s)", feed_url, len(entries))
        for entry in entries:
            published = _parse_date(entry)
            if cutoff and published < cutoff:
                logger.debug("Ignorando artigo antigo: %s", entry.get("link") or entry.get("title") or "sem-link")
                continue
            link = entry.get("link") or ""
            if not link or seen_article(link):
                logger.debug("Ignorando artigo já visto ou sem link: %s", link or entry.get("title") or "sem-link")
                continue

            title = entry.get("title", "") or ""
            description = entry.get("description", "") or entry.get("summary", "") or ""
            content = " ".join(entry.get("content", [])) if entry.get("content") else ""
            title_matches = _find_matches_in_text(title, watch_terms)
            description_matches = _find_matches_in_text(description, watch_terms) if description else []
            content_matches = _find_matches_in_text(content, watch_terms) if content else []
            matches = _unique_matches(title_matches, description_matches, content_matches)

            if description_matches and not title_matches:
                logger.debug(
                    "Menção apenas na descrição, encaminhando para IA: %s | %s",
                    title,
                    [code for code, _ in description_matches],
                )

            if content_matches and not title_matches:
                logger.debug(
                    "Menção apenas no conteúdo, encaminhando para IA: %s | %s",
                    title,
                    [code for code, _ in content_matches],
                )

            if not matches:
                logger.debug("Nenhuma correspondência local para artigo: %s", title)

            mark_article_seen(link, int(published.timestamp()))
            article_id = save_article(link, title, description or content, int(published.timestamp()), feed_url)
            if not matches or not article_id:
                logger.debug("Artigo persistido sem alerta: %s", title)
                continue

            if not title_matches:
                logger.debug("Menção fora do título, artigo persistido sem alerta: %s", title)
                continue

            assets_for_llm = [{"id": watch_terms[code].get("id"), "code": code, "name": name} for code, name in matches]
            logger.info(
                "Enviando artigo para avaliacao da IA: title=%s matches=%s assets_for_llm=%s",
                title,
                [code for code, _ in matches],
                [asset.get("code") for asset in assets_for_llm],
            )
            ai_result = is_relevant(title, description, content, assets_for_llm)
            logger.info("Resultado da avaliacao IA: relevant=%s matched=%s reason=%s", ai_result.get("relevant"), ai_result.get("matched"), ai_result.get("reason", ""))
            if not ai_result.get("relevant"):
                logger.info("Artigo rejeitado pela relevância: %s | %s", title, ai_result.get("reason", ""))
                continue

            local_codes = {code for code, _ in matches}
            matched_codes = [code for code in (ai_result.get("matched") or [code for code, _ in matches]) if code in watch_terms]
            matched_codes = [code for code in matched_codes if code in local_codes]
            if not matched_codes:
                logger.warning("IA sinalizou relevância sem coincidência local: %s | %s", title, ai_result.get("matched", []))
                continue

            for code in set(matched_codes):
                asset_id = watch_terms[code].get("id")
                if asset_id is None:
                    continue
                link_article_match(article_id, asset_id)
                logger.info("Alerta persistido: title=%s codigo=%s asset_id=%s", title, code, asset_id)

            reports.append(
                {
                    "published": published.isoformat(),
                    "title": title,
                    "link": link,
                    "matches": [(code, watch_terms.get(code, {}).get("name")) for code in matched_codes],
                    "reason": ai_result.get("reason", ""),
                }
            )
    return reports