# Monitor Financeiro

Sistema de monitoramento de notícias financeiras com classificação inteligente via IA. Coleta notícias de feeds RSS, processa por um pipeline de 6 fases (embeddings + heurísticas + LLM) e gera alertas personalizados por perfil de investidor.

## Como usar

### 1. Instale as dependências

```bash
python -m venv venv
./venv/bin/python -m pip install -r requirements.txt
```

### 2. Configure as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
OPENAI_API_KEY=sk-...          # Opcional — sem ela, as fases LLM usam fallback heurístico
DJANGO_START_MONITOR=1         # Auto-inicia o monitor ao rodar o servidor
DJANGO_START_SCHEDULER=1       # Auto-inicia o scheduler ao rodar o servidor
MONITOR_INTERVAL_SECONDS=300   # Intervalo de coleta recorrente (segundos)
```

### 3. Prepare o banco de dados

```bash
./venv/bin/python manage.py migrate
```

### 4. Crie um usuário

```bash
./venv/bin/python manage.py createsuperuser
```

### 5. Execute o servidor

```bash
./venv/bin/python manage.py runserver
```

Acesse `http://localhost:8000/` — redireciona para o dashboard (autenticado) ou login.

### 6. Coleta manual de notícias

```bash
./venv/bin/python manage.py run_monitor
```

Popula a base de ativos (JSON → S&P500 → B3 CSV) e dispara a coleta inicial dos feeds RSS.

### 7. Coleta recorrente (scheduler)

```bash
./venv/bin/python manage.py run_scheduler
```

Mantém o APScheduler em background, coletando notícias a cada `MONITOR_INTERVAL_SECONDS`.

### 8. Pipeline Lab (staff)

Acesse `/lab/` para testar o pipeline completo com notícias arbitrárias sem persistir dados.

## Pipeline Inteligente (6 fases)

```
Notícia → Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6 → Alerta
           Filtro    Match    Heuríst.  LLM Gate  Classif.  Decisor
           Global    Ticker   Scoring   (binário)  Rich      Engine
```

| Fase | O que faz |
|------|-----------|
| **1. Filtro Global** | Embeddings (sentence-transformers) contra 5 centroides temáticas; rejeita notícias irrelevantes |
| **2. Match de Tickers** | Similaridade semântica entre a notícia e os ativos da carteira do usuário |
| **3. Heurística** | Scoring por regras (menção direta, setor, palavras-chave macro, urgência, etc.) |
| **4. LLM Gate** | Decisão binária via OpenAI apenas para o "zona cinza" (score 3–6); alta/baixa bypassam a LLM |
| **5. Classificação Rich** | Sentimento, impacto, urgência, categoria — via LLM com fallback por keywords |
| **6. Decisor** | Regras configuráveis (YAML) → prioridade (CRITICAL/HIGH/MEDIUM/LOW) + canais de notificação |

O custo da LLM é controlado: Fases 4 e 5 só chamam a API quando o score cai na zona cinza.

## Modelos de dados

| Modelo | Descrição |
|--------|-----------|
| **Ativo** | Ativo financeiro (ticker, nome, fonte) |
| **Carteira** | Carteira do usuário (1:1 com User, M2M com Ativo) |
| **Noticia** | Artigo coletado (link, título, conteúdo, resumo, impacto) |
| **NoticiaClassificacao** | Classificação LLM por artigo (sentimento, impacto, urgência, categoria) |
| **NoticiaScore** | Score personalizado por usuário+notícia |
| **PerfilInvestidor** | Perfil (risco, horizonte, setores, sensibilidade, frequência) |
| **InteracaoNoticia** | Tracking de interação (abriu, ignorou, tempo de leitura) |
| **FonteRSS** | Fonte RSS (URL, nome, confiabilidade, ativa) |
| **Alerta** | Alerta gerado por usuário+notícia+ativo(s) |

## Rotas da aplicação

| URL | Descrição |
|-----|-----------|
| `/dashboard/` | Dashboard principal (métricas, gráficos, carteira, ranking, alertas) |
| `/noticias/` | Lista paginada de notícias com filtros |
| `/noticia/<id>/` | Detalhe da notícia com classificação completa |
| `/meus-alertas/` | Alertas do usuário com filtros de prioridade/ticker |
| `/register/` | Cadastro de usuário |
| `/lab/` | Pipeline Lab (staff) |
| `/admin/` | Django Admin |

## Estrutura do projeto

