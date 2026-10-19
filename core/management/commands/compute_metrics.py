from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from pipeline_lab.models import ExperimentRun
from pipeline_lab.services.metrics import compute_run_metrics


class Command(BaseCommand):
    help = "Recalcula e salva as métricas de uma ou de todas as execuções."

    def add_arguments(self, parser):
        parser.add_argument("--run-id", type=int, default=None)
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        if options["run_id"]:
            try:
                runs = [ExperimentRun.objects.get(pk=options["run_id"])]
            except ExperimentRun.DoesNotExist as exc:
                raise CommandError(
                    f"Execução {options['run_id']} não encontrada."
                ) from exc
        elif options["all"]:
            runs = list(ExperimentRun.objects.all())
        else:
            raise CommandError("Use --run-id N ou --all.")

        for run in runs:
            metrics = compute_run_metrics(run)
            run.metricas = metrics
            run.save(update_fields=["metricas"])

            if options["json"]:
                self.stdout.write(json.dumps(metrics, ensure_ascii=False, indent=2))
                continue

            fase1 = metrics["fase1"]["metricas"]
            fase4 = metrics["fase4"]["metricas"]
            fase1_f1 = fase1["f1"] if fase1.get("total") else "-"
            fase4_f1 = fase4["f1"] if fase4.get("total") else "-"
            best_score = metrics["score_heuristico"].get("best") or {}
            best_global = metrics["relevancia_global"].get("best") or {}
            self.stdout.write(
                f"run={run.id} modelo={run.modelo} labeled={metrics['labeled_total']} "
                f"fase1_f1={fase1_f1} fase4_f1={fase4_f1} "
                f"score_best_f1={best_score.get('f1', '-')} "
                f"global_best_f1={best_global.get('f1', '-')}"
            )
