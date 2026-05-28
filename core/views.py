from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render

from core.forms import PerfilInvestidorForm
from core.models import (
    Alerta,
    Ativo,
    Carteira,
    InteracaoNoticia,
    Noticia,
    NoticiaClassificacao,
    NoticiaScore,
    PerfilInvestidor,
)
from core.services.interacao_service import update_profile_from_interactions
logger = logging.getLogger("views")


_PRIORITY_BADGES = {
    "critica": "text-bg-danger",
    "alta": "text-bg-warning",
    "media": "text-bg-info",
    "baixa": "text-bg-secondary",
}
_SENTIMENT_BADGES = {
    "positivo": "text-bg-success",
    "negativo": "text-bg-danger",
    "neutro": "text-bg-secondary",
}


def _priority_badge(priority: str) -> str:
    return _PRIORITY_BADGES.get(priority, "text-bg-secondary")


def _sentiment_badge(sentiment: str) -> str:
    return _SENTIMENT_BADGES.get(sentiment, "text-bg-secondary")


def _format_motivos(motivos: dict | None) -> str:
    if not motivos:
        return "Sem detalhes"

    parts = []
    if "base" in motivos:
        parts.append(f"Base {motivos.get('base')}")
    if "impacto" in motivos:
        parts.append(f"Impacto {motivos.get('impacto')}")
    if "urgencia" in motivos:
        parts.append(f"Urgencia {motivos.get('urgencia')}")
    if "sentimento" in motivos:
        parts.append(f"Sentimento {motivos.get('sentimento')}")
    if "ticker_match" in motivos:
        parts.append("Ticker match sim" if motivos.get("ticker_match") else "Ticker match nao")
    if "setor_match" in motivos:
        parts.append("Setor match sim" if motivos.get("setor_match") else "Setor match nao")
    if "raw_score" in motivos:
        parts.append(f"Raw {motivos.get('raw_score')}")
    if "carteira_tickers" in motivos:
        tickers = ",".join(motivos.get("carteira_tickers") or [])
        if tickers:
            parts.append(f"Carteira {tickers}")

    return " | ".join(parts) if parts else "Sem detalhes"


def _get_or_create_carteira(user) -> Carteira:
    carteira, _ = Carteira.objects.get_or_create(usuario=user)
    return carteira


def _get_or_create_perfil(user) -> PerfilInvestidor:
    perfil, _ = PerfilInvestidor.objects.get_or_create(usuario=user)
    return perfil


def _serialize_asset(asset: Ativo) -> dict:
    return {
        "id": asset.id,
        "ticker": asset.ticker,
        "nome": asset.nome,
        "source": asset.source,
    }


def _find_asset_suggestions(term: str, limit: int = 8) -> list[Ativo]:
    term = term.strip()
    if not term:
        return []

    return list(
        Ativo.objects.filter(Q(ticker__istartswith=term) | Q(nome__istartswith=term)).distinct().order_by("ticker")[:limit]
    )


@login_required
def asset_suggestions(request):
    term = request.GET.get("q", "").strip()
    assets = _find_asset_suggestions(term)
    return JsonResponse({"results": [_serialize_asset(asset) for asset in assets]})


