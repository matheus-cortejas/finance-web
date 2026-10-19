from __future__ import annotations

import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Prefetch

from core.models import Noticia
from pipeline_lab.models import ExperimentRun, RunClassification


def _iso(value) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _fonte(feed_url: str) -> str:
    if not feed_url:
        return ""
    try:
        return urlsplit(feed_url).netloc.lower()
    except Exception:
        return ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_info(path: Path, linhas: int) -> dict:
    return {
        "arquivo": path.name,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "linhas": linhas,
    }


def _label_dict(label) -> dict | None:
    if label is None:
        return None
    return {
        "relevancia": label.relevancia,
        "sentimento": label.sentimento,
        "impacto": label.impacto,
        "categoria": label.categoria,
        "observacao": label.observacao,
        "anotador": label.anotador,
        "anotado_em": _iso(label.anotado_em),
    }


def _classificacao_legada(classificacao) -> dict | None:
    if classificacao is None:
        return None
    return {
        "sentimento": classificacao.sentimento,
        "impacto": classificacao.impacto,
        "urgencia": classificacao.urgencia,
        "setor": classificacao.setor,
        "tipo_evento": classificacao.tipo_evento,
        "tickers_relacionados": classificacao.tickers_relacionados,
        "tickers_encontrados": classificacao.tickers_encontrados,
        "relevancia_llm": classificacao.relevancia_llm,
        "confianca_fase4": classificacao.confianca_fase4,
        "provider_fase4": classificacao.provider_fase4,
        "explicacao": classificacao.explicacao,
    }


def _run_dict(item: RunClassification | None) -> dict | None:
    if item is None:
        return None
    return {
        "fase1_aprovada": item.fase1_aprovada,
        "relevancia_global": item.relevancia_global,
        "tickers_relacionados": item.tickers_relacionados,
        "tickers_encontrados": item.tickers_encontrados,
        "score_heuristico": item.score_heuristico,
        "criterios_ativados": item.criterios_ativados,
        "relevancia_binaria": item.relevancia_binaria,
        "confianca_fase4": item.confianca_fase4,
        "provider_fase4": item.provider_fase4,
        "sentimento": item.sentimento,
        "impacto": item.impacto,
        "urgencia": item.urgencia,
        "categoria": item.categoria,
        "explicacao": item.explicacao,
        "erro": item.erro,
    }


