from __future__ import annotations

from django.core.management.base import BaseCommand

from setup.settings import DEFAULT_B3_CSV, DEFAULT_RSS_PATH
from core.management.workflows import run_monitor_workflow


class Command(BaseCommand):
    help = "Run the news monitor workflow once and stop after the initial collection."

    def add_arguments(self, parser):
        parser.add_argument("--b3-csv", default=str(DEFAULT_B3_CSV))
        parser.add_argument("--rss", default=str(DEFAULT_RSS_PATH))
        parser.add_argument("--no-interactive", action="store_true", help="Skip the watchlist prompt")

    def handle(self, *args, **options):
        run_monitor_workflow(
            b3_csv=options["b3_csv"],
            rss_path=options["rss"],
            interactive=not options["no_interactive"],
        )