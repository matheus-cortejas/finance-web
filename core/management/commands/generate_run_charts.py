from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pipeline_lab.models import ExperimentRun


def _comparativo_rows() -> list[dict]:
    """Monta o comparativo de F1 entre execuções com notícias anotadas."""
    rows = []
    for run in ExperimentRun.objects.filter(status=ExperimentRun.STATUS_DONE).order_by("id"):
        metricas = run.metricas or {}
        fase1 = (metricas.get("fase1") or {}).get("metricas") or {}
        fase4 = (metricas.get("fase4") or {}).get("metricas") or {}
        rows.append(
            {
                "run_id": run.id,
                "label": f"#{run.id}",
                "labeled_total": metricas.get("labeled_total") or 0,
                "fase1_f1": fase1.get("f1") if fase1.get("total") else None,
                "fase4_f1": fase4.get("f1") if fase4.get("total") else None,
            }
        )
    return rows


class Command(BaseCommand):
    help = (
        "Gera os gráficos e artefatos de uma execução (por run_id) em "
        "exports/lab/run-<id>/ a partir do pipeline_metrics.jsonl."
    )

    def add_arguments(self, parser):
        parser.add_argument("--run-id", type=int, required=True)
        parser.add_argument(
            "--metrics-path",
            default=None,
            help="Arquivo JSONL de métricas (default: EXPERIMENT_METRICS_PATH).",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Diretório de saída (default: exports/lab/run-<id>).",
        )
        parser.add_argument(
            "--no-amostra",
            action="store_true",
            help="Não gerar a amostra para anotação da Fase 4.",
        )

    def handle(self, *args, **options):
        run_id = options["run_id"]
        try:
            run = ExperimentRun.objects.get(pk=run_id)
        except ExperimentRun.DoesNotExist as exc:
            raise CommandError(f"Execução {run_id} não encontrada.") from exc

        # pandas/matplotlib são importados só na hora de gerar, para que
        # comandos e testes que não tocam gráficos não dependam deles.
        try:
            from core.intelligent_motor.metrics_charts import generate_all, load_metrics
        except ImportError as exc:  # pragma: no cover - depende da imagem
            raise CommandError(
                "pandas/matplotlib não instalados; instale as dependências para "
                "gerar os gráficos."
            ) from exc

        metrics_path = (
            options["metrics_path"]
            or getattr(settings, "EXPERIMENT_METRICS_PATH", None)
            or "pipeline_metrics.jsonl"
        )
        output = Path(
            options["output"]
            or getattr(settings, "LAB_CHARTS_DIR", Path(settings.BASE_DIR) / "exports" / "lab")
            / f"run-{run.id}"
        )

        df = load_metrics(metrics_path, run_id=run.id)
        parametros = (run.config or {}).get("efetivo") or {}
        escritos = generate_all(
            df,
            output,
            metricas=run.metricas or {},
            parametros=parametros,
            run_meta={"run_id": run.id, "modelo": run.modelo},
            comparativo_rows=_comparativo_rows(),
            include_amostra=not options["no_amostra"],
        )

        if options.get("verbosity", 1):
            self.stdout.write(
                f"Run {run.id}: {len(df)} linha(s) de métricas; "
                f"{len(escritos)} arquivo(s) em {output}"
            )
            for nome in escritos:
                self.stdout.write(f"  - {nome}")
