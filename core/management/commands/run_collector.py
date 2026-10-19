from __future__ import annotations

import logging
import signal
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from django.core.management.base import BaseCommand, CommandError

from core.services.collector_service import collect_configured_feeds
from setup.settings import COLLECTOR_INTERVAL_SECONDS

logger = logging.getLogger("collector.command")


class Command(BaseCommand):
    help = "Coleta notícias RSS sem executar o pipeline. Processo contínuo (ou --once)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Executa um único ciclo de coleta e encerra.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=COLLECTOR_INTERVAL_SECONDS,
            help=f"Intervalo entre ciclos em segundos (padrão: {COLLECTOR_INTERVAL_SECONDS}).",
        )
        parser.add_argument(
            "--within-days",
            type=int,
            default=None,
            help="Na primeira coleta, ignora notícias mais antigas que N dias.",
        )
        parser.add_argument(
            "--max-entries",
            type=int,
            default=None,
            help="Limita entradas por feed (útil para testes).",
        )

    def handle(self, *args, **options):
        interval = options["interval"]
        if interval <= 0:
            raise CommandError("--interval deve ser maior que zero.")

        within_days = options["within_days"]
        max_entries = options["max_entries"]

        def run_cycle() -> None:
            try:
                result = collect_configured_feeds(
                    within_days=within_days,
                    max_entries=max_entries,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        "Coleta: "
                        f"{result.criadas} nova(s), "
                        f"{result.duplicadas} duplicada(s), "
                        f"{result.erros} erro(s)."
                    )
                )
            except Exception as exc:  # o scheduler deve continuar vivo
                logger.exception("Falha no ciclo de coleta")
                self.stderr.write(self.style.ERROR(f"Falha na coleta: {exc}"))

        if options["once"]:
            run_cycle()
            return

        scheduler = BlockingScheduler(timezone="UTC")

        def shutdown(signum, frame):
            logger.info("Sinal %s recebido; encerrando coletor", signum)
            if scheduler.running:
                scheduler.shutdown(wait=False)

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        scheduler.add_job(
            run_cycle,
            trigger="interval",
            seconds=interval,
            id="collect-rss",
            next_run_time=datetime.now(timezone.utc),
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )

        self.stdout.write(
            f"Coletor iniciado (intervalo de {interval}s). Ctrl+C para parar."
        )
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            if scheduler.running:
                scheduler.shutdown(wait=False)
            self.stdout.write("Coletor encerrado.")
