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
| `generate_run_charts` | Gera gráficos/artefatos da execução em `exports/lab/run-<id>/`. `--run-id N`. |
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
  datas, `stop_after` (1–5), device (`auto`/`cpu`/`cuda`) e se usa LLM.
- **Parâmetros por execução** (painel "Parâmetros avançados"): limiar de
  relevância da Fase 1 e seus centroides, limiar de similaridade da Fase 2, os
  11 pesos da Fase 3 e os cortes da Fase 4 (rejeição, faixa do LLM, aprovação e
  fallback). Só o que difere do `config.yaml` é gravado em
  `ExperimentRun.config["overrides"]`, com o resultado final em
  `config["efetivo"]`. A Fase 6 fica fora (o pipeline para na Fase 5).
- Os parâmetros efetivos aparecem na página da execução e a comparação mostra
  `θ rel. / θ sim.` por execução.
- **Gráficos do artigo**: ao terminar cada execução o worker gera
  automaticamente os artefatos em `exports/lab/run-<id>/` (bind mount, visível
  no host): os 4 gráficos do artigo (score heurístico, funil de decisão,
  tickers por origem, tempo por fase) e extras (varredura de limiar, matrizes de
  confusão, distribuições e comparativo entre execuções), além de `resumo.txt`,
  `metricas.csv` e `amostra_fase4.csv`. Há um botão "Regenerar gráficos" na
  página da execução e o comando `generate_run_charts --run-id N`.
- Fases 4 e 5 podem rodar com fallback heurístico quando `usar_llm=0`
  (não exige `OPENAI_API_KEY`).
- O worker processa as execuções pendentes, retoma execuções interrompidas e
  aceita cancelamento.
- `/lab/compare/` compara F1, melhor score e melhor similaridade global entre
  execuções. Fases sem labels avaliados aparecem como `—`.
- `/lab/models/` é o catálogo de modelos: envia `.zip`/`.tar.gz` de modelos
  locais, registra IDs do Hugging Face, testa o carregamento (e grava a
  dimensão real), limpa embeddings de ativos e exclui modelos locais.

## Experimentos do TCC

- O modelo de embeddings é configurável por execução (`ExperimentRun.modelo`).
- Os embeddings de ativos ficam em `AssetEmbedding`, com namespace por modelo.
- Modelos locais em `core/intelligent_motor/models/` ou IDs do Hugging Face.
- A pasta de modelos é gravável pelo container, então o upload do `/lab/`
  instala direto em `core/intelligent_motor/models/<nome>` no host.
- Device por execução: `auto` escolhe `cuda` quando o PyTorch enxerga GPU.
- Sem GPU: `EMBEDDING_DEVICE=cpu` e imagem Docker com PyTorch CPU.
- Cache de Fase 1 e store de embeddings usam o mesmo namespace de modelo.

Variáveis principais:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DATABASE_URL` | — | Se vazia, usa SQLite (`db.sqlite3`). |
| `EMBEDDING_DEVICE` | `cpu` | `cpu`, `cuda` ou `auto` (default da interface). |
| `EMBEDDING_MODELS` | `paraphrase-multilingual-MiniLM-L12-v2` | Sugestões iniciais na UI. |
| `LAB_MODELS_DIR` | `core/intelligent_motor/models` | Pasta dos modelos locais. |
| `LAB_MODEL_UPLOAD_MAX_MB` | `4096` | Limite do upload de modelo compactado. |
| `GUNICORN_TIMEOUT` | `600` | Timeout do `web` (uploads/testes grandes). |
| `COLLECTOR_INTERVAL_SECONDS` | `300` | Intervalo da coleta contínua. |
| `WORKER_POLL_SECONDS` | `10` | Intervalo de busca por execuções pendentes. |
| `EXPERIMENT_BATCH_SIZE` | `16` | Tamanho do lote ao iterar notícias. |
| `EXPERIMENT_CACHE_ENABLED` | `0` | Habilita cache da Fase 1. |
| `OPENAI_API_KEY` | — | Opcional; sem ela, Fases 4/5 usam fallback. |
| `PIPELINE_METRICS_PATH` | `pipeline_metrics.jsonl` | JSONL de métricas do pipeline. |
| `LAB_CHARTS_DIR` | `exports/lab` | Pasta dos gráficos/artefatos por execução. |

## Dataset exportado

Cada execução do `export_dataset` cria uma pasta com:

- `noticias.jsonl` — uma notícia por linha, já com a classificação da execução
  (`--run-id`) e o label anotado, quando existir.
- `manifest.json` — filtros usados, contagens, tamanho e SHA-256 dos arquivos.
- `annotation_sample.csv` — amostra para anotação manual. Por padrão prioriza
  notícias com conteúdo; use `--sample-all` para amostrar todas.
- `--only-run` restringe a exportação (e a amostra de anotação) às notícias
  classificadas por uma execução. É o caminho recomendado para anotar e medir
  F1 de um run específico.

```bash
./venv/bin/python manage.py export_dataset \
  --output exports --name tcc-v1 \
  --run-id 3 --sample-size 300 --seed 42

# Só as notícias da execução 3, com 100% delas na amostra de anotação
./venv/bin/python manage.py export_dataset \
  --output exports --name tcc-run3-anotacao \
  --run-id 3 --only-run --sample-size 500
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
./venv/bin/python manage.py test core pipeline_lab -v 2
```

Os testes cobrem normalização/deduplicação da coleta, exportação (incluindo
`--only-run`), criação e métricas de execuções, store de embeddings, pipeline
sem LLM, catálogo/upload de modelos e a UI do `/lab/`. Nenhum teste carrega
modelo ou acessa rede.
