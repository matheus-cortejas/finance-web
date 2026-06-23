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
from core.intelligent_motor.pipeline_orchestrator import processar_noticia_completa
from core.intelligent_motor.fase6_decisor.pipeline import decidir_alerta
from core.intelligent_motor.config_loader import load_global_config
from core.parsers.factory import create_parser

logger = logging.getLogger("services.noticia_service")

# ============================================================================
# Funções auxiliares (mantidas do código original)
# ============================================================================

PRIORITY_ORDER = ["baixa", "media", "alta", "critica"]

def is_priority_at_least(priority: str, minimum: str) -> bool:
    try:
        return PRIORITY_ORDER.index(priority) >= PRIORITY_ORDER.index(minimum)
    except ValueError:
        return False

def _parse_date(entry) -> datetime:
    published = entry.get("published")
    if isinstance(published, datetime):
        return published
    return datetime.now(timezone.utc)

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

_TRACKING_PARAMS = {
    "fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "mkt_tok",
    "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
}

def _safe_raw_data(raw_entry) -> dict | None:
    if raw_entry is None:
        return None
    try:
        json.dumps(raw_entry)
        return raw_entry
    except TypeError:
        return json.loads(json.dumps(raw_entry, default=str))

def seen_article(link: str) -> bool:
    return Noticia.objects.filter(link=link).exists()

def _get_all_tickers() -> list[str]:
    """Retorna todos os tickers cadastrados no sistema."""
    return list(Ativo.objects.values_list('ticker', flat=True))

def _convert_perfil(perfil: PerfilInvestidor) -> dict:
    """Converte o modelo PerfilInvestidor para o formato esperado pela fase 6."""
    canais_habilitados = []
    if perfil.notificacao_email:
        canais_habilitados.append("email")
    if perfil.notificacao_push:
        canais_habilitados.append("push")
    if perfil.notificacao_dashboard:
        canais_habilitados.append("dashboard")
    if not canais_habilitados:
        canais_habilitados = ["dashboard"]
    categorias_permitidas = []
    if hasattr(perfil, 'notificar_apenas_categorias') and perfil.notificar_apenas_categorias:
        categorias_permitidas = perfil.notificar_apenas_categorias
    return {
        "canais_habilitados": canais_habilitados,
        "categorias_permitidas": categorias_permitidas,
    }

# ============================================================================
# Função principal de processamento
# ============================================================================

def check_feeds_and_report(feed_urls, watch_assets=None, within_days=None):
    """
    Coleta feeds, processa usando o pipeline inteligente e gera alertas.
    O parâmetro watch_assets é ignorado (mantido apenas para compatibilidade com chamadas antigas).
    """
    config = load_global_config()

    all_tickers = _get_all_tickers()
    if not all_tickers:
        logger.warning("Nenhum ativo cadastrado para monitoramento.")
        all_tickers = []

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
                logger.debug("Ignorando artigo antigo")
                continue

            raw_link = entry.get("link") or entry.get("id") or ""
            link = _normalize_link(raw_link)
            if not link or seen_article(link):
                logger.debug("Ignorando artigo já visto ou sem link")
                continue

            title = (entry.get("title") or "").strip()
            description_full = (entry.get("description") or "").strip()
            content_full = (entry.get("content") or "").strip()
            if not description_full and content_full:
                description_full = content_full[:500]

            description = description_full[:settings.ARTICLE_DESCRIPTION_MAX_CHARS] if description_full else ""
            content = content_full[:settings.ARTICLE_CONTENT_MAX_CHARS] if content_full else ""

            noticia_dict = {
                "id": None,
                "titulo": title,
                "descricao": description,
                "conteudo": content,
                "link": link,
            }

            try:
                pipeline_result = processar_noticia_completa(
                    noticia=noticia_dict,
                    carteira_usuario=all_tickers,
                )
            except Exception as e:
                logger.exception("Erro no pipeline para %s: %s", title, e)
                continue

            raw_data = _safe_raw_data(entry.get("raw"))
            published_ts = int(published.timestamp())
            article = _save_article_with_pipeline_result(
                link=link, title=title, description=description,
                content=content, published_ts=published_ts,
                feed_url=feed_url, raw_data=raw_data,
                pipeline_result=pipeline_result,
            )
            if not article:
                continue

            if not pipeline_result.get("relevancia_binaria"):
                logger.info("Notícia irrelevante: %s", title)
                continue

            tickers_relacionados = pipeline_result.get("tickers_relacionados", [])
            if not tickers_relacionados:
                logger.info("Nenhum ticker relacionado: %s", title)
                continue

            asset_ids = list(Ativo.objects.filter(ticker__in=tickers_relacionados).values_list('id', flat=True))
            if not asset_ids:
                logger.info("Nenhum ativo cadastrado para os tickers relacionados: %s", tickers_relacionados)
                continue

            # Usuários que possuem pelo menos um dos ativos
            carteiras = Carteira.objects.filter(ativos__in=asset_ids).distinct()
            perfis = {p.usuario_id: p for p in PerfilInvestidor.objects.filter(
                usuario__in=[c.usuario_id for c in carteiras]
            )}

            for carteira in carteiras:
                usuario = carteira.usuario
                perfil = perfis.get(usuario.id)
                perfil_dict = _convert_perfil(perfil) if perfil else None

                # Fase 6
                try:
                    decision = decidir_alerta(
                        noticia=pipeline_result,
                        perfil=perfil_dict,
                    )
                except Exception as e:
                    logger.exception("Erro na fase 6 para usuário %s: %s", usuario.id, e)
                    continue

                prioridade = decision.get("prioridade", "baixa")
                acoes = decision.get("acao_sugerida", [])
                score_final = decision.get("score_final", 0.0)
                explicacao_regra = decision.get("explicacao_regra", "")

                # Salva score personalizado
                NoticiaScore.objects.update_or_create(
                    noticia=article,
                    usuario=usuario,
                    defaults={
                        "score_final": score_final,
                        "prioridade": prioridade,
                        "motivos": {"explicacao_regra": explicacao_regra, "acoes": acoes},
                    },
                )

                min_priority = getattr(settings, "ALERT_MIN_PRIORITY", "media")
                if perfil and hasattr(perfil, "alerta_min_prioridade"):
                    min_priority = perfil.alerta_min_prioridade

                if is_priority_at_least(prioridade, min_priority):
                    user_assets = Ativo.objects.filter(
                        carteiras__usuario=usuario,
                        id__in=asset_ids
                    )

                    # Cria um único alerta por (usuário, notícia)
                    alerta, created = Alerta.objects.get_or_create(
                        usuario=usuario,
                        noticia=article
                    )
                    # Associa todos os ativos da carteira que aparecem na notícia
                    if user_assets.exists():
                        alerta.ativos.add(*user_assets)
                        logger.info(
                            "Alerta %s: noticia_id=%s usuario_id=%s ativos=%s",
                            "criado" if created else "já existia",
                            article.id,
                            usuario.id,
                            list(user_assets.values_list('ticker', flat=True))
                        )

            reports.append({
                "published": published.isoformat(),
                "title": title,
                "link": link,
                "matches": [(ticker, "") for ticker in tickers_relacionados],
                "reason": pipeline_result.get("explicacao", ""),
            })

    return reports

