from __future__ import annotations

import sys
import logging

from django.conf import settings
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.models import Alerta, Ativo, Carteira
from core.services import chat_service


logger = logging.getLogger("views")


def _is_runserver_context() -> bool:
    if any(part == "test" or part == "discover" or "unittest" in part or "test_" in part for part in sys.argv):
        return False
    return "runserver" in sys.argv


def _get_or_create_admin_user():
    user_model = get_user_model()
    user, created = user_model.objects.get_or_create(
        username=settings.AUTO_LOGIN_ADMIN_USERNAME,
        defaults={
            "email": settings.AUTO_LOGIN_ADMIN_EMAIL,
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    needs_save = created
    if user.email != settings.AUTO_LOGIN_ADMIN_EMAIL:
        user.email = settings.AUTO_LOGIN_ADMIN_EMAIL
        needs_save = True
    if not user.is_staff:
        user.is_staff = True
        needs_save = True
    if not user.is_superuser:
        user.is_superuser = True
        needs_save = True
    if not user.is_active:
        user.is_active = True
        needs_save = True
    if not user.check_password(settings.AUTO_LOGIN_ADMIN_PASSWORD):
        user.set_password(settings.AUTO_LOGIN_ADMIN_PASSWORD)
        needs_save = True
    if needs_save:
        user.save()
    return user


def _should_auto_login_admin(request) -> bool:
    return (
        settings.AUTO_LOGIN_ADMIN_ON_SERVER
        and request.method == "GET"
        and not request.user.is_authenticated
        and _is_runserver_context()
    )


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
    # auto-login quando aplicável
    if _should_auto_login_admin(request):
        admin_user = _get_or_create_admin_user()
        auth_login(request, admin_user)
        messages.info(request, "Sessão administrativa iniciada automaticamente.")

    # se o usuário já estiver autenticado, renderiza o dashboard (mesmo contexto)
    if request.user.is_authenticated:
        carteira = _get_or_create_carteira(request.user)
        asset_matches = []
        portfolio_assets = list(carteira.ativos.order_by("ticker"))
        recent_alerts = list(
            Alerta.objects.filter(usuario=request.user)
            .select_related("ativo", "noticia")
            .order_by("-created_at")[:8]
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

    # usuário anônimo: renderiza landing / formulário de cadastro
    return render(request, "core/home.html", {"show_signup": True})