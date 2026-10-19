from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Ativo, Noticia
from pipeline_lab.models import ExperimentRun, NewsLabel
from pipeline_lab.services.experiments import create_run

logger = logging.getLogger("pipeline_lab")


def _is_staff(user):
    return user.is_authenticated and user.is_staff


def _model_choices() -> list[str]:
    choices = list(getattr(settings, "EMBEDDING_MODELS", []) or [])
    for modelo in ExperimentRun.objects.values_list("modelo", flat=True).distinct():
        if modelo and modelo not in choices:
            choices.append(modelo)
    return choices


def _run_pipeline_test(
    noticia: dict,
    carteira_usuario: list[str],
    model_name: str,
    stop_after: int,
    usar_llm: bool,
) -> dict:
    from core.intelligent_motor.pipeline_orchestrator import (
        processar_noticia_completa,
    )

    return processar_noticia_completa(
        noticia=noticia,
        carteira_usuario=carteira_usuario,
        model_name=model_name,
        stop_after=stop_after,
        usar_llm=usar_llm,
        cache_enabled=False,
    )


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
            nao_alertariam.append(
                {
                    "username": usuario.username,
                    "motivo": "Nenhum ticker relacionado",
                    "carteira": sorted(user_tickers),
                }
            )
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
            nao_alertariam.append(
                {
                    "username": usuario.username,
                    "motivo": f"Erro ao processar: {exc}",
                    "tickers_casaram": sorted(matched),
                }
            )
            continue

        prioridade = decision.get("prioridade", "baixa")
        min_priority = "media"
        if perfil and hasattr(perfil, "alerta_min_prioridade"):
            min_priority = perfil.alerta_min_prioridade

        if is_priority_at_least(prioridade, min_priority):
            alertariam.append(
                {
                    "username": usuario.username,
                    "tickers_casaram": sorted(matched),
                    "prioridade": prioridade,
                    "score_final": decision.get("score_final", 0),
                    "acoes": decision.get("acao_sugerida", []),
                    "explicacao": decision.get("explicacao_regra", ""),
                }
            )
        else:
            nao_alertariam.append(
                {
                    "username": usuario.username,
                    "motivo": (
                        f"Prioridade '{prioridade}' abaixo do mínimo "
                        f"'{min_priority}'"
                    ),
                    "tickers_casaram": sorted(matched),
                }
            )

    alertariam.sort(key=lambda x: x["score_final"], reverse=True)
    return {"alertariam": alertariam, "nao_alertariam": nao_alertariam}


@login_required
@user_passes_test(_is_staff)
def pipeline_lab_home(request):
    context = {
        "model_choices": _model_choices() or [
            "paraphrase-multilingual-MiniLM-L12-v2"
        ],
        "runs": ExperimentRun.objects.select_related("criado_por")[:20],
        "total_noticias": Noticia.objects.count(),
        "noticias_com_conteudo": Noticia.objects.exclude(conteudo__isnull=True)
        .exclude(conteudo="")
        .count(),
        "total_labels": NewsLabel.objects.exclude(relevancia=None).count(),
        "total_runs": ExperimentRun.objects.count(),
    }

    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        descricao = request.POST.get("descricao", "").strip()
        conteudo = request.POST.get("conteudo", "").strip()
        link = request.POST.get("link", "").strip() or "https://test.example.com/news"
        modelo = request.POST.get("modelo", "").strip() or context["model_choices"][0]
        try:
            stop_after = max(1, min(int(request.POST.get("stop_after", 5)), 5))
        except ValueError:
            stop_after = 5
        usar_llm = request.POST.get("usar_llm") == "on"

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
        all_tickers = list(Ativo.objects.values_list("ticker", flat=True))

        t_start = time.perf_counter()
        try:
            pipeline_result = _run_pipeline_test(
                noticia_dict,
                all_tickers,
                model_name=modelo,
                stop_after=stop_after,
                usar_llm=usar_llm,
            )
        except Exception as exc:
            logger.exception("Erro no pipeline de teste")
            context["error"] = f"Erro ao executar pipeline: {exc}"
            return render(request, "pipeline_lab/home.html", context)
        t_pipeline = round(time.perf_counter() - t_start, 3)

        t_start2 = time.perf_counter()
        alertas_simulados = _simular_alertas(pipeline_result)
        t_alertas = round(time.perf_counter() - t_start2, 3)

        context.update(
            {
                "result": pipeline_result,
                "result_json": json.dumps(
                    pipeline_result, ensure_ascii=False, indent=2, default=str
                ),
                "alertas_simulados": alertas_simulados,
                "form_data": request.POST,
                "t_pipeline": t_pipeline,
                "t_alertas": t_alertas,
                "selected_model": modelo,
                "selected_stop_after": stop_after,
                "selected_usar_llm": usar_llm,
            }
        )

    return render(request, "pipeline_lab/home.html", context)