@login_required
def dashboard(request):
    carteira = _get_or_create_carteira(request.user)
    perfil = _get_or_create_perfil(request.user)
    perfil_form = PerfilInvestidorForm(instance=perfil)
    asset_matches = []

    if request.method == "POST":
        if request.POST.get("update_profile"):
            perfil_form = PerfilInvestidorForm(request.POST, instance=perfil)
            if perfil_form.is_valid():
                perfil_form.save()
                messages.success(request, "Perfil atualizado com sucesso.")
                return redirect("dashboard")
            messages.warning(request, "Verifique os campos do perfil.")
        else:
            remove_asset_id = request.POST.get("remove_asset_id", "").strip()
            if remove_asset_id:
                asset = Ativo.objects.filter(pk=remove_asset_id).first()
                if asset and carteira.ativos.filter(pk=asset.pk).exists():
                    carteira.ativos.remove(asset)
                    logger.info("Ativo removido da carteira: user=%s ticker=%s", request.user.username, asset.ticker)
                    messages.success(request, f"{asset.ticker} removido da sua carteira.")
                else:
                    logger.warning(
                        "Tentativa de remover ativo inexistente ou não vinculado: user=%s asset_id=%s",
                        request.user.username,
                        remove_asset_id,
                    )
                    messages.warning(request, "O ativo informado não está vinculado à sua carteira.")
                return redirect("dashboard")

            asset_term = request.POST.get("asset_term", "").strip()
            logger.info("Dashboard recebeu busca de ativo: user=%s termo=%s", request.user.username, asset_term or "<vazio>")
            if asset_term:
                matches = list(
                    Ativo.objects.filter(Q(ticker__icontains=asset_term) | Q(nome__icontains=asset_term)).distinct()
                )
                if len(matches) == 1:
                    asset = matches[0]
                    carteira.ativos.add(asset)
                    logger.info("Ativo associado à carteira: user=%s ticker=%s", request.user.username, asset.ticker)
                    messages.success(request, f"{asset.ticker} adicionado à sua carteira.")
                    return redirect("dashboard")
                if len(matches) > 1:
                    logger.info(
                        "Busca retornou múltiplos ativos: user=%s termo=%s total=%d",
                        request.user.username,
                        asset_term,
                        len(matches),
                    )
                    asset_matches = matches[:8]
                    messages.info(request, "Mais de um ativo encontrado. Selecione um resultado mais específico.")
                else:
                    logger.warning("Nenhum ativo encontrado na dashboard: user=%s termo=%s", request.user.username, asset_term)
                    messages.warning(request, "Nenhum ativo encontrado para esse termo.")
            else:
                logger.warning("Envio vazio de ativo na dashboard: user=%s", request.user.username)
                messages.warning(request, "Informe um código ou nome de ativo.")

    portfolio_assets = list(carteira.ativos.order_by("ticker"))
    recent_alerts = list(
        Alerta.objects.filter(usuario=request.user)
        .select_related("ativo", "noticia", "noticia__classificacao")
        .order_by("-created_at")[:8]
    )

    alert_scores = {
        score.noticia_id: score
        for score in NoticiaScore.objects.filter(
            usuario=request.user,
            noticia_id__in=[alert.noticia_id for alert in recent_alerts],
        )
    }
    for score in alert_scores.values():
        score.badge_class = _priority_badge(score.prioridade)
        score.priority_label = score.get_prioridade_display()

    for alert in recent_alerts:
        alert.score_for_user = alert_scores.get(alert.noticia_id)

    priority_filter = (request.GET.get("priority") or "").strip().lower()
    sector_filter = (request.GET.get("sector") or "").strip()
    score_queryset = (
        NoticiaScore.objects.filter(usuario=request.user)
        .select_related("noticia", "noticia__classificacao")
        .order_by("-score_final", "-calculado_em")
    )
    if priority_filter in _PRIORITY_BADGES:
        score_queryset = score_queryset.filter(prioridade=priority_filter)
    if sector_filter:
        score_queryset = score_queryset.filter(noticia__classificacao__setor__iexact=sector_filter)

    ranked_news = []
    for score in score_queryset[:12]:
        classificacao = getattr(score.noticia, "classificacao", None)
        sentimento = (getattr(classificacao, "sentimento", "") or "").lower()
        impacto = (getattr(classificacao, "impacto", "") or score.noticia.impacto or "").lower()
        urgencia = (getattr(classificacao, "urgencia", "") or "").lower()
        setor = getattr(classificacao, "setor", "") or ""
        ranked_news.append(
            {
                "noticia_id": score.noticia_id,
                "titulo": score.noticia.titulo or score.noticia.link,
                "link": score.noticia.link,
                "resumo": score.noticia.resumo,
                "publicado_em": score.noticia.publicado_em or score.calculado_em,
                "prioridade": score.prioridade,
                "prioridade_label": score.get_prioridade_display(),
                "prioridade_class": _priority_badge(score.prioridade),
                "score_final": score.score_final,
                "sentimento": sentimento,
                "sentimento_class": _sentiment_badge(sentimento),
                "impacto": impacto,
                "urgencia": urgencia,
                "setor": setor,
                "motivos_text": _format_motivos(score.motivos),
            }
        )

    sector_options = list(
        NoticiaClassificacao.objects.filter(noticia__scores__usuario=request.user)
        .exclude(setor="")
        .values_list("setor", flat=True)
        .distinct()
        .order_by("setor")
    )

    logger.debug(
        "Dashboard renderizada: user=%s ativos=%d alertas=%d",
        request.user.username,
        len(portfolio_assets),
        len(recent_alerts),
    )

    return render(
        request,
        "core/dashboard.html",
        {
            "carteira": carteira,
            "portfolio_assets": portfolio_assets,
            "recent_alerts": recent_alerts,
            "asset_matches": asset_matches,
            "perfil_form": perfil_form,
            "ranked_news": ranked_news,
            "priority_filter": priority_filter,
            "sector_filter": sector_filter,
            "priority_options": [key for key in _PRIORITY_BADGES.keys()],
            "sector_options": sector_options,
        },
    )


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    return redirect("login")


@login_required
def record_interaction(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method_not_allowed"}, status=405)

    noticia_id = (request.POST.get("noticia_id") or "").strip()
    action = (request.POST.get("acao") or "").strip().lower()
    origem = (request.POST.get("origem") or "dashboard").strip()
    tempo_leitura = request.POST.get("tempo_leitura")

    if not noticia_id or action not in {"abriu", "ignorou"}:
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)

    noticia = Noticia.objects.filter(id=noticia_id).first()
    if not noticia:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    interaction = InteracaoNoticia.objects.filter(usuario=request.user, noticia=noticia).first()
    created = False
    if not interaction:
        interaction = InteracaoNoticia(usuario=request.user, noticia=noticia)
        created = True

    if action == "abriu":
        interaction.abriu = True
    if action == "ignorou":
        interaction.ignorou = True

    if tempo_leitura:
        try:
            tempo = int(tempo_leitura)
        except ValueError:
            tempo = 0
        if tempo > 0 and tempo > interaction.tempo_leitura:
            interaction.tempo_leitura = tempo

    if origem:
        interaction.origem = origem

    interaction.save()
    update_profile_from_interactions(request.user)

    return JsonResponse({"ok": True, "created": created})