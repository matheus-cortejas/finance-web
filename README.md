# Finance Web — TCC

Sistema de coleta de notícias financeiras e de experimentos com modelos de
embeddings. A coleta é **independente** do pipeline: ela grava a notícia crua no
banco e não carrega modelo de embeddings, pipeline ou LLM. O processamento roda
depois, pelo laboratório de experimentos, com o modelo escolhido pela interface
web.

> O software antigo (monitor/scheduler com pipeline embutido) foi isolado em
> [`legacy/`](legacy/README.md) e não é mais carregado pela aplicação.

## Arquitetura

```
web        → interface Django (dashboard, /lab/, admin, /healthz/)
migrate    → aplica migrações (roda uma vez, antes dos demais)
collector  → coleta RSS crua, sem pipeline (processo contínuo)
worker     → processa execuções pendentes do laboratório
db         → PostgreSQL 16
bootstrap  → popula ativos/feeds e faz coleta inicial (one-shot)
exporter   → exporta JSONL + manifest.json + CSV de anotação (one-shot)
```

Fluxo:

```
RSS → collector → Noticia (crua) → /lab/ cria ExperimentRun
     → worker → RunClassification → métricas → export_dataset
```

## Rodando localmente (sem Docker)

```bash
python -m venv venv
./venv/bin/python -m pip install -r requirements.txt

# .env (opcional no SQLite)
cp .env.docker.example .env

./venv/bin/python manage.py migrate
./venv/bin/python manage.py bootstrap          # ativos + feeds + coleta inicial
./venv/bin/python manage.py createsuperuser
./venv/bin/python manage.py runserver
```

Acesse `http://localhost:8000/`. O laboratório fica em `/lab/` (usuário staff).

## Rodando com Docker

```bash
cp .env.docker.example .env      # ajuste senha e chave
docker compose up -d --build     # db, migrate, web, collector, worker
docker compose ps
```

Serviços one-shot (perfil `tools`):

```bash
# Popula ativos/feeds e faz a coleta inicial
docker compose --profile tools run --rm bootstrap

# Exporta um dataset para ./exports
docker compose --profile tools run --rm exporter
```

### Migrar o corpus do SQLite legado

Preservando IDs, 16.348 notícias e 9.140 classificações:

```bash
# garanta que ./db.sqlite3 existe na raiz do projeto
docker compose --profile tools run --rm migrate-data
```

Se `./db.sqlite3` não existir, o serviço falha com uma mensagem clara (sem
criar um diretório vazio no host). O comando também falha de propósito se o
destino já tiver notícias; use `--force` (via `command` do serviço) apenas
quando quiser sobrescrever.

### Perfil com GPU (opcional, ainda não validado)

`web` e `worker` podem rodar em GPU NVIDIA; `db`, `migrate`, `collector`,
`bootstrap` e `exporter` continuam em CPU.

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

O overlay `compose.gpu.yaml` reconstrói a imagem como `finance-web:gpu`
usando PyTorch CUDA (`cu124`) e define `EMBEDDING_DEVICE=cuda`. Pré-requisitos
no host: driver NVIDIA + `nvidia-container-toolkit` (no WSL2, integração de
GPU habilitada). O build baixa vários GB.

> Este perfil foi apenas preparado; falta validar numa máquina com GPU.

## Comandos de gerenciamento

| Comando | Descrição |
|---------|-----------|
| `migrate` | Aplica migrações do Django. |
| `bootstrap` | Carrega `core_ativos.json`, sincroniza `rss.txt` e coleta. `--skip-collect` só prepara. |
| `run_collector` | Coleta contínua via `BlockingScheduler`. `--once`, `--interval`, `--within-days`, `--max-entries`. |
| `sync_feeds` | Sincroniza `FonteRSS` a partir de `rss.txt`. |
| `run_experiments` | Worker de execuções. `--once`, `--run-id`, `--poll-seconds`. |
| `compute_metrics` | Recalcula métricas de uma execução. `--run-id N` ou `--all`. |
| `import_labels` | Importa labels anotados (CSV) para `NewsLabel`. |
| `export_dataset` | Exporta JSONL + `manifest.json` + `annotation_sample.csv`. |
| `migrate_sqlite_to_postgres` | Migra o corpus do SQLite para o PostgreSQL preservando IDs. |

Exemplos:

```bash
./venv/bin/python manage.py run_collector --once --max-entries 5
./venv/bin/python manage.py run_experiments --once
./venv/bin/python manage.py export_dataset --output exports --sample-size 300 --run-id 3
./venv/bin/python manage.py import_labels --csv exports/ds/annotation_sample.csv
./venv/bin/python manage.py compute_metrics --run-id 3
```

## Laboratório (`/lab/`)

- Cria uma `ExperimentRun` escolhendo modelo de embeddings, limite, janela de
  datas, `stop_after` (1–5) e se usa LLM.
- Fases 4 e 5 podem rodar com fallback heurístico quando `usar_llm=0`
  (não exige `OPENAI_API_KEY`).
- O worker processa as execuções pendentes, retoma execuções interrompidas e
  aceita cancelamento.
- `/lab/compare/` compara F1, melhor score e melhor similaridade global entre
  execuções. Fases sem labels avaliados aparecem como `—`.

## Experimentos do TCC

- O modelo de embeddings é configurável por execução (`ExperimentRun.modelo`).
- Os embeddings de ativos ficam em `AssetEmbedding`, com namespace por modelo.
- Modelos locais em `core/intelligent_motor/models/` ou IDs do Hugging Face.
- Sem GPU: `EMBEDDING_DEVICE=cpu` e imagem Docker com PyTorch CPU.
- Cache de Fase 1 e store de embeddings usam o mesmo namespace de modelo.

Variáveis principais:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DATABASE_URL` | — | Se vazia, usa SQLite (`db.sqlite3`). |
| `EMBEDDING_DEVICE` | `cpu` | `cpu` ou `cuda`. |
| `EMBEDDING_MODELS` | `paraphrase-multilingual-MiniLM-L12-v2` | Modelos disponíveis na UI. |
| `COLLECTOR_INTERVAL_SECONDS` | `300` | Intervalo da coleta contínua. |
| `WORKER_POLL_SECONDS` | `10` | Intervalo de busca por execuções pendentes. |
| `EXPERIMENT_BATCH_SIZE` | `16` | Tamanho do lote ao iterar notícias. |
| `EXPERIMENT_CACHE_ENABLED` | `0` | Habilita cache da Fase 1. |
| `OPENAI_API_KEY` | — | Opcional; sem ela, Fases 4/5 usam fallback. |
| `PIPELINE_METRICS_PATH` | `pipeline_metrics.jsonl` | JSONL de métricas do pipeline. |

## Dataset exportado

Cada execução do `export_dataset` cria uma pasta com:

- `noticias.jsonl` — uma notícia por linha, já com a classificação da execução
  (`--run-id`) e o label anotado, quando existir.
- `manifest.json` — filtros usados, contagens, tamanho e SHA-256 dos arquivos.
- `annotation_sample.csv` — amostra para anotação manual. Por padrão prioriza
  notícias com conteúdo; use `--sample-all` para amostrar todas.

```bash
./venv/bin/python manage.py export_dataset \
  --output exports --name tcc-v1 \
  --run-id 3 --sample-size 300 --seed 42
```

## Estrutura

```
finance-web/
├── setup/                          # settings, URLs, WSGI, logging
├── core/
│   ├── models.py                   # Noticia, Ativo, FonteRSS, Carteira...
│   ├── services/collector_service.py
│   ├── intelligent_motor/          # pipeline de 6 fases
│   └── management/commands/        # coleta, experimentos, exportação
├── pipeline_lab/                   # app dos experimentos (UI + worker)
├── templates/                      # dashboard, notícias, lab
├── static/
├── legacy/                         # software antigo preservado (não usado)
├── compose.yaml
├── compose.gpu.yaml
├── Dockerfile
├── rss.txt                         # fontes RSS
├── core_ativos.json                # base de ativos
└── requirements.txt
```

## Testes

```bash
./venv/bin/python manage.py test core -v 2
```

Os testes cobrem normalização/deduplicação da coleta, exportação, criação e
métricas de execuções, store de embeddings, pipeline sem LLM e a UI do `/lab/`.
Nenhum teste carrega modelo ou acessa rede.
