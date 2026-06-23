from __future__ import annotations

import logging
import time
from unittest.mock import patch

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render

logger = logging.getLogger("pipeline_lab")


def _is_staff(user):
    return user.is_authenticated and user.is_staff


def _run_pipeline_test(noticia: dict, carteira_usuario: list[str]) -> dict:
    """Roda o pipeline completo (Fases 1-5) sem persistir nada no banco."""
    from core.intelligent_motor.pipeline_orchestrator import processar_noticia_completa

    with patch("core.services.noticia_service.seen_article", return_value=False):
        result = processar_noticia_completa(
            noticia=noticia,
            carteira_usuario=carteira_usuario,
        )
    return result


def _simular_alertas(pipeline_result: dict) -> dict:
    """Simula a Fase 6 para cada usuário com carteira, sem criar alertas."""
    from core.models import Carteira, PerfilInvestidor
    from core.intelligent_motor.fase6_decisor.pipeline import decidir_alerta
    from core.services.noticia_service import _convert_perfil, is_priority_at_least

    tickers_relacionados = set(pipeline_result.get("tickers_relacionados", []))

    alertariam = []
    nao_alertariam = []

    if not tickers_relacionados:
        return {"alertariam": alertariam, "nao_alertariam": nao_alertariam}

    carteiras = Carteira.objects.prefetch_related("ativos").all()

    for carteira in carteiras:
        usuario = carteira.usuario
        user_tickers = set(carteira.ativos.values_list("ticker", flat=True))
        matched = tickers_relacionados & user_tickers

        if not matched:
            nao_alertariam.append({
                "username": usuario.username,
                "motivo": "Nenhum ticker relacionado",
                "carteira": sorted(user_tickers),
            })
            continue

        perfil = PerfilInvestidor.objects.filter(usuario=usuario).first()
        perfil_dict = _convert_perfil(perfil) if perfil else None

        try:
            decision = decidir_alerta(
                noticia=pipeline_result,
                perfil=perfil_dict,
            )
        except Exception as exc:
            logger.exception("Erro na Fase 6 para usuário %s", usuario.username)
            nao_alertariam.append({
                "username": usuario.username,
                "motivo": f"Erro ao processar: {exc}",
                "tickers_casaram": sorted(matched),
            })
            continue

        prioridade = decision.get("prioridade", "baixa")
        min_priority = "media"
        if perfil and hasattr(perfil, "alerta_min_prioridade"):
            min_priority = perfil.alerta_min_prioridade

        if is_priority_at_least(prioridade, min_priority):
            alertariam.append({
                "username": usuario.username,
                "tickers_casaram": sorted(matched),
                "prioridade": prioridade,
                "score_final": decision.get("score_final", 0),
                "acoes": decision.get("acao_sugerida", []),
                "explicacao": decision.get("explicacao_regra", ""),
            })
        else:
            nao_alertariam.append({
                "username": usuario.username,
                "motivo": f"Prioridade '{prioridade}' abaixo do mínimo '{min_priority}'",
                "tickers_casaram": sorted(matched),
            })

    alertariam.sort(key=lambda x: x["score_final"], reverse=True)
    return {"alertariam": alertariam, "nao_alertariam": nao_alertariam}


@login_required
@user_passes_test(_is_staff)
def pipeline_lab_home(request):
    context = {}

    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        descricao = request.POST.get("descricao", "").strip()
        conteudo = request.POST.get("conteudo", "").strip()
        link = request.POST.get("link", "").strip() or "https://test.example.com/news"

        if not titulo:
            context["error"] = "Título é obrigatório."
            return render(request, "pipeline_lab/home.html", context)

        noticia_dict = {
            "id": None,
            "titulo": titulo,
            "descricao": descricao,
            "conteudo": conteudo,
            "link": link,
        }

        from core.models import Ativo
        all_tickers = list(Ativo.objects.values_list("ticker", flat=True))

        t_start = time.perf_counter()
        try:
            pipeline_result = _run_pipeline_test(noticia_dict, all_tickers)
        except Exception as exc:
            logger.exception("Erro no pipeline de teste")
            context["error"] = f"Erro ao executar pipeline: {exc}"
            return render(request, "pipeline_lab/home.html", context)
        t_pipeline = round(time.perf_counter() - t_start, 3)

        t_start2 = time.perf_counter()
        alertas_simulados = _simular_alertas(pipeline_result)
        t_alertas = round(time.perf_counter() - t_start2, 3)

        context = {
            "result": pipeline_result,
            "alertas_simulados": alertas_simulados,
            "form_data": request.POST,
            "t_pipeline": t_pipeline,
            "t_alertas": t_alertas,
        }

    return render(request, "pipeline_lab/home.html", context)