from __future__ import annotations

from django.core.management.base import BaseCommand

from core.models import FonteRSS
from core.services.collector_service import sync_feeds_from_file
from setup.settings import DEFAULT_RSS_PATH


class Command(BaseCommand):
    help = "Sincroniza o arquivo de feeds RSS com a tabela FonteRSS."

    def add_arguments(self, parser):
        parser.add_argument("--rss", default=str(DEFAULT_RSS_PATH))

    def handle(self, *args, **options):
        created, total = sync_feeds_from_file(options["rss"])
        ativos = FonteRSS.objects.filter(ativo=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"{created} feed(s) novo(s); {total} no arquivo; "
                f"{ativos} ativo(s) no banco."
            )
        )