@login_required
@user_passes_test(_is_staff)
@require_POST
def create_run_view(request):
    try:
        limite_raw = (request.POST.get("limite") or "").strip()
        limite = int(limite_raw) if limite_raw else None
        if limite is not None and limite <= 0:
            raise ValueError("O limite deve ser um inteiro maior que zero.")
        stop_after = max(1, min(int(request.POST.get("stop_after", 3)), 5))
        run = create_run(
            modelo=request.POST.get("modelo", ""),
            nome=request.POST.get("nome", ""),
            criado_por=request.user,
            limite=limite,
            since=request.POST.get("since") or None,
            until=request.POST.get("until") or None,
            only_with_content=request.POST.get("only_with_content") == "on",
            stop_after=stop_after,
            usar_llm=request.POST.get("usar_llm") == "on",
            cache_enabled=request.POST.get("cache_enabled") == "on",
        )
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc))
        return redirect("pipeline_lab_home")

    messages.success(
        request,
        f"Execução {run.id} criada com {run.total_noticias} notícia(s). "
        "O worker irá processá-la.",
    )
    return redirect("pipeline_lab_run_detail", run_id=run.id)


@login_required
@user_passes_test(_is_staff)
def run_detail(request, run_id: int):
    run = get_object_or_404(ExperimentRun, pk=run_id)
    classifications = (
        run.classifications.select_related("noticia")
        .order_by("noticia_id")[:200]
    )
    return render(
        request,
        "pipeline_lab/run_detail.html",
        {
            "run": run,
            "classifications": classifications,
            "total_classifications": run.classifications.count(),
            "config": run.config or {},
            "metricas": run.metricas or {},
            "model_choices": _model_choices(),
        },
    )


@login_required
@user_passes_test(_is_staff)
@require_POST
def cancel_run(request, run_id: int):
    run = get_object_or_404(ExperimentRun, pk=run_id)
    if run.status in {
        ExperimentRun.STATUS_PENDING,
        ExperimentRun.STATUS_RUNNING,
    }:
        run.status = ExperimentRun.STATUS_CANCELLED
        run.finalizado_em = timezone.now()
        run.save(update_fields=["status", "finalizado_em"])
        messages.success(request, f"Execução {run.id} cancelada.")
    else:
        messages.warning(request, "Esta execução já foi finalizada.")
    return redirect("pipeline_lab_run_detail", run_id=run.id)


@login_required
@user_passes_test(_is_staff)
def compare_runs(request):
    rows = []
    for run in ExperimentRun.objects.order_by("-criado_em")[:100]:
        metrics = run.metricas or {}
        best_score = (metrics.get("score_heuristico") or {}).get("best") or {}
        best_global = (metrics.get("relevancia_global") or {}).get("best") or {}
        fase1_metrics = (metrics.get("fase1") or {}).get("metricas", {})
        fase4_metrics = (metrics.get("fase4") or {}).get("metricas", {})
        rows.append(
            {
                "run": run,
                "labeled": metrics.get("labeled_total"),
                "fase1_f1": (
                    fase1_metrics.get("f1")
                    if fase1_metrics.get("total")
                    else None
                ),
                "fase4_f1": (
                    fase4_metrics.get("f1")
                    if fase4_metrics.get("total")
                    else None
                ),
                "score_f1": best_score.get("f1"),
                "score_threshold": best_score.get("threshold"),
                "global_f1": best_global.get("f1"),
                "global_threshold": best_global.get("threshold"),
                "tempo_medio": metrics.get("tempo_medio_s"),
                "cobertura": metrics.get("cobertura"),
            }
        )
    return render(request, "pipeline_lab/compare.html", {"rows": rows})