class Command(BaseCommand):
    help = "Exporta o corpus para JSONL + manifest.json + CSV de anotação."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="exports",
            help="Diretório base onde a pasta do dataset será criada.",
        )
        parser.add_argument(
            "--name",
            default=None,
            help="Nome da pasta do dataset (padrão: dataset_YYYYmmdd_HHMMSS).",
        )
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--since", default=None, help="Data ISO mínima de publicação.")
        parser.add_argument("--until", default=None, help="Data ISO máxima de publicação.")
        parser.add_argument(
            "--only-with-content",
            action="store_true",
            help="Exporta apenas notícias com conteúdo não vazio.",
        )
        parser.add_argument(
            "--run-id",
            type=int,
            default=None,
            help="Inclui no JSONL o resultado de uma execução do laboratório.",
        )
        parser.add_argument(
            "--only-run",
            action="store_true",
            help=(
                "Exporta apenas as notícias classificadas pela execução "
                "indicada (exige --run-id)."
            ),
        )
        parser.add_argument(
            "--sample-size",
            type=int,
            default=300,
            help="Tamanho da amostra do CSV de anotação (padrão: 300).",
        )
        parser.add_argument(
            "--sample-all",
            action="store_true",
            help="Permite amostrar notícias sem conteúdo (por padrão prioriza com conteúdo).",
        )
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument(
            "--annotation-content-chars",
            type=int,
            default=2000,
            help="Limite de caracteres do conteúdo no CSV de anotação.",
        )

    def handle(self, *args, **options):
        output_base = Path(options["output"]).expanduser().resolve()
        name = options["name"] or datetime.now().strftime("dataset_%Y%m%d_%H%M%S")
        output_dir = output_base / name
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError(f"Diretório já existe e não está vazio: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)

        qs = Noticia.objects.all().order_by("id")
        if options["since"]:
            qs = qs.filter(publicado_em__gte=self._parse_dt(options["since"]))
        if options["until"]:
            qs = qs.filter(publicado_em__lte=self._parse_dt(options["until"]))
        if options["only_with_content"]:
            qs = qs.exclude(conteudo__isnull=True).exclude(conteudo="")

        run = None
        if options["run_id"]:
            try:
                run = ExperimentRun.objects.get(pk=options["run_id"])
            except ExperimentRun.DoesNotExist as exc:
                raise CommandError(f"Execução {options['run_id']} não encontrada.") from exc

        if options["only_run"]:
            if run is None:
                raise CommandError("--only-run exige --run-id.")
            qs = qs.filter(run_classifications__run=run).distinct()

        if options["limit"]:
            qs = qs[: options["limit"]]

        if run is not None:
            qs = qs.prefetch_related(
                Prefetch(
                    "run_classifications",
                    queryset=RunClassification.objects.filter(run=run),
                    to_attr="run_items",
                )
            )

        qs = qs.select_related("label", "classificacao")

        jsonl_path = output_dir / "noticias.jsonl"
        total = 0
        com_conteudo = 0
        com_label = 0
        com_classificacao = 0
        com_run = 0
        publicado_min = None
        publicado_max = None

        with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
            for noticia in qs.iterator(chunk_size=1000):
                label = noticia.label if hasattr(noticia, "label") else None
                classificacao = (
                    noticia.classificacao if hasattr(noticia, "classificacao") else None
                )
                run_item = (
                    noticia.run_items[0]
                    if getattr(noticia, "run_items", None)
                    else None
                )
                record = {
                    "id": noticia.id,
                    "link": noticia.link,
                    "titulo": noticia.titulo,
                    "descricao": noticia.descricao,
                    "conteudo": noticia.conteudo or "",
                    "publicado_em": _iso(noticia.publicado_em),
                    "coletado_em": _iso(noticia.coletado_em),
                    "feed_url": noticia.feed_url or "",
                    "fonte": _fonte(noticia.feed_url),
                    "label": _label_dict(label),
                    "classificacao_legada": _classificacao_legada(classificacao),
                    "run": _run_dict(run_item),
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

                total += 1
                if record["conteudo"]:
                    com_conteudo += 1
                if label is not None:
                    com_label += 1
                if classificacao is not None:
                    com_classificacao += 1
                if run_item is not None:
                    com_run += 1
                if noticia.publicado_em:
                    if publicado_min is None or noticia.publicado_em < publicado_min:
                        publicado_min = noticia.publicado_em
                    if publicado_max is None or noticia.publicado_em > publicado_max:
                        publicado_max = noticia.publicado_em

        annotation_path = output_dir / "annotation_sample.csv"
        all_ids = list(qs.values_list("id", flat=True))
        sample_pool = all_ids
        if all_ids and not options["sample_all"]:
            content_ids = set(
                Noticia.objects.filter(id__in=all_ids)
                .exclude(conteudo__isnull=True)
                .exclude(conteudo="")
                .values_list("id", flat=True)
            )
            preferred = [
                noticia_id for noticia_id in all_ids if noticia_id in content_ids
            ]
            if len(preferred) >= options["sample_size"]:
                sample_pool = preferred

        rng = random.Random(options["seed"])
        sample_size = max(0, min(options["sample_size"], len(sample_pool)))
        if sample_size:
            sample_ids = sorted(rng.sample(sample_pool, sample_size))
        else:
            sample_ids = []

        annotation_rows = 0
        with annotation_path.open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "noticia_id",
                    "link",
                    "titulo",
                    "descricao",
                    "conteudo",
                    "publicado_em",
                    "fonte",
                    "relevancia",
                    "sentimento",
                    "impacto",
                    "categoria",
                    "observacao",
                    "anotador",
                ],
                lineterminator="\n",
            )
            writer.writeheader()
            if sample_ids:
                for noticia in (
                    Noticia.objects.filter(id__in=sample_ids)
                    .select_related("label")
                    .order_by("id")
                ):
                    label = noticia.label if hasattr(noticia, "label") else None
                    writer.writerow(
                        {
                            "noticia_id": noticia.id,
                            "link": noticia.link,
                            "titulo": noticia.titulo,
                            "descricao": noticia.descricao,
                            "conteudo": (noticia.conteudo or "")[
                                : options["annotation_content_chars"]
                            ],
                            "publicado_em": _iso(noticia.publicado_em) or "",
                            "fonte": _fonte(noticia.feed_url),
                            "relevancia": (
                                ""
                                if label is None or label.relevancia is None
                                else ("1" if label.relevancia else "0")
                            ),
                            "sentimento": label.sentimento if label else "",
                            "impacto": label.impacto if label else "",
                            "categoria": label.categoria if label else "",
                            "observacao": label.observacao if label else "",
                            "anotador": label.anotador if label else "",
                        }
                    )
                    annotation_rows += 1

        manifest = {
            "schema_version": 1,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "gerado_por": "export_dataset",
            "total_noticias": total,
            "com_conteudo": com_conteudo,
            "com_label": com_label,
            "com_classificacao_legada": com_classificacao,
            "com_resultado_run": com_run,
            "publicado_em_min": _iso(publicado_min),
            "publicado_em_max": _iso(publicado_max),
            "filtros": {
                "limit": options["limit"],
                "since": options["since"],
                "until": options["until"],
                "only_with_content": options["only_with_content"],
                "run_id": options["run_id"],
                "only_run": options["only_run"],
                "sample_size": options["sample_size"],
                "sample_all": options["sample_all"],
                "seed": options["seed"],
            },
            "run": (
                {
                    "id": run.id,
                    "nome": run.nome,
                    "modelo": run.modelo,
                    "modelo_revision": run.modelo_revision,
                    "embedding_dim": run.embedding_dim,
                    "status": run.status,
                    "config": run.config,
                }
                if run
                else None
            ),
            "arquivos": {
                "noticias": _file_info(jsonl_path, total),
                "annotation_sample": _file_info(
                    annotation_path, annotation_rows + 1
                ),
            },
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Exportação concluída em {output_dir} "
                f"({total} notícia(s), {sample_size} para anotação)."
            )
        )

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise CommandError(f"Data inválida: {value!r}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
