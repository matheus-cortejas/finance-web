from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render

from core.models import Alerta, Ativo, Carteira
logger = logging.getLogger("views")


def _get_or_create_carteira(user) -> Carteira:
    carteira, _ = Carteira.objects.get_or_create(usuario=user)
    return carteira


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
    asset_matches = []

    if request.method == "POST":
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
        .select_related("ativo", "noticia")
        .order_by("-created_at")[:8]
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
        },
    )


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    return redirect("login")