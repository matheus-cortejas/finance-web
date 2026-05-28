from __future__ import annotations

from django.core.management.base import BaseCommand

from setup.settings import DEFAULT_RSS_PATH
from core.management.workflows import run_scheduler_workflow


class Command(BaseCommand):
    help = "Run the persistent APScheduler loop for the news monitor."

    def add_arguments(self, parser):
        parser.add_argument("--rss", default=str(DEFAULT_RSS_PATH))

    def handle(self, *args, **options):
        run_scheduler_workflow(rss_path=options["rss"])