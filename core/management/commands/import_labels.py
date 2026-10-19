from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import Noticia
from pipeline_lab.models import NewsLabel


def parse_bool(value) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "sim", "s", "yes", "y", "relevante"}:
        return True
    if text in {"0", "false", "nao", "não", "n", "no", "irrelevante"}:
        return False
    return None


class Command(BaseCommand):
    help = "Importa o CSV de anotação para a tabela NewsLabel."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--anotador", default="")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["csv_path"]).expanduser()
        if not path.exists():
            raise CommandError(f"CSV não encontrado: {path}")

        criados = atualizados = ignorados = invalidos = 0

        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"noticia_id"}
            if not required.issubset(reader.fieldnames or []):
                raise CommandError("O CSV precisa da coluna noticia_id.")

            for row in reader:
                raw_id = (row.get("noticia_id") or "").strip()
                if not raw_id:
                    invalidos += 1
                    continue
                try:
                    noticia_id = int(raw_id)
                except ValueError:
                    invalidos += 1
                    continue
                if not Noticia.objects.filter(pk=noticia_id).exists():
                    invalidos += 1
                    continue

                defaults = {}
                relevancia = parse_bool(row.get("relevancia"))
                if relevancia is not None:
                    defaults["relevancia"] = relevancia

                for field, max_len in (
                    ("sentimento", 16),
                    ("impacto", 16),
                    ("categoria", 64),
                ):
                    value = (row.get(field) or "").strip().lower()
                    if value:
                        defaults[field] = value[:max_len]

                observacao = (row.get("observacao") or "").strip()
                if observacao:
                    defaults["observacao"] = observacao

                anotador = (
                    (row.get("anotador") or "").strip()
                    or options["anotador"]
                )
                if anotador:
                    defaults["anotador"] = anotador[:150]

                if not defaults:
                    ignorados += 1
                    continue

                if options["dry_run"]:
                    atualizados += 1
                    continue

                _, created = NewsLabel.objects.update_or_create(
                    noticia_id=noticia_id, defaults=defaults
                )
                if created:
                    criados += 1
                else:
                    atualizados += 1

        prefixo = "[dry-run] " if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefixo}criados={criados} atualizados={atualizados} "
                f"ignorados={ignorados} inválidos={invalidos}"
            )
        )
