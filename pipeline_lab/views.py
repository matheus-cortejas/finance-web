from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Ativo, Noticia
from pipeline_lab.models import AssetEmbedding, ExperimentRun, LabModel, NewsLabel
from pipeline_lab.services.experiments import create_run
from pipeline_lab.services.run_params import (
    PESOS_FASE3,
    build_overrides,
    defaults as param_defaults,
)
from pipeline_lab.services.model_registry import (
    clear_asset_embeddings,
    delete_local_model,
    install_archive,
    local_model_exists,
    register_huggingface,
    scan_local_models,
    test_model_load,
)

logger = logging.getLogger("pipeline_lab")


def _is_staff(user):
    return user.is_authenticated and user.is_staff


def _device_choices() -> list[str]:
    return ["auto", "cpu", "cuda"]


def _charts_dir(run_id: int) -> Path:
    base = Path(
        getattr(settings, "LAB_CHARTS_DIR", Path(settings.BASE_DIR) / "exports" / "lab")
    )
    return base / f"run-{run_id}"


def _chart_files(run_id: int) -> list[dict]:
    """Lista os artefatos já gerados para uma execução (na ordem do manifesto)."""
    from core.intelligent_motor.chart_manifest import FILE_LABELS

    run_dir = _charts_dir(run_id)
    arquivos = []
    for nome, rotulo in FILE_LABELS.items():
        caminho = run_dir / nome
        if caminho.is_file():
            arquivos.append(
                {
                    "name": nome,
                    "label": rotulo,
                    "is_image": nome.endswith(".png"),
                }
            )
    return arquivos