```
finance-web/
├── setup/                  # Configuração Django (settings, URLs, WSGI/ASGI, logging)
├── core/
│   ├── models.py           # Modelos de domínio
│   ├── views.py            # Views web
│   ├── urls.py             # Rotas do app
│   ├── forms.py            # Formulários
│   ├── signals.py          # Signals Django
│   ├── apps.py             # AppConfig (auto-start monitor/scheduler)
│   ├── startup.py          # Bootstrap em background
│   ├── intelligent_motor/  # Pipeline de 6 fases (embeddings, heurística, LLM)
│   ├── llm/                # Camada de compatibilidade (delega para intelligent_motor)
│   ├── services/           # Regra de negócio (notícias, scoring, interações, ativos)
│   ├── parsers/            # Parsing de feeds RSS
│   ├── scheduler/          # APScheduler (coleta recorrente)
│   ├── management/commands/# run_monitor, run_scheduler
│   └── migrations/         # Migrações do banco
├── pipeline_lab/           # App staff para testar o pipeline
├── templates/              # Templates HTML (Bootstrap 5 + Chart.js)
├── static/                 # CSS, JS, assets estáticos
├── scripts/                # Scripts utilitários (export, embeddings, dataset)
├── logs/                   # Logs da aplicação (criar manualmente)
├── manage.py               # CLI do Django
├── core_ativos.json        # Base de ativos pré-construída
├── IBOVDia_24-03-26.csv    # Dados B3
├── rss.txt                 # Lista de feeds RSS
└── requirements.txt        # Dependências
```

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `OPENAI_API_KEY` | — | Chave da OpenAI (sem ela, fallback heurístico) |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Modelo para Fase 4 |
| `DJANGO_START_MONITOR` | `1` | Auto-iniciar monitor no `runserver` |
| `DJANGO_START_SCHEDULER` | `1` | Auto-iniciar scheduler no `runserver` |
| `MONITOR_INTERVAL_SECONDS` | `300` | Intervalo de coleta recorrente |
| `ARTICLE_RETENTION_DAYS` | `1` | Janela temporal da coleta inicial |
| `ASSETS_JSON_PATH` | `core_ativos.json` | Caminho para base de ativos JSON |
| `B3_CSV_PATH` | `IBOVDia_24-03-26.csv` | Caminho para CSV da B3 |
| `RSS_PATH` | `rss.txt` | Caminho para lista de feeds RSS |
| `LOG_FILE_PATH` | `logs/monitor.log` | Caminho do arquivo de log |

## Scripts utilitários

```bash
# Testar parser RSS
./venv/bin/python scripts/test_rss.py

# Listar tickers registrados
./venv/bin/python scripts/listar_tickers.py

# Exportar notícias para JSON
./venv/bin/python scripts/export_notices.py

# Pré-gerar embeddings dos ativos (Fase 2)
./venv/bin/python scripts/popular_embeddings_agora.py

# Construir dataset para treino/avaliação
./venv/bin/python scripts/build_dataset.py
```

## Observações

- A LLM é opcional; sem `OPENAI_API_KEY`, o pipeline usa fallback heurístico por keywords.
- O auto-start do monitor/scheduler no `runserver` é controlado pelas env vars `DJANGO_START_MONITOR` e `DJANGO_START_SCHEDULER`. Em produção, o scheduler deve rodar em um container separado.
- Crie a pasta `logs/` manualmente antes de rodar o servidor, caso não exista.
- O logout usa `POST` com CSRF para evitar `405 Method Not Allowed`.
- Os alertas recentes abrem a notícia em nova aba.
- O perfil adaptativo do usuário é ajustado automaticamente com base nas interações (abrir/ignorar notícias).
- Métricas do pipeline são exportadas via JSONL para análise de performance.

## Pendências

### Críticas

- **Tests mocks funções que não existem** — `summarize_article`, `is_relevant`, `create_parser` em `core/tests.py` não existem em `noticia_service.py`. Os testes são de uma arquitetura anterior e vão falhar.

### Altas

- **Envio de e-mail/push não implementado** — `PerfilInvestidor` tem campos `notificacao_email`, `notificacao_push` e o Fase 6 define ações `["email", "push", "dashboard_destacado"]`, mas não existe infraestrutura de envio (sem `send_mail`, sem FCM, sem WebSocket).
- **Geração de resumo não implementada** — `Noticia` tem campos `resumo`, `resumo_status` (default `"pendente"`), templates exibem o resumo, mas nenhum backend gera. O old README mencionava integração com OpenAI para isso.
- **`CustomParser` para `.html` é stub** — `core/parsers/custom_parser.py` levanta `NotImplementedError`. A factory rota URLs `.html`/`.htm` para ele, o que vai quebrar se algum feed usar essa extensão.
- **`STATIC_ROOT` comentado** em `setup/settings.py:133` — `collectstatic` vai falhar se executado.

### Médias

- **Feature flags sem uso** — `ENABLE_STRUCTURED_CLASSIFICATION` definida mas nunca consumida. `ENABLE_PRIORITY_ENGINE` definida mas nunca verificada no código de produção.
- **`scoring_service.py` órfão** — módulo completo (148 linhas) nunca chamado em produção. O scoring real é feito pelo `fase6_decisor/score_final.py` e `noticia_service.py`.
- **Scripts com paths hardcoded errados** — `scripts/popular_embeddings_agora.py` e `scripts/listar_tickers.py` apontam para `C:/Users/matheusdossantos/finance-web` (falta `-web`).
- **Duplicação de `is_priority_at_least`** — definida tanto em `scoring_service.py:72` quanto em `noticia_service.py:35`.
- **Perfis adaptativos limitados** — `interacao_service.py` só ajusta `sensibilidade_negativo` e `setores_preferidos`. `horizonte`, `perfil_risco` e `frequencia_alertas` nunca são adaptados.

### Baixas

- **Sem REST API** — todas as views servem HTML. Sem DRF, serializers, ou padrão `/api/`.
- **Sem auth por token** — só session auth do Django. Sem JWT ou API keys para acesso programático.
- **Signals subutilizados** — só `create_investor_profile` está conectado. Falta signal para recalcular scores, gerar resumos e enviar notificações.

## Arquivos úteis

- [requirements.txt](requirements.txt)
- [REFACTORING_GUIDE.md](REFACTORING_GUIDE.md)
