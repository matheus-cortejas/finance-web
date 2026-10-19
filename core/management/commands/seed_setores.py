from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from core.intelligent_motor.setores import setor_do_ativo
from core.models import Ativo

DEFAULT_MAPPING_PATH = (
    Path(__file__).resolve().parents[2]
    / "intelligent_motor"
    / "fase2_tickers"
    / "ativos_mapeamento.json"
)


class Command(BaseCommand):
    help = (
        "Preenche Ativo.setor a partir do nome/descrição (classificador por "
        "palavras-chave). Use --from-json para aplicar um mapeamento manual."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-json",
            default=None,
            help="Caminho de um JSON {ticker: setor} para aplicar (overrides).",
        )
        parser.add_argument(
            "--export",
            default=None,
            help="Grava o mapeamento calculado (ticker->setor) em um JSON.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Sobrescreve setores já preenchidos (por padrão só preenche vazios).",
        )
        parser.add_argument(
            "--source",
            default="",
            help="Restringe a ativos com este source (b3, sp500). Vazio = todos.",
        )

    def _descricoes_legado(self) -> dict:
        if not DEFAULT_MAPPING_PATH.exists():
            return {}
        try:
            data = json.loads(DEFAULT_MAPPING_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def handle(self, *args, **options):
        legado = self._descricoes_legado()

        if options["from_json"]:
            path = Path(options["from_json"]).expanduser()
            mapping = json.loads(path.read_text(encoding="utf-8"))
            atualizados = 0
            for ticker, setor in mapping.items():
                atualizados += Ativo.objects.filter(ticker=ticker).update(
                    setor=setor
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Aplicados {atualizados} setores de {len(mapping)} entradas "
                    f"({path})."
                )
            )
            if options["export"]:
                self._export(mapping, options["export"])
            return

        qs = Ativo.objects.all()
        if options["source"]:
            qs = qs.filter(source=options["source"])

        calculado: dict[str, str] = {}
        atualizados = 0
        for ativo in qs.only("ticker", "nome", "descricao_embedding", "setor"):
            if ativo.setor and not options["force"]:
                calculado[ativo.ticker] = ativo.setor
                continue
            descricao = ativo.descricao_embedding or legado.get(ativo.ticker, "")
            setor = setor_do_ativo(ativo.nome, descricao)
            calculado[ativo.ticker] = setor
            if setor != ativo.setor or options["force"]:
                Ativo.objects.filter(pk=ativo.pk).update(setor=setor)
                atualizados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Setores atualizados: {atualizados} de {len(calculado)} ativos."
            )
        )
        if options["export"]:
            self._export(calculado, options["export"])

    def _export(self, mapping: dict, path_repr: str) -> None:
        path = Path(path_repr).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(f"Mapeamento gravado em {path}."))
