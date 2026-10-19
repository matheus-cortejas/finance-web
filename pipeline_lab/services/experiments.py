from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from typing import Optional

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone as django_timezone

from core.models import Ativo, Noticia
from pipeline_lab.models import ExperimentRun, RunClassification

logger = logging.getLogger("pipeline_lab.experiments")


def parse_datetime(value) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_noticias_queryset(config: dict, apply_limit: bool = True):
    config = config or {}
    qs = Noticia.objects.all().order_by("id")

    since = parse_datetime(config.get("since"))
    until = parse_datetime(config.get("until"))
    if since:
        qs = qs.filter(publicado_em__gte=since)
    if until:
        qs = qs.filter(publicado_em__lte=until)
    if config.get("only_with_content"):
        qs = qs.exclude(conteudo__isnull=True).exclude(conteudo="")

    limit = config.get("limite")
    if apply_limit and limit:
        qs = qs[: int(limit)]
    return qs


def create_run(
    *,
    modelo: str,
    nome: str = "",
    criado_por=None,
    limite: int | None = None,
    since=None,
    until=None,
    only_with_content: bool = False,
    stop_after: int = 3,
    usar_llm: bool = False,
    cache_enabled: bool | None = None,
    device: str | None = None,
) -> ExperimentRun:
    modelo = (modelo or "").strip()
    if not modelo:
        raise ValueError("Modelo de embeddings é obrigatório.")
    if len(modelo) > 255:
        raise ValueError("Nome do modelo muito longo (máximo 255).")

    config = {
        "limite": int(limite) if limite else None,
        "since": since.isoformat() if isinstance(since, datetime) else since,
        "until": until.isoformat() if isinstance(until, datetime) else until,
        "only_with_content": bool(only_with_content),
        "stop_after": max(1, min(int(stop_after), 5)),
        "usar_llm": bool(usar_llm),
        "cache_enabled": (
            getattr(settings, "EXPERIMENT_CACHE_ENABLED", False)
            if cache_enabled is None
            else bool(cache_enabled)
        ),
        "device": (device or "").strip()
        or getattr(settings, "EMBEDDING_DEVICE", "cpu"),
    }

    qs = build_noticias_queryset(config)
    total = qs.count()

    return ExperimentRun.objects.create(
        nome=(nome or "").strip()
        or f"{modelo} — {django_timezone.localtime():%d/%m %H:%M}",
        modelo=modelo,
        config=config,
        total_noticias=total,
        criado_por=criado_por,
    )


def claim_pending_run(run_id: int | None = None) -> Optional[ExperimentRun]:
    """Reserva uma execução pendente usando SELECT ... FOR UPDATE SKIP LOCKED."""
    with transaction.atomic(using="default"):
        qs = ExperimentRun.objects.filter(
            status=ExperimentRun.STATUS_PENDING
        ).order_by("criado_em")
        if connection.features.has_select_for_update:
            qs = qs.select_for_update(skip_locked=True)
        if run_id is not None:
            qs = qs.filter(pk=run_id)
        run = qs.first()
        if run is None:
            return None

        run.status = ExperimentRun.STATUS_RUNNING
        run.iniciado_em = django_timezone.now()
        run.finalizado_em = None
        run.erro = ""
        run.save(
            update_fields=[
                "status",
                "iniciado_em",
                "finalizado_em",
                "erro",
            ]
        )
        return run


def process_run(run_id: int, should_stop=None) -> None:
    try:
        run = ExperimentRun.objects.get(pk=run_id)
    except ExperimentRun.DoesNotExist:
        logger.error("Execução %s não encontrada", run_id)
        return

    if run.status not in {
        ExperimentRun.STATUS_RUNNING,
        ExperimentRun.STATUS_PENDING,
    }:
        logger.info("Execução %s está com status %s; ignorando", run.id, run.status)
        return

    if run.status == ExperimentRun.STATUS_PENDING:
        run.status = ExperimentRun.STATUS_RUNNING
        run.iniciado_em = django_timezone.now()
        run.save(update_fields=["status", "iniciado_em"])

    try:
        _execute_run(run, should_stop=should_stop)
    except Exception:
        logger.exception("Falha fatal na execução %s", run.id)
        run.refresh_from_db()
        run.status = ExperimentRun.STATUS_FAILED
        run.erro = traceback.format_exc()[-5000:]
        run.finalizado_em = django_timezone.now()
        run.save(update_fields=["status", "erro", "finalizado_em"])


