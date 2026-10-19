# Legado

Este diretório guarda o software antigo do projeto (monitor/scheduler com o
pipeline embutido na coleta). Ele foi movido para cá para separar o código do
TCC da versão anterior e **não é carregado pela aplicação atual**.

## O que veio para cá

- `startup.py` — auto-start do monitor/scheduler no `runserver` (removido).
- `workflows.py` — workflows `run_monitor`/`run_scheduler`.
- `management_commands/run_monitor.py` e `run_scheduler.py` — comandos Django
  antigos. Como não ficam em `core/management/commands/`, não são mais
  descobertos pelo `manage.py`.
- `scheduler/` — APScheduler `BackgroundScheduler` que coletava e disparava o
  pipeline.
- `scripts/export_notices.py`, `build_dataset.py`,
  `popular_embeddings_agora.py`, `listar_tickers.py` — utilitários antigos.

## Substitutos atuais

| Antigo | Atual |
|--------|-------|
| `run_monitor` / `run_scheduler` | `python manage.py run_collector` |
| coleta + pipeline juntos | coleta grava `Noticia` crua; `/lab/` cria `ExperimentRun` e o worker processa |
| `scripts/export_notices.py` | `python manage.py export_dataset` |
| `scripts/popular_embeddings_agora.py` | geração automática de `AssetEmbedding` pelo worker (Fase 2) |
| `scripts/build_dataset.py` | `python manage.py export_dataset` |
