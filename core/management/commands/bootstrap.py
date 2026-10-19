from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import Ativo, FonteRSS, Noticia
from core.services.acao_service import load_assets_from_json, parse_b3_csv
from core.services.collector_service import (
    collect_configured_feeds,
    sync_feeds_from_file,
)
from setup.settings import (
    ARTICLE_RETENTION_DAYS,
    DEFAULT_ASSETS_JSON_PATH,
    DEFAULT_B3_CSV,
    DEFAULT_RSS_PATH,
)


class Command(BaseCommand):
    help = (
        "Prepara o ambiente: ativos, fontes RSS e coleta inicial. "
        "Não executa o pipeline nem carrega modelos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--assets-json", default=str(DEFAULT_ASSETS_JSON_PATH))
        parser.add_argument("--b3-csv", default=str(DEFAULT_B3_CSV))
        parser.add_argument("--rss", default=str(DEFAULT_RSS_PATH))
        parser.add_argument(
            "--days",
            type=int,
            default=ARTICLE_RETENTION_DAYS,
            help="Janela da coleta inicial em dias (padrão: ARTICLE_RETENTION_DAYS).",
        )
        parser.add_argument(
            "--skip-collect",
            action="store_true",
            help="Apenas popula ativos/feeds, sem coletar notícias.",
        )
        parser.add_argument("--max-entries", type=int, default=None)

    def handle(self, *args, **options):
        assets_path = Path(options["assets_json"]).expanduser()
        carregados = load_assets_from_json(str(assets_path))
        if carregados == 0 and Ativo.objects.count() == 0:
            b3_path = Path(options["b3_csv"]).expanduser()
            if b3_path.exists():
                carregados = parse_b3_csv(str(b3_path))

        created_feeds, total_feeds = sync_feeds_from_file(options["rss"])
        self.stdout.write(
            f"Ativos: {Ativo.objects.count()} (carregados agora: {carregados})"
        )
        self.stdout.write(
            f"Feeds: {FonteRSS.objects.filter(ativo=True).count()} ativo(s) "
            f"({created_feeds} novo(s), {total_feeds} no arquivo)"
        )

        if options["skip_collect"]:
            self.stdout.write("Coleta inicial ignorada (--skip-collect).")
            return

        if FonteRSS.objects.filter(ativo=True).count() == 0:
            self.stdout.write(
                self.style.WARNING("Nenhum feed ativo; coleta inicial ignorada.")
            )
            return

        result = collect_configured_feeds(
            within_days=options["days"],
            max_entries=options["max_entries"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Coleta inicial: {result.criadas} nova(s), "
                f"{result.duplicadas} duplicada(s), {result.erros} erro(s). "
                f"Total no banco: {Noticia.objects.count()}."
            )
        )