def _model_choices() -> list[str]:
    choices = list(getattr(settings, "EMBEDDING_MODELS", []) or [])
    for nome in LabModel.objects.filter(ativo=True).values_list("nome", flat=True):
        if nome and nome not in choices:
            choices.append(nome)
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
    device: str | None = None,
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
        device=device,
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
    padroes = param_defaults()
    context = {
        "model_choices": _model_choices() or [
            "paraphrase-multilingual-MiniLM-L12-v2"
        ],
        "device_choices": _device_choices(),
        "default_device": getattr(settings, "EMBEDDING_DEVICE", "cpu"),
        "runs": ExperimentRun.objects.select_related("criado_por")[:20],
        "total_noticias": Noticia.objects.count(),
        "noticias_com_conteudo": Noticia.objects.exclude(conteudo__isnull=True)
        .exclude(conteudo="")
        .count(),
        "total_labels": NewsLabel.objects.exclude(relevancia=None).count(),
        "total_runs": ExperimentRun.objects.count(),
        "total_modelos": LabModel.objects.count(),
        "param_defaults": padroes,
        "param_pesos": [
            {
                "key": chave,
                "label": rotulo,
                "default": padroes["fase3"]["pesos"][chave],
            }
            for chave, rotulo in PESOS_FASE3
        ],
    }

    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        descricao = request.POST.get("descricao", "").strip()
        conteudo = request.POST.get("conteudo", "").strip()
        link = request.POST.get("link", "").strip() or "https://test.example.com/news"
        modelo = request.POST.get("modelo", "").strip() or context["model_choices"][0]
        device = request.POST.get("device", "").strip() or context["default_device"]
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
                device=device,
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
                "selected_device": device,
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
        overrides = build_overrides(request.POST)
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
            device=request.POST.get("device") or None,
            overrides=overrides,
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("pipeline_lab_home")
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
    config = run.config or {}
    return render(
        request,
        "pipeline_lab/run_detail.html",
        {
            "run": run,
            "classifications": classifications,
            "total_classifications": run.classifications.count(),
            "config": config,
            "metricas": run.metricas or {},
            "model_choices": _model_choices(),
            "parametros": config.get("efetivo") or param_defaults(),
            "overrides": config.get("overrides") or {},
            "chart_files": _chart_files(run.id),
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
@require_POST
def run_charts(request, run_id: int):
    """Regenera os gráficos/artefatos da execução a pedido do usuário."""
    run = get_object_or_404(ExperimentRun, pk=run_id)
    try:
        from django.core.management import call_command

        call_command("generate_run_charts", run_id=run.id, verbosity=0)
        messages.success(request, "Gráficos regenerados.")
    except Exception as exc:
        logger.exception("Falha ao gerar gráficos da execução %s", run.id)
        messages.error(request, f"Falha ao gerar gráficos: {exc}")
    return redirect("pipeline_lab_run_detail", run_id=run.id)


@login_required
@user_passes_test(_is_staff)
def run_chart_file(request, run_id: int, filename: str):
    """Serve um artefato gerado, com whitelist de nomes e da pasta da execução."""
    from core.intelligent_motor.chart_manifest import FILE_LABELS

    if filename not in FILE_LABELS:
        raise Http404("Arquivo não permitido.")

    run_dir = _charts_dir(run_id).resolve()
    caminho = (run_dir / filename).resolve()
    # Garante que o arquivo está mesmo dentro da pasta da execução.
    if run_dir not in caminho.parents or not caminho.is_file():
        raise Http404("Arquivo não encontrado.")

    if filename.endswith(".png"):
        return FileResponse(caminho.open("rb"), content_type="image/png")
    if filename.endswith(".csv"):
        return FileResponse(
            caminho.open("rb"), content_type="text/csv", as_attachment=False
        )
    conteudo = caminho.read_text(encoding="utf-8")
    return HttpResponse(conteudo, content_type="text/plain; charset=utf-8")


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
        efetivo = (run.config or {}).get("efetivo") or {}
        rows.append(
            {
                "run": run,
                "theta_rel": (efetivo.get("fase1") or {}).get("threshold_relevancia"),
                "theta_sim": (efetivo.get("fase2") or {}).get(
                    "threshold_similaridade"
                ),
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


# --------------------------------------------------------------------- modelos


def _decorate_models(models: list[LabModel]) -> list[LabModel]:
    from collections import Counter

    try:
        from core.intelligent_motor.fase1_global_filter.embedding_generator import (
            EmbeddingGenerator,
        )
    except Exception:  # pragma: no cover - ambiente sem sentence-transformers
        EmbeddingGenerator = None

    alvos_por_modelo: dict[int, set[str]] = {}
    for model in models:
        alvos = {model.nome}
        if EmbeddingGenerator is not None:
            try:
                alvos.add(EmbeddingGenerator.resolve_model_name(model.nome))
            except Exception:
                pass
        alvos_por_modelo[model.id] = alvos

    todos = set().union(*alvos_por_modelo.values()) if alvos_por_modelo else set()
    embeddings = Counter(
        AssetEmbedding.objects.filter(modelo__in=list(todos)).values_list(
            "modelo", flat=True
        )
    )
    runs = Counter(ExperimentRun.objects.values_list("modelo", flat=True))

    for model in models:
        model.alvos = alvos_por_modelo.get(model.id, set())
        model.total_embeddings = sum(embeddings[alvo] for alvo in model.alvos)
        model.total_runs = runs.get(model.nome, 0)
        model.existe = local_model_exists(model) if model.e_local else True
    return models


@login_required
@user_passes_test(_is_staff)
def models_view(request):
    if request.method == "POST":
        acao = request.POST.get("acao", "")
        try:
            if acao == "upload":
                model = install_archive(
                    request.FILES.get("arquivo"),
                    nome=request.POST.get("nome", ""),
                    descricao=request.POST.get("descricao", ""),
                    user=request.user,
                    sobrescrever=request.POST.get("sobrescrever") == "on",
                )
                messages.success(
                    request,
                    f"Modelo '{model.nome}' instalado. Use 'Testar' para validar.",
                )
            elif acao == "registrar_hf":
                model = register_huggingface(
                    request.POST.get("nome", ""),
                    descricao=request.POST.get("descricao", ""),
                    user=request.user,
                )
                messages.success(
                    request,
                    f"Modelo Hugging Face '{model.nome}' registrado.",
                )
            elif acao == "scan":
                criados = scan_local_models(user=request.user)
                messages.success(
                    request,
                    f"Varredura concluída: {criados} modelo(s) novo(s) registrado(s).",
                )
            else:
                messages.warning(request, "Ação desconhecida.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages) if exc.messages else str(exc))
        except Exception as exc:  # noqa: BLE001 - reportado na tela
            logger.exception("Falha na gestão de modelos")
            messages.error(request, f"Falha: {exc}")
        return redirect("pipeline_lab_models")

    models = _decorate_models(list(LabModel.objects.all()))
    return render(
        request,
        "pipeline_lab/models.html",
        {
            "models": models,
            "device_choices": _device_choices(),
            "default_device": getattr(settings, "EMBEDDING_DEVICE", "cpu"),
            "models_dir": str(getattr(settings, "LAB_MODELS_DIR", "")),
            "upload_max_mb": getattr(settings, "LAB_MODEL_UPLOAD_MAX_MB", 4096),
        },
    )


@login_required
@user_passes_test(_is_staff)
@require_POST
def model_test(request, model_id: int):
    model = get_object_or_404(LabModel, pk=model_id)
    device = request.POST.get("device") or None
    test_model_load(model, device=device)
    if model.erro_teste:
        messages.error(request, f"'{model.nome}' falhou: {model.erro_teste[:500]}")
    else:
        messages.success(
            request,
            f"'{model.nome}' carregou com {model.dimensao or '?'} dimensões.",
        )
    return redirect("pipeline_lab_models")


@login_required
@user_passes_test(_is_staff)
@require_POST
def model_clear_embeddings(request, model_id: int):
    model = get_object_or_404(LabModel, pk=model_id)
    total = clear_asset_embeddings(model)
    messages.success(request, f"{total} embedding(s) removido(s) para '{model.nome}'.")
    return redirect("pipeline_lab_models")


@login_required
@user_passes_test(_is_staff)
@require_POST
def model_toggle(request, model_id: int):
    model = get_object_or_404(LabModel, pk=model_id)
    model.ativo = not model.ativo
    model.save(update_fields=["ativo", "atualizado_em"])
    estado = "ativado" if model.ativo else "desativado"
    messages.success(request, f"Modelo '{model.nome}' {estado}.")
    return redirect("pipeline_lab_models")


@login_required
@user_passes_test(_is_staff)
@require_POST
def model_delete(request, model_id: int):
    model = get_object_or_404(LabModel, pk=model_id)
    nome = model.nome
    try:
        delete_local_model(model)
        messages.success(request, f"Modelo '{nome}' excluído.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if exc.messages else str(exc))
    return redirect("pipeline_lab_models")