def _save_article_with_pipeline_result(link, title, description, content, published_ts, feed_url, raw_data, pipeline_result):
    """Salva a notícia e seus metadados enriquecidos pelo pipeline."""
    published_at = datetime.fromtimestamp(published_ts, tz=timezone.utc) if published_ts else None
    defaults = {
        "titulo": title,
        "descricao": description,
        "publicado_em": published_at,
        "feed_url": feed_url or "",
        "impacto": pipeline_result.get("impacto", "pendente"),
        "raw_data": raw_data,
        "conteudo": content if hasattr(Noticia, 'conteudo') else None,
        "relevancia_binaria": pipeline_result.get("relevancia_binaria", False),
    }
    # Campos adicionais que podem ser salvos diretamente na notícia (se existirem no modelo)
    extra_fields = [
        "relevancia_global", "score_heuristico", "sentimento", "urgencia", "categoria", "explicacao"
    ]
    for field in extra_fields:
        if field in pipeline_result and hasattr(Noticia, field):
            defaults[field] = pipeline_result[field]

    article, _ = Noticia.objects.update_or_create(link=link, defaults=defaults)

    # Salva classificação estruturada (NoticiaClassificacao)
    if pipeline_result.get("sentimento"):
        # Mapeia urgencia (int) para string (se necessário)
        urgencia_int = pipeline_result.get("urgencia", 5)
        if urgencia_int >= 7:
            urgencia_str = "alta"
        elif urgencia_int >= 4:
            urgencia_str = "media"
        else:
            urgencia_str = "baixa"

        # Prepara os dados para update_or_create
        classificacao_defaults = {
            "sentimento": pipeline_result.get("sentimento", "neutro"),
            "impacto": pipeline_result.get("impacto", "medio"),
            "urgencia": urgencia_str,
            "setor": pipeline_result.get("categoria", ""),
            "tipo_evento": "noticia",
            "tickers_relacionados": pipeline_result.get("tickers_relacionados", []),
            "tickers_encontrados": pipeline_result.get("tickers_encontrados", []),   # NOVO
            "explicacao": pipeline_result.get("explicacao", ""),                     # NOVO
            "relevancia_llm": pipeline_result.get("relevancia_global", 0.0),
            "confianca_fase4": pipeline_result.get("confianca_fase4", 0.0),          # NOVO
            "provider_fase4": pipeline_result.get("provider_fase4", ""),             # NOVO
            "provider": "motor_inteligente",
            "status": "ok",
        }
        NoticiaClassificacao.objects.update_or_create(
            noticia=article,
            defaults=classificacao_defaults
        )

    # (O resumo pode ser gerado posteriormente, se necessário)
    return article