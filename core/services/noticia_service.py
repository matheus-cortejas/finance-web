from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings

from core.models import (
    Alerta,
    Ativo,
    Carteira,
    FonteRSS,
    Noticia,
    NoticiaClassificacao,
    NoticiaScore,
    PerfilInvestidor,
)
from core.llm.relevance import is_relevant
from core.llm.openai_client import classify_article, summarize_article
from core.parsers.factory import create_parser
from core.services.scoring_service import calculate_relevance_score, is_priority_at_least


logger = logging.getLogger("services.noticia_service")


def _parse_date(entry) -> datetime:
    published = entry.get("published")
    if isinstance(published, datetime):
        return published
    return datetime.now(timezone.utc)


# Expressões regulares e constantes
_TAG_RE = re.compile(r"<[^>]+>")
_CODE_LETTERS_RE = re.compile(r"\d+")
_TRACKING_PARAMS = {
    "fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "mkt_tok",
    "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
}


def _normalize_link(link: str) -> str:
    """Remove parâmetros de tracking da URL."""
    if not link:
        return ""
    try:
        parts = urlsplit(link)
    except Exception:
        return link
    if not parts.scheme or not parts.netloc:
        return link
    query_items = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(query_items, doseq=True)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, query, ""))


def _safe_raw_data(raw_entry) -> dict | None:
    if raw_entry is None:
        return None
    try:
        json.dumps(raw_entry)
        return raw_entry
    except TypeError:
        return json.loads(json.dumps(raw_entry, default=str))


def _code_aliases(code: str) -> list[str]:
    """Retorna possíveis aliases para um ticker (ex: PETR4 -> PETR)."""
    if not code:
        return []
    letters_only = _CODE_LETTERS_RE.sub("", code).strip()
    if len(letters_only) >= 4 and letters_only.upper() != code.upper():
        return [letters_only]
    return []


def _find_matches_in_text(text: str, watch_terms: dict) -> list[tuple[str, str]]:
    """Busca tickers ou nomes de empresas no texto (match superficial)."""
    text_lower = text.lower()
    matches = []
    for code, meta in watch_terms.items():
        name = meta.get("name", "")
        if re.search(r"\b" + re.escape(code.lower()) + r"\b", text_lower):
            matches.append((code, name))
            continue
        if name and name.lower() in text_lower:
            matches.append((code, name))
            continue
        for alias in _code_aliases(code):
            if re.search(r"\b" + re.escape(alias.lower()) + r"\b", text_lower):
                matches.append((code, name))
                break
    return matches


