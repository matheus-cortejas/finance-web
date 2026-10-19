from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction


# Ordem respeita as dependências de chave estrangeira.
TABLES = [
    "auth_user",
    "core_ativo",
    "core_fonterss",
    "core_carteira",
    "core_perfilinvestidor",
    "core_noticia",
    "core_noticiaclassificacao",
    "core_noticiascore",
    "core_interacaonoticia",
    "core_alerta",
    "core_carteira_ativos",
    "core_alerta_ativos",
]

# Colunas que não existem no SQLite antigo e recebem valor depois da cópia.
POST_COPY_SQL = [
    """
    UPDATE core_noticia
       SET coletado_em = COALESCE(publicado_em, NOW())
     WHERE coletado_em IS NULL
    """,
]


class Command(BaseCommand):
    help = "Copia os dados do SQLite legado para o PostgreSQL configurado em DATABASE_URL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="db.sqlite3",
            help="Caminho do SQLite de origem (padrão: db.sqlite3).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Linhas por lote (padrão: 1000).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Continua mesmo que o destino já tenha dados (usa ON CONFLICT DO NOTHING).",
        )
        parser.add_argument(
            "--verify-only",
            action="store_true",
            help="Apenas compara as contagens origem/destino.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria copiado, sem gravar.",
        )

    def handle(self, *args, **options):
        source_path = Path(options["source"]).resolve()
        if not source_path.exists():
            raise CommandError(f"SQLite não encontrado: {source_path}")

        target = connections["default"]
        if target.vendor != "postgresql":
            raise CommandError(
                "Este comando só funciona com PostgreSQL. "
                f"Banco atual: {target.vendor}."
            )

        source = sqlite3.connect(str(source_path))
        source.row_factory = sqlite3.Row

        try:
            self._check_source(source)
            self._cleanup_bootstrap_admin(source, target)
            source_counts = self._source_counts(source)
            target_counts = self._target_counts(target)

            if options["verify_only"]:
                self._print_counts(source_counts, target_counts)
                self._verify(source_counts, target_counts)
                return

            if not options["force"] and not options["dry_run"]:
                existing = {
                    table: count
                    for table, count in target_counts.items()
                    if count and table in {"core_noticia", "core_ativo", "core_fonterss", "auth_user"}
                }
                if existing:
                    raise CommandError(
                        "O destino já possui dados "
                        f"({existing}). Use --force para complementar "
                        "ou limpe o banco antes de migrar."
                    )

            if options["dry_run"]:
                self._print_counts(source_counts, target_counts)
                self.stdout.write(
                    self.style.WARNING("Dry-run: nenhuma linha foi gravada.")
                )
                return

            self.stdout.write("Copiando dados...")
            for table in TABLES:
                copied = self._copy_table(
                    source,
                    target,
                    table,
                    batch_size=options["batch_size"],
                )
                self.stdout.write(f"  {table}: {copied} linha(s)")

            with target.cursor() as cursor:
                for sql in POST_COPY_SQL:
                    cursor.execute(sql)

            self._reset_sequences(target)
            self.stdout.write("Sequências ajustadas.")

            target_counts = self._target_counts(target)
            self._print_counts(source_counts, target_counts)
            self._verify(source_counts, target_counts)
            self.stdout.write(self.style.SUCCESS("Migração concluída."))
        finally:
            source.close()

    # ------------------------------------------------------------------ helpers

    def _check_source(self, source: sqlite3.Connection) -> None:
        existing = {
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing = [table for table in TABLES if table not in existing]
        if missing:
            raise CommandError(
                "Tabelas ausentes no SQLite: " + ", ".join(missing)
            )

    def _cleanup_bootstrap_admin(
        self,
        source: sqlite3.Connection,
        target,
    ) -> None:
        """Remove o admin criado pela migração 0008 em um destino vazio.

        A migração `core.0008_auto_create_admin_portfolio` cria um usuário
        `admin` quando o banco está vazio. Se o SQLite legado tem exatamente
        esse usuário e o destino ainda não tem notícias, o admin placeholder é
        removido para que o usuário original (com o hash de senha) seja
        copiado com o mesmo ID.
        """
        from django.contrib.auth.models import User

        source_users = source.execute(
            "SELECT id, username FROM auth_user"
        ).fetchall()
        if len(source_users) != 1:
            return

        _, source_username = source_users[0]
        with target.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM core_noticia")
            if cursor.fetchone()[0]:
                return

        target_users = list(User.objects.values_list("id", "username"))
        if (
            len(target_users) == 1
            and target_users[0][1] == source_username
        ):
            self.stdout.write(
                self.style.WARNING(
                    f"Removendo admin placeholder id={target_users[0][0]} "
                    f"para preservar o usuário {source_username!r}."
                )
            )
            User.objects.filter(pk=target_users[0][0]).delete()

    def _source_counts(self, source: sqlite3.Connection) -> dict[str, int]:
        return {
            table: source.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in TABLES
        }

    def _target_counts(self, connection) -> dict[str, int]:
        counts: dict[str, int] = {}
        with connection.cursor() as cursor:
            for table in TABLES:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    counts[table] = cursor.fetchone()[0]
                except Exception:
                    counts[table] = -1
        return counts

    def _target_columns(self, connection, table: str) -> dict[str, str]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = %s
                """,
                [table],
            )
            return {name: dtype for name, dtype in cursor.fetchall()}

    def _copy_table(
        self,
        source: sqlite3.Connection,
        target,
        table: str,
        *,
        batch_size: int,
    ) -> int:
        source_columns = {
            row[1] for row in source.execute(f'PRAGMA table_info("{table}")')
        }
        target_columns = self._target_columns(target, table)
        if not target_columns:
            raise CommandError(
                f"Tabela {table} não existe no PostgreSQL. Rode `manage.py migrate` antes."
            )

        # Interseção preservando a ordem do modelo de destino.
        columns = [name for name in target_columns if name in source_columns]
        if not columns:
            return 0

        quoted_columns = ", ".join(f'"{name}"' for name in columns)
        placeholders = ", ".join(
            self._placeholder(target_columns[name]) for name in columns
        )
        sql = (
            f'INSERT INTO "{table}" ({quoted_columns}) '
            f"VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        )

        select_sql = (
            f'SELECT {", ".join(f""" "{name}" """ for name in columns)} '
            f'FROM "{table}"'
        )

        copied = 0
        cursor = source.execute(select_sql)
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            values = [
                tuple(self._convert(value, target_columns[name]) for name, value in zip(columns, row))
                for row in rows
            ]
            with transaction.atomic(using="default"):
                with target.cursor() as target_cursor:
                    target_cursor.executemany(sql, values)
            copied += len(values)
        return copied

    @staticmethod
    def _placeholder(data_type: str) -> str:
        if data_type == "jsonb":
            return "%s::jsonb"
        if data_type == "timestamp with time zone":
            return "%s::timestamptz"
        if data_type == "timestamp without time zone":
            return "%s::timestamp"
        if data_type == "date":
            return "%s::date"
        return "%s"

    @staticmethod
    def _convert(value, data_type: str):
        if value is None:
            return None

        if data_type == "boolean":
            return bool(value)

        if data_type == "jsonb":
            if value == "":
                return None
            if isinstance(value, (bytes, bytearray)):
                value = value.decode("utf-8")
            if isinstance(value, str):
                try:
                    return json.dumps(json.loads(value))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"JSON inválido: {value[:80]!r}") from exc
            return json.dumps(value)

        if data_type in {"timestamp with time zone", "timestamp without time zone"}:
            if value == "":
                return None
            return value

        if data_type == "date" and value == "":
            return None

        return value

    def _reset_sequences(self, connection) -> None:
        with connection.cursor() as cursor:
            for table in TABLES:
                try:
                    cursor.execute(
                        f"""
                        SELECT setval(
                            pg_get_serial_sequence(%s, 'id'),
                            COALESCE(MAX(id), 1),
                            MAX(id) IS NOT NULL
                        )
                          FROM "{table}"
                        """,
                        [table],
                    )
                except Exception:
                    # Tabelas sem sequência (ex.: through table sem id) são ignoradas.
                    continue

    def _print_counts(self, source: dict[str, int], target: dict[str, int]) -> None:
        self.stdout.write(f"{'tabela':30} {'sqlite':>10} {'postgres':>10}")
        for table in TABLES:
            self.stdout.write(
                f"{table:30} {source.get(table, -1):>10} {target.get(table, -1):>10}"
            )

    def _verify(self, source: dict[str, int], target: dict[str, int]) -> None:
        problems = []
        for table in TABLES:
            if source[table] != target.get(table):
                problems.append(
                    f"{table}: sqlite={source[table]} postgres={target.get(table)}"
                )
        if problems:
            raise CommandError(
                "Contagens divergentes:\n  " + "\n  ".join(problems)
            )