def _execute_run(run: ExperimentRun, should_stop=None) -> None:
    config = run.config or {}
    stop_after = max(1, min(int(config.get("stop_after", 3)), 5))
    usar_llm = bool(config.get("usar_llm", False))
    cache_enabled = bool(
        config.get("cache_enabled", getattr(settings, "EXPERIMENT_CACHE_ENABLED", False))
    )
    batch_size = max(1, int(getattr(settings, "EXPERIMENT_BATCH_SIZE", 16)))
    device = (config.get("device") or "").strip() or getattr(
        settings, "EMBEDDING_DEVICE", "cpu"
    )

    base_qs = build_noticias_queryset(config, apply_limit=False)
    already_ids = list(
        RunClassification.objects.filter(run=run).values_list(
            "noticia_id", flat=True
        )
    )
    limit = config.get("limite")
    if limit:
        limit = int(limit)
        base_ids = list(
            base_qs.values_list("id", flat=True)[:limit]
        )
        existing_set = set(already_ids)
        pending_ids = [
            noticia_id
            for noticia_id in base_ids
            if noticia_id not in existing_set
        ]
        pending_qs = base_qs.filter(id__in=pending_ids)
        total = len(base_ids)
        pendentes = len(pending_ids)
        processadas = total - pendentes
    else:
        pending_qs = base_qs.exclude(id__in=already_ids)
        total = base_qs.count()
        pendentes = pending_qs.count()
        processadas = total - pendentes

    run.total_noticias = total
    run.processadas = processadas
    run.erros = RunClassification.objects.filter(run=run).exclude(erro="").count()
    run.save(update_fields=["total_noticias", "processadas", "erros"])

    logger.info(
        "Run %s (%s): %d/%d já processadas, %d pendentes, stop_after=%d, llm=%s",
        run.id,
        run.modelo,
        processadas,
        total,
        pendentes,
        stop_after,
        usar_llm,
    )

    # Carrega o modelo uma vez e registra a dimensão real.
    from core.intelligent_motor.fase1_global_filter.embedding_generator import (
        EmbeddingGenerator,
    )

    generator = EmbeddingGenerator.instance(
        model_name=run.modelo,
        device=device,
    )
    run.embedding_dim = generator.dimension
    run.save(update_fields=["embedding_dim"])

    # A Fase 2 depende dos embeddings dos ativos para este modelo.
    if stop_after >= 2:
        from core.intelligent_motor.fase2_tickers.asset_embedding_store import (
            get_asset_embedding_store,
        )

        store = get_asset_embedding_store(model_name=run.modelo, device=device)
        gerados = store.generate_and_persist_all()
        if gerados:
            logger.info(
                "Run %s: %d embedding(s) de ativos gerados para %s",
                run.id,
                gerados,
                run.modelo,
            )

    from core.intelligent_motor.pipeline_orchestrator import (
        processar_noticia_completa,
    )

    tickers = list(Ativo.objects.values_list("ticker", flat=True))
    if not tickers:
        logger.warning("Run %s sem ativos cadastrados; Fase 2 ficará vazia", run.id)

    processadas_run = processadas
    erros_run = run.erros
    desde_progresso = 0

    for noticia in pending_qs.iterator(chunk_size=batch_size):
        current_status = (
            ExperimentRun.objects.filter(pk=run.pk)
            .values_list("status", flat=True)
            .first()
        )
        if current_status == ExperimentRun.STATUS_CANCELLED:
            logger.info("Run %s cancelada pelo usuário", run.id)
            run.processadas = processadas_run
            run.erros = RunClassification.objects.filter(run=run).exclude(
                erro=""
            ).count()
            run.finalizado_em = django_timezone.now()
            run.save(
                update_fields=["processadas", "erros", "finalizado_em"]
            )
            return

        if should_stop is not None and should_stop():
            logger.info("Run %s interrompida; voltando para pendente", run.id)
            run.processadas = processadas_run
            run.erros = RunClassification.objects.filter(run=run).exclude(
                erro=""
            ).count()
            run.status = ExperimentRun.STATUS_PENDING
            run.finalizado_em = None
            run.save(
                update_fields=[
                    "processadas",
                    "erros",
                    "status",
                    "finalizado_em",
                ]
            )
            return

        noticia_dict = {
            "id": noticia.id,
            "titulo": noticia.titulo or "",
            "descricao": noticia.descricao or "",
            "conteudo": noticia.conteudo or "",
            "link": noticia.link,
            "feed_url": noticia.feed_url or "",
            "publicado_em": (
                noticia.publicado_em.isoformat() if noticia.publicado_em else None
            ),
        }

        started = django_timezone.now()
        try:
            result = processar_noticia_completa(
                noticia=noticia_dict,
                carteira_usuario=tickers,
                model_name=run.modelo,
                run_id=run.id,
                stop_after=stop_after,
                usar_llm=usar_llm,
                cache_enabled=cache_enabled,
                device=device,
            )
            elapsed = (django_timezone.now() - started).total_seconds()
            defaults = _classification_defaults(result or {}, elapsed)
            RunClassification.objects.update_or_create(
                run=run, noticia=noticia, defaults=defaults
            )
        except Exception as exc:
            logger.exception(
                "Run %s: erro na notícia %s", run.id, noticia.id
            )
            RunClassification.objects.update_or_create(
                run=run,
                noticia=noticia,
                defaults={
                    "erro": str(exc)[:4000],
                    "tempos": {
                        "total_s": (
                            django_timezone.now() - started
                        ).total_seconds()
                    },
                },
            )
            erros_run += 1

        processadas_run += 1
        desde_progresso += 1

        if desde_progresso >= 25:
            run.processadas = processadas_run
            run.erros = erros_run
            run.save(update_fields=["processadas", "erros"])
            desde_progresso = 0

    run.refresh_from_db()
    if run.status == ExperimentRun.STATUS_CANCELLED:
        run.processadas = processadas_run
        run.erros = erros_run
        run.finalizado_em = django_timezone.now()
        run.save(update_fields=["processadas", "erros", "finalizado_em"])
        return

    run.processadas = processadas_run
    run.erros = RunClassification.objects.filter(run=run).exclude(erro="").count()
    run.status = ExperimentRun.STATUS_DONE
    run.finalizado_em = django_timezone.now()
    run.save(
        update_fields=[
            "processadas",
            "erros",
            "status",
            "finalizado_em",
        ]
    )

    from pipeline_lab.services.metrics import compute_run_metrics

    run.metricas = compute_run_metrics(run)
    run.save(update_fields=["metricas"])
    logger.info(
        "Run %s concluída: %d processadas, %d erros",
        run.id,
        run.processadas,
        run.erros,
    )


def _classification_defaults(result: dict, elapsed: float) -> dict:
    return {
        "fase1_aprovada": result.get("fase1_aprovada"),
        "relevancia_global": result.get("relevancia_global"),
        "tickers_relacionados": result.get("tickers_relacionados") or [],
        "tickers_encontrados": result.get("tickers_encontrados") or [],
        "score_heuristico": result.get("score_heuristico"),
        "criterios_ativados": result.get("criterios_ativados") or [],
        "relevancia_binaria": result.get("relevancia_binaria"),
        "confianca_fase4": result.get("confianca_fase4"),
        "provider_fase4": result.get("provider_fase4") or "",
        "sentimento": (result.get("sentimento") or "")[:16],
        "impacto": (result.get("impacto") or "")[:16],
        "urgencia": result.get("urgencia"),
        "categoria": (result.get("categoria") or "")[:64],
        "explicacao": result.get("explicacao") or "",
        "tempos": {"total_s": round(float(elapsed), 4)},
        "erro": "",
    }
