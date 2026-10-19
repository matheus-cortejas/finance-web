from __future__ import annotations

import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import Noticia
from pipeline_lab.models import NewsLabel

# Sentinela usada na coluna de tickers para indicar "anotei, nenhum correto".
_NENHUM = {"nenhum", "nenhuma", "-", "n/a", "na", "vazio", "sem"}

_LIST_SPLIT = re.compile(r"[|;,]+")


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


def parse_list(value) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() in _NENHUM:
        return []
    itens = []
    for parte in _LIST_SPLIT.split(text):
        item = parte.strip().upper()
        if item and item not in itens and item.lower() not in _NENHUM:
            itens.append(item)
    return itens


def _tickers_cell_revisada(value) -> bool:
    """True se a célula foi preenchida (inclusive 'NENHUM')."""
    if value is None:
        return False
    return bool(str(value).strip())


def parse_urgencia(value) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    if text in {"alta", "media", "média", "baixa", "indefinida"}:
        return "media" if text == "média" else text
    try:
        numero = float(text)
    except ValueError:
        return text[:16]
    if numero >= 7:
        return "alta"
    if numero >= 4:
        return "media"
    return "baixa"


def parse_int(value) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
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

                # Fase 4 (compatível com a coluna antiga `relevancia`).
                relevancia = parse_bool(
                    row.get("rel_alerta", row.get("relevancia"))
                )
                if relevancia is not None:
                    defaults["relevancia"] = relevancia

                # Fase 1.
                rel_fin = parse_bool(
                    row.get("rel_financeira", row.get("relevancia_financeira"))
                )
                if rel_fin is not None:
                    defaults["relevancia_financeira"] = rel_fin

                for field, max_len in (
                    ("sentimento", 16),
                    ("impacto", 16),
                    ("categoria", 64),
                    ("setor", 64),
                    ("setor_secundario", 64),
                ):
                    value = (row.get(field) or "").strip()
                    if value:
                        defaults[field] = value[:max_len]

                urgencia = parse_urgencia(row.get("urgencia"))
                if urgencia:
                    defaults["urgencia"] = urgencia[:16]

                confianca = parse_int(row.get("confianca"))
                if confianca is not None:
                    defaults["confianca"] = max(1, min(3, confianca))

                if any(
                    col in (reader.fieldnames or [])
                    for col in ("tickers_corretos", "tickers_faltantes")
                ):
                    cell = row.get("tickers_corretos")
                    revisada = _tickers_cell_revisada(cell)
                    if revisada:
                        defaults["tickers_corretos"] = parse_list(cell)
                    faltantes = parse_list(row.get("tickers_faltantes"))
                    if faltantes:
                        defaults["tickers_faltantes"] = faltantes
                    if revisada or _tickers_cell_revisada(
                        row.get("tickers_faltantes")
                    ):
                        defaults["tickers_anotados"] = True

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
