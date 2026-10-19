from __future__ import annotations

import logging
import signal
import threading

from django.core.management.base import BaseCommand, CommandError

from pipeline_lab.models import ExperimentRun
from pipeline_lab.services.experiments import claim_pending_run, process_run
from setup.settings import EXPERIMENT_WORKER_POLL_SECONDS

logger = logging.getLogger("pipeline_lab.worker")


class Command(BaseCommand):
    help = "Processa execuções pendentes do laboratório de embeddings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Processa no máximo uma execução e encerra.",
        )
        parser.add_argument(
            "--run-id",
            type=int,
            default=None,
            help="Processa apenas a execução indicada.",
        )
        parser.add_argument(
            "--poll-seconds",
            type=int,
            default=EXPERIMENT_WORKER_POLL_SECONDS,
        )

    def handle(self, *args, **options):
        stop = threading.Event()

        def shutdown(signum, frame):
            logger.info("Sinal %s recebido; solicitando parada do worker", signum)
            stop.set()

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        run_id = options["run_id"]
        if run_id is not None:
            run = ExperimentRun.objects.filter(pk=run_id).first()
            if run is None:
                raise CommandError(f"Execução {run_id} não encontrada.")
            if run.status == ExperimentRun.STATUS_PENDING:
                run = claim_pending_run(run_id)
            if run is None:
                self.stdout.write("Nenhuma execução pendente.")
                return
            process_run(run.id, should_stop=stop.is_set)
            return

        while not stop.is_set():
            run = claim_pending_run()
            if run is not None:
                self.stdout.write(
                    f"Processando execução {run.id} ({run.modelo})..."
                )
                process_run(run.id, should_stop=stop.is_set)
                if options["once"]:
                    return
                continue

            if options["once"]:
                self.stdout.write("Nenhuma execução pendente.")
                return

            stop.wait(max(1, options["poll_seconds"]))

        self.stdout.write("Worker encerrado.")
