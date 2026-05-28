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
CHAT_SESSION_KEY = "monitor_chat_history"
CHAT_WELCOME_MESSAGE = {
    "role": "assistant",
    "content": (
        "Olá. Eu sou o assistente do Monitor Financeiro. Pergunte sobre a carteira, os alertas,"
        " o scheduler ou a estrutura do projeto."
    ),
}


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


def _get_chat_history(request) -> list[dict[str, str]]:
    history = request.session.get(CHAT_SESSION_KEY)
    if history:
        normalized = []
        for item in history:
            role = item.get("role")
            content = item.get("content", "").strip()
            if role in {"user", "assistant"} and content:
                normalized.append({"role": role, "content": content})
        if normalized:
            return normalized[-24:]
    request.session[CHAT_SESSION_KEY] = [CHAT_WELCOME_MESSAGE]
    request.session.modified = True
    return [CHAT_WELCOME_MESSAGE]


def _store_chat_history(request, history: list[dict[str, str]]) -> None:
    request.session[CHAT_SESSION_KEY] = history[-24:]
    request.session.modified = True


def home(request):
    if _should_auto_login_admin(request):
        admin_user = _get_or_create_admin_user()
        auth_login(request, admin_user)
        logger.info("Admin logado automaticamente no runserver: username=%s", admin_user.username)

    signup_form = UserCreationForm()
    login_form = AuthenticationForm(request)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "signup":
            signup_form = UserCreationForm(request.POST)
            logger.info("Cadastro solicitado pela home: username=%s", signup_form.data.get("username", ""))
            if signup_form.is_valid():
                user = signup_form.save()
                auth_login(request, user)
                logger.info("Cadastro concluído e usuário autenticado: username=%s", user.username)
                messages.success(request, "Conta criada com sucesso. Você já pode usar sua dashboard.")
                return redirect("dashboard")
            logger.info("Cadastro inválido pela home: username=%s", signup_form.data.get("username", ""))
        elif action == "login":
            login_form = AuthenticationForm(request, data=request.POST)
            logger.info("Login solicitado pela home: username=%s", login_form.data.get("username", ""))
            if login_form.is_valid():
                user = login_form.get_user()
                auth_login(request, user)
                logger.info("Login concluído pela home: username=%s", user.username)
                messages.success(request, "Bem-vindo de volta.")
                return redirect("dashboard")
            logger.warning("Falha de login pela home: username=%s", login_form.data.get("username", ""))
            messages.error(request, "Usuário ou senha inválidos.")

    return render(
        request,
        "core/home.html",
        {
            "signup_form": signup_form,
            "login_form": login_form,
        },
    )


def _get_or_create_carteira(user) -> Carteira:
    carteira, _ = Carteira.objects.get_or_create(usuario=user)
    return carteira


@login_required
def dashboard(request):
    carteira = _get_or_create_carteira(request.user)
    asset_matches = []

    if request.method == "POST":
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


@login_required
def chat(request):
    chat_history = _get_chat_history(request)
    return render(
        request,
        "core/chat.html",
        {
            "chat_history": chat_history,
            "chat_provider": "OpenAI" if settings.OPENAI_API_KEY else "Fallback local",
        },
    )


@login_required
@require_POST
def chat_api(request):
    message = request.POST.get("message", "").strip()
    history = _get_chat_history(request)
    if not message:
        return JsonResponse({"error": "Mensagem vazia."}, status=400)

    history.append({"role": "user", "content": message})
    response = chat_service.generate_chat_reply(history, message)
    reply = response["reply"]
    history.append({"role": "assistant", "content": reply})
    _store_chat_history(request, history)

    return JsonResponse(
        {
            "reply": reply,
            "provider": response.get("provider", "fallback"),
            "history": history,
        }
    )