def _unique_matches(*match_groups: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Junta matches de várias fontes removendo duplicatas."""
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


def mark_article_seen(link: str, published_ts: int | None = None, raw_data: dict | None = None) -> None:
    published_at = datetime.fromtimestamp(published_ts, tz=timezone.utc) if published_ts is not None else None
    Noticia.objects.get_or_create(
        link=link,
        defaults={
            "titulo": "",
            "descricao": "",
            "publicado_em": published_at,
            "feed_url": "",
            "impacto": "pendente",
            "raw_data": raw_data,
        },
    )


def save_article(
    link: str,
    title: str,
    description: str,
    published_ts: int | None = None,
    feed_url: str | None = None,
    raw_data: dict | None = None,
    content: str | None = None,          # NOVO: parâmetro para conteúdo limpo
) -> int | None:
    published_at = datetime.fromtimestamp(published_ts, tz=timezone.utc) if published_ts is not None else None
    defaults = {
        "titulo": title,
        "descricao": description,
        "publicado_em": published_at,
        "feed_url": feed_url or "",
        "impacto": "pendente",
        "raw_data": raw_data,
    }
    # Se o model tiver o campo 'conteudo', inclui (caso contrário, será ignorado pelo update_or_create)
    if content is not None and hasattr(Noticia, 'conteudo'):
        defaults["conteudo"] = content

    article, _ = Noticia.objects.update_or_create(link=link, defaults=defaults)
    return article.id


def link_article_match(article_id: int, asset_id: int) -> None:
    article = Noticia.objects.filter(id=article_id).first()
    asset = Ativo.objects.filter(id=asset_id).first()
    if not article or not asset:
        return

    for carteira in Carteira.objects.filter(ativos=asset).select_related("usuario"):
        Alerta.objects.get_or_create(usuario=carteira.usuario, noticia=article, ativo=asset)


def _ensure_article_summary(article_id: int, title: str, description: str, content: str) -> None:
    article = Noticia.objects.filter(id=article_id).first()
    if not article:
        return
    if article.resumo:
        return

    summary_result = summarize_article(title, description, content)
    summary_text = (summary_result.get("summary") or "").strip()
    article.resumo = summary_text
    article.resumo_status = summary_result.get("status", "ok")
    article.resumo_provider = summary_result.get("provider", "")
    article.resumo_em = datetime.now(timezone.utc)
    article.save(update_fields=["resumo", "resumo_status", "resumo_provider", "resumo_em"])


def _ensure_article_classification(
    article_id: int,
    title: str,
    description: str,
    content: str,
    assets: list | None = None,
) -> NoticiaClassificacao | None:
    return _ensure_article_classification_force(
        article_id, title, description, content, assets=assets, force=False
    )


def _ensure_article_classification_force(
    article_id: int,
    title: str,
    description: str,
    content: str,
    assets: list | None = None,
    force: bool = False,
) -> NoticiaClassificacao | None:
    if not settings.ENABLE_STRUCTURED_CLASSIFICATION and not force:
        return None

    article = Noticia.objects.filter(id=article_id).first()
    if not article:
        return None

    existing = NoticiaClassificacao.objects.filter(noticia=article).first()
    if existing:
        return existing

    classification = classify_article(title, description, content, assets or [])
    classificacao, _ = NoticiaClassificacao.objects.update_or_create(
        noticia=article,
        defaults={
            "sentimento": classification.get("sentimento", "neutro"),
            "impacto": classification.get("impacto", "medio"),
            "urgencia": classification.get("urgencia", "media"),
            "setor": classification.get("setor", ""),
            "tipo_evento": classification.get("tipo_evento", "outro"),
            "tickers_relacionados": classification.get("tickers_relacionados", []),
            "relevancia_llm": classification.get("relevancia_llm", 0.0),
            "provider": classification.get("provider", ""),
            "status": classification.get("status", "ok"),
        },
    )
    return classificacao


def _get_fonte_confiabilidade(feed_url: str | None) -> float | None:
    if not feed_url:
        return None
    fonte = FonteRSS.objects.filter(url__iexact=feed_url).first()
    if not fonte:
        return None
    return fonte.confiabilidade


def _score_and_alert_users(
    article: Noticia,
    matched_asset_ids: list[int],
    classification: NoticiaClassificacao | None,
    feed_url: str | None,
) -> None:
    if not matched_asset_ids or not classification:
        return

    asset_id_set = set(matched_asset_ids)
    carteiras = (
        Carteira.objects.filter(ativos__in=matched_asset_ids)
        .select_related("usuario")
        .prefetch_related("ativos")
        .distinct()
    )
    if not carteiras:
        return

    perfis = {
        perfil.usuario_id: perfil
        for perfil in PerfilInvestidor.objects.filter(usuario__in=[carteira.usuario for carteira in carteiras])
    }
    fonte_confiabilidade = _get_fonte_confiabilidade(feed_url)

    for carteira in carteiras:
        usuario = carteira.usuario
        perfil = perfis.get(usuario.id)
        carteira_assets = [asset for asset in carteira.ativos.all() if asset.id in asset_id_set]
        carteira_tickers = [asset.ticker for asset in carteira_assets]

        score_data = calculate_relevance_score(
            classification,
            perfil=perfil,
            carteira_tickers=carteira_tickers,
            fonte_confiabilidade=fonte_confiabilidade,
        )
        NoticiaScore.objects.update_or_create(
            noticia=article,
            usuario=usuario,
            defaults={
                "score_final": score_data["score_final"],
                "prioridade": score_data["prioridade"],
                "motivos": score_data["motivos"],
            },
        )
        logger.info(
            "Score calculado: noticia_id=%s usuario_id=%s prioridade=%s score=%s",
            article.id,
            usuario.id,
            score_data["prioridade"],
            score_data["score_final"],
        )

        min_priority = settings.ALERT_MIN_PRIORITY
        if perfil and getattr(perfil, "alerta_min_prioridade", None):
            min_priority = perfil.alerta_min_prioridade

        if not is_priority_at_least(score_data["prioridade"], min_priority):
            continue

        for asset in carteira_assets:
            Alerta.objects.get_or_create(usuario=usuario, noticia=article, ativo=asset)
            logger.info(
                "Alerta criado por prioridade: noticia_id=%s usuario_id=%s ativo_id=%s",
                article.id,
                usuario.id,
                asset.id,
            )


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

            raw_link = entry.get("link") or entry.get("id") or ""
            link = _normalize_link(raw_link)
            if not link or seen_article(link):
                logger.debug("Ignorando artigo já visto ou sem link: %s", link or entry.get("title") or "sem-link")
                continue

            # O parser já retorna texto limpo (sem HTML, sem entidades)
            title = (entry.get("title") or "").strip()
            description_full = (entry.get("description") or "").strip()
            content_full = (entry.get("content") or "").strip()      # string, não lista

            # Fallback: se descrição estiver vazia, usa o início do conteúdo
            if not description_full and content_full:
                description_full = content_full[:500]

            # Trunca conforme configuração
            description = description_full[:settings.ARTICLE_DESCRIPTION_MAX_CHARS] if description_full else ""
            content = content_full[:settings.ARTICLE_CONTENT_MAX_CHARS] if content_full else ""

            # Log para debug (pode ser removido em produção)
            logger.debug(
                "Artigo: title=%s, desc_len=%d, content_len=%d, link=%s",
                title, len(description), len(content), link
            )

            # Matches superficiais (ticker, nome, alias)
            title_matches = _find_matches_in_text(title, watch_terms)
            description_matches = _find_matches_in_text(description_full, watch_terms) if description_full else []
            content_matches = _find_matches_in_text(content_full, watch_terms) if content_full else []
            matches = _unique_matches(title_matches, description_matches, content_matches)

            if description_matches and not title_matches:
                logger.debug("Menção apenas na descrição: %s | %s", title, [c for c, _ in description_matches])
            if content_matches and not title_matches:
                logger.debug("Menção apenas no conteúdo: %s | %s", title, [c for c, _ in content_matches])
            if not matches:
                logger.debug("Nenhuma correspondência local para artigo: %s", title)

            # Persiste a notícia mesmo sem matches (apenas para histórico)
            raw_data = _safe_raw_data(entry.get("raw"))
            mark_article_seen(link, int(published.timestamp()), raw_data=raw_data)
            article_id = save_article(
                link=link,
                title=title,
                description=description or content,   # se desc vazia, usa conteúdo
                published_ts=int(published.timestamp()),
                feed_url=feed_url,
                raw_data=raw_data,
                content=content,                      # salva conteúdo limpo (se campo existir)
            )

            if not matches or not article_id:
                logger.debug("Artigo persistido sem alerta: %s", title)
                continue

            if not title_matches:
                logger.debug("Menção fora do título, validando com IA: %s", title)

            assets_for_llm = [
                {"id": watch_terms[code].get("id"), "code": code, "name": name}
                for code, name in matches
            ]
            logger.info(
                "Enviando artigo para avaliacao da IA: title=%s matches=%s",
                title, [code for code, _ in matches]
            )

            # LLM barata para relevância binária
            ai_result = is_relevant(title, description, content, assets_for_llm)
            logger.info(
                "Resultado IA: relevant=%s matched=%s reason=%s",
                ai_result.get("relevant"), ai_result.get("matched"), ai_result.get("reason", "")
            )

            if not ai_result.get("relevant"):
                logger.info("Artigo rejeitado pela relevância: %s | %s", title, ai_result.get("reason", ""))
                continue

            # Filtra apenas os códigos que realmente deram match local
            local_codes = {code for code, _ in matches}
            matched_codes = [
                code for code in (ai_result.get("matched") or [code for code, _ in matches])
                if code in watch_terms and code in local_codes
            ]
            if not matched_codes:
                logger.warning("IA sinalizou relevância sem coincidência local: %s | %s", title, ai_result.get("matched", []))
                continue

            # Gera resumo e classificação estruturada
            _ensure_article_summary(article_id, title, description, content)

            matched_asset_ids = [
                watch_terms[code].get("id")
                for code in matched_codes
                if watch_terms[code].get("id") is not None
            ]

            classification = None
            if settings.ENABLE_PRIORITY_ENGINE:
                classification = _ensure_article_classification_force(
                    article_id, title, description, content,
                    assets=assets_for_llm, force=True
                )
                article = Noticia.objects.filter(id=article_id).first()
                if article:
                    _score_and_alert_users(article, matched_asset_ids, classification, feed_url)
            else:
                _ensure_article_classification(article_id, title, description, content, assets_for_llm)
                for code in set(matched_codes):
                    asset_id = watch_terms[code].get("id")
                    if asset_id is None:
                        continue
                    link_article_match(article_id, asset_id)
                    logger.info("Alerta persistido: title=%s codigo=%s asset_id=%s", title, code, asset_id)

            reports.append({
                "published": published.isoformat(),
                "title": title,
                "link": link,
                "matches": [(code, watch_terms.get(code, {}).get("name")) for code in matched_codes],
                "reason": ai_result.get("reason", ""),
            })

    return reports