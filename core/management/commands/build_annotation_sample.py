from __future__ import annotations

import csv
import random
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.intelligent_motor.setores import SETORES_ANOTACAO
from pipeline_lab.models import ExperimentRun

SENTIMENTOS = ["positivo", "neutro", "negativo"]
IMPACTOS = ["baixo", "medio", "alto"]
URGENCIAS = ["alta", "media", "baixa"]
CATEGORIAS = [
    "resultados",
    "regulacao",
    "commodities",
    "macroeconomia",
    "empresa",
    "tecnologia",
    "outros",
]

ANNOTATION_FIELDS = [
    "noticia_id",
    "link",
    "fonte",
    "publicado_em",
    "titulo",
    "descricao",
    "conteudo",
    "rel_financeira",
    "rel_alerta",
    "setor",
    "setor_secundario",
    "candidatos",
    "tickers_corretos",
    "tickers_faltantes",
    "sentimento",
    "impacto",
    "urgencia",
    "categoria",
    "confianca",
    "observacao",
    "anotador",
]


def _iso(value) -> str:
    if not value:
        return ""
    try:
        return value.astimezone(timezone.utc).isoformat()
    except Exception:
        return str(value)


def _fonte(feed_url: str) -> str:
    if not feed_url:
        return ""
    try:
        from urllib.parse import urlparse

        return urlparse(feed_url).netloc
    except Exception:
        return feed_url


class Command(BaseCommand):
    help = (
        "Gera o CSV de anotação (todas as fases) a partir de uma execução, "
        "com os candidatos da Fase 2 pré-preenchidos e estratificação por "
        "Faixa 1/score heurístico."
    )

    def add_arguments(self, parser):
        parser.add_argument("--run-id", type=int, default=None)
        parser.add_argument("--output", default="exports/anotacao")
        parser.add_argument("--name", default="anotacao")
        parser.add_argument("--n-descartadas", type=int, default=130)
        parser.add_argument("--n-baixo", type=int, default=110)
        parser.add_argument("--n-cinza", type=int, default=150)
        parser.add_argument("--n-alto", type=int, default=110)
        parser.add_argument(
            "--min-explicito",
            type=int,
            default=100,
            help="Garante ao menos N notícias com ticker explícito (regex).",
        )
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--content-chars", type=int, default=1500)

    def handle(self, *args, **options):
        run = self._get_run(options["run_id"])
        rows = self._load_rows(run)
        if not rows:
            raise CommandError(f"A execução {run.id} não tem classificações.")

        rng = random.Random(options["seed"])
        amostra = self._estratificar(rows, options, rng)

        out_dir = Path(options["output"]).expanduser() / options["name"]
        out_dir.mkdir(parents=True, exist_ok=True)
        self._write_csv(amostra, out_dir / "anotacao.csv", options["content_chars"])
        self._write_diagnostico(amostra, out_dir / "diagnostico.csv")
        self._write_guia(out_dir / "LEIA-ME.txt", run)

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(amostra)} notícias para anotar em {out_dir / 'anotacao.csv'}"
            )
        )

    # ------------------------------------------------------------------ run
    def _get_run(self, run_id: int | None) -> ExperimentRun:
        if run_id:
            try:
                return ExperimentRun.objects.get(pk=run_id)
            except ExperimentRun.DoesNotExist as exc:
                raise CommandError(f"Execução {run_id} não encontrada.") from exc
        run = (
            ExperimentRun.objects.filter(status=ExperimentRun.STATUS_DONE)
            .order_by("-id")
            .first()
        )
        if run is None:
            raise CommandError("Nenhuma execução concluída. Use --run-id.")
        return run

    def _load_rows(self, run: ExperimentRun) -> list[dict]:
        rows = []
        qs = run.classifications.select_related("noticia").all()
        for item in qs:
            n = item.noticia
            rows.append(
                {
                    "noticia": n,
                    "fase1_aprovada": item.fase1_aprovada,
                    "score": item.score_heuristico,
                    "relevancia_global": item.relevancia_global,
                    "provider_fase4": item.provider_fase4 or "",
                    "relevancia_binaria": item.relevancia_binaria,
                    "confianca_fase4": item.confianca_fase4,
                    "tickers_encontrados": item.tickers_encontrados or [],
                    "tickers_relacionados": item.tickers_relacionados or [],
                }
            )
        return rows

    # ------------------------------------------------------------ sampling
    @staticmethod
    def _sample(pool: list[dict], n: int, rng: random.Random) -> list[dict]:
        if n <= 0 or not pool:
            return []
        if n >= len(pool):
            return list(pool)
        return rng.sample(pool, n)

    def _estratificar(self, rows, options, rng) -> list[dict]:
        descartadas = [r for r in rows if r["fase1_aprovada"] is False]
        mantidas = [r for r in rows if r["fase1_aprovada"] is True]

        def score(r):
            return r["score"] if r["score"] is not None else -999

        baixo = [r for r in mantidas if score(r) <= 2]
        cinza = [r for r in mantidas if 3 <= score(r) <= 6]
        alto = [r for r in mantidas if score(r) >= 7]
        sem_score = [r for r in mantidas if r["score"] is None]
        cinza = cinza + sem_score

        selecionadas = []
        selecionadas += self._sample(descartadas, options["n_descartadas"], rng)
        kept = (
            self._sample(baixo, options["n_baixo"], rng)
            + self._sample(cinza, options["n_cinza"], rng)
            + self._sample(alto, options["n_alto"], rng)
        )
        kept = self._garantir_explicito(
            kept, mantidas, options["min_explicito"], rng
        )
        selecionadas += kept

        # Deduplica preservando a ordem por id.
        vistos = set()
        unicas = []
        for r in sorted(selecionadas, key=lambda x: x["noticia"].id):
            if r["noticia"].id in vistos:
                continue
            vistos.add(r["noticia"].id)
            unicas.append(r)
        return unicas

    def _garantir_explicito(self, kept, mantidas, minimo, rng):
        def explicito(r):
            return bool(r.get("tickers_encontrados"))

        atuais = sum(1 for r in kept if explicito(r))
        if atuais >= minimo:
            return kept
        selecionados_ids = {r["noticia"].id for r in kept}
        candidatos = [
            r
            for r in mantidas
            if explicito(r) and r["noticia"].id not in selecionados_ids
        ]
        rng.shuffle(candidatos)
        faltam = minimo - atuais
        extras = candidatos[:faltam]
        # Substitui os últimos não-explícitos para não estourar o total.
        nao_expl = [r for r in kept if not explicito(r)]
        remover = {
            r["noticia"].id for r in nao_expl[: max(0, len(extras))]
        }
        return [r for r in kept if r["noticia"].id not in remover] + extras

    # -------------------------------------------------------------- output
    def _candidatos(self, row) -> list[str]:
        return sorted(
            set(row["tickers_encontrados"]) | set(row["tickers_relacionados"])
        )

    def _write_csv(self, rows, path: Path, content_chars: int) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=ANNOTATION_FIELDS, lineterminator="\n"
            )
            writer.writeheader()
            for r in rows:
                n = r["noticia"]
                writer.writerow(
                    {
                        "noticia_id": n.id,
                        "link": n.link,
                        "fonte": _fonte(getattr(n, "feed_url", "")),
                        "publicado_em": _iso(n.publicado_em),
                        "titulo": n.titulo,
                        "descricao": n.descricao,
                        "conteudo": (n.conteudo or "")[:content_chars],
                        "rel_financeira": "",
                        "rel_alerta": "",
                        "setor": "",
                        "setor_secundario": "",
                        "candidatos": "|".join(self._candidatos(r)),
                        "tickers_corretos": "",
                        "tickers_faltantes": "",
                        "sentimento": "",
                        "impacto": "",
                        "urgencia": "",
                        "categoria": "",
                        "confianca": "",
                        "observacao": "",
                        "anotador": "",
                    }
                )

    def _write_diagnostico(self, rows, path: Path) -> None:
        campos = [
            "noticia_id",
            "fase1_aprovada",
            "score_heuristico",
            "relevancia_global",
            "provider_fase4",
            "relevancia_binaria",
            "confianca_fase4",
            "n_candidatos",
            "tickers_encontrados",
            "tickers_relacionados",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=campos, lineterminator="\n")
            writer.writeheader()
            for r in rows:
                writer.writerow(
                    {
                        "noticia_id": r["noticia"].id,
                        "fase1_aprovada": r["fase1_aprovada"],
                        "score_heuristico": r["score"],
                        "relevancia_global": r["relevancia_global"],
                        "provider_fase4": r["provider_fase4"],
                        "relevancia_binaria": r["relevancia_binaria"],
                        "confianca_fase4": r["confianca_fase4"],
                        "n_candidatos": len(self._candidatos(r)),
                        "tickers_encontrados": "|".join(r["tickers_encontrados"]),
                        "tickers_relacionados": "|".join(r["tickers_relacionados"]),
                    }
                )

    def _write_guia(self, path: Path, run: ExperimentRun) -> None:
        linhas = [
            "=== Guia de anotação — Monitor Financeiro Inteligente ===",
            f"Execução: run {run.id} ({run.modelo})",
            "",
            "Uma linha por notícia. Preencha:",
            "",
            "rel_financeira : 1 se a notícia é do mercado financeiro (Fase 1); senão 0.",
            "rel_alerta     : 1 se, para um investidor, a notícia é relevante/acionável (Fase 4); senão 0.",
            "setor          : setor principal da notícia (ver lista abaixo); use 'Macro/Mercado' para notícias gerais.",
            "setor_secundario (opcional): segundo setor, se houver.",
            "tickers_corretos: subconjunto de 'candidatos' que a notícia afeta MATERIALMENTE,",
            "                  separado por '|'. Se nenhum, escreva NENHUM.",
            "tickers_faltantes: tickers que deveriam estar na lista e não estão (opcional).",
            "sentimento     : " + " / ".join(SENTIMENTOS),
            "impacto        : " + " / ".join(IMPACTOS),
            "urgencia       : " + " / ".join(URGENCIAS),
            "categoria      : " + " / ".join(CATEGORIAS),
            "confianca      : 1 (baixa) a 3 (alta) — sua confiança na linha.",
            "",
            "Regra dos tickers: marque CORRETO só se a empresa é mencionada ou é",
            "claramente afetada (impacto direto, não especulativo). 'Mesmo setor' NÃO basta.",
            "Exemplo: notícia da PETR4 -> PETR4 correto; BRKM5/PRIO3/DOW/AVY incorretos.",
            "",
            "Setores:",
        ]
        linhas += [f"  - {s}" for s in SETORES_ANOTACAO]
        linhas += [
            "",
            "Grade da amostra (descartadas na Fase 1 ficam sem setor/tickers quando não couber).",
            "Campos vazios = não anotado (não entram na métrica correspondente).",
        ]
        path.write_text("\n".join(linhas), encoding="utf-8")
