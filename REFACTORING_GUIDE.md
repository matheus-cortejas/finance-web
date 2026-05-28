# Guia de Refatoração e Evolução do Projeto

## Visão Geral

Este documento define a arquitetura alvo, decisões tecnológicas e o plano de refatoração para transformar o MVP "Go Horse" em um sistema estruturado, escalável e de fácil manutenção.

## Estado Atual (MVP Go Horse)

- Coleta de notícias por polling a cada 5 minutos, utilizando RSS feeds.
- Planilhas CSV com lista de ações da B3 e S&P500.
- Persistência de notícias por 1 dia.
- Usuário informa ativos manualmente (códigos separados por vírgula).
- Lógica concentrada em um ou poucos scripts.
- Já utiliza a biblioteca `feedparser` para consumir feeds RSS.

## Arquitetura Alvo

Camadas bem definidas:

1. **Repositórios** – abstraem acesso ao banco de dados.
2. **Serviços** – contêm a lógica de negócio.
3. **Parsers** – extraem notícias de feeds RSS (via feedparser) ou, excepcionalmente, de HTML.
4. **LLM Analyzer** – classifica relevância das notícias.
5. **Scheduler** – gerencia execução periódica de tarefas.
6. **CLI / Interface** – interação com o usuário.

### Tecnologias

| Componente      | Escolha               |
|-----------------|-----------------------|
| Linguagem       | Python 3.10+          |
| Banco de dados  | PostgreSQL (ou SQLite para desenvolvimento) |
| Agendamento     | APScheduler           |
| RSS/Feeds       | feedparser            |
| Scraping (HTML) | BeautifulSoup4 + requests (apenas fallback) |
| LLM             | OpenAI API (GPT-3.5-turbo) |
| Configuração    | python-dotenv         |
| Logs            | logging padrão        |
| Testes          | pytest                |

## Estrutura de Pastas
projeto/
├── .env
├── .gitignore
├── pyproject.toml (ou requirements.txt)
├── README.md
├── REFACTORING_GUIDE.md # este arquivo
│
├── data/ # arquivos estáticos (CSVs)
│ ├── b3_acoes.csv
│ └── rss.txt
│
├── setup/ # configurações globais do Django
│ ├── init.py
│ ├── settings.py # carrega .env e paths
│ └── logger.py # setup de logs
│
├── core/ # código fonte do app
│ ├── init.py
│ │
│ ├── models.py # ORM do domínio
│ ├── views.py # dashboard e autenticação
│ └── services/ # regras de negócio
│ │
│ ├── database/ # acesso a dados
│ │ ├── connection.py # gerenciador de conexão
│ │ ├── repository.py # base abstrata
│ │ ├── noticia_repo.py
│ │ ├── acao_repo.py
│ │ └── usuario_repo.py
│ │
│ ├── parsers/ # extração de notícias
│ │ ├── init.py
│ │ ├── base_parser.py # ABC com método fetch()
│ │ ├── rss_parser.py # parser genérico para RSS (usa feedparser)
│ │ ├── custom_parser.py # para sites sem RSS (herda de BaseParser)
│ │ └── factory.py # retorna parser adequado por URL
│ │
│ ├── services/ # lógica de negócio
│ │ ├── init.py
│ │ ├── acao_service.py # carrega planilhas, valida códigos
│ │ ├── noticia_service.py # coleta, análise, persistência
│ │ ├── usuario_service.py # gestão de ativos do usuário
│ │ └── llm_service.py # integração com LLM
│ │
│ ├── llm/ # camada de decisão com IA
│ │ ├── init.py
│ │ ├── openai_client.py
│ │ └── relevance.py # função is_relevant(title)
│ │
│ ├── scheduler/ # tarefas agendadas
│ │ ├── init.py
│ │ └── jobs.py # definição dos jobs
│ │
│ ├── cli/ # interface por linha de comando
│ │ ├── init.py
│ │ └── main.py # ponto de entrada para o usuário
│ │
│ └── utils/ # helpers
│ ├── file_utils.py # leitura de CSV
│ ├── date_utils.py
│ └── text_utils.py # normalização, tokenização
│
├── tests/ # testes
│ ├── unit/
│ ├── integration/
│ └── conftest.py
│
└── scripts/ # utilitários avulsos
└── update_acoes.py # script para baixar lista atualizada de ações


## Fluxo de Dados com LLM

1. **Coleta** – `NoticiaService` invoca parsers (principalmente `RSSParser` para cada feed configurado) para obter notícias recentes.
2. **Filtro de menção** – verifica se o título ou conteúdo menciona ativos que o usuário possui.
3. **Análise de relevância** – para cada notícia que passou no filtro, chama `llm_service.is_relevant(title)`.
4. **Persistência** – apenas notícias consideradas relevantes são salvas no banco.
5. **Notificação** – quando o usuário consulta, as notícias relevantes são exibidas.

## Plano de Refatoração (Passo a Passo)

### Fase 1: Estrutura de Pastas e Configurações
- Criar as pastas conforme estrutura acima.
- Mover os arquivos existentes para dentro de `core/` e `setup/` (sem alterar funcionalidade).
- Adicionar `setup/settings.py` e `.env` para variáveis (API keys, intervalos, caminhos).

### Fase 2: Isolar Acesso a Dados (Repositórios)
- Definir modelos (dataclasses) para `Noticia`, `Acao`, `Usuario`.
- Criar repositórios com métodos CRUD básicos.
- Substituir chamadas diretas ao banco pelos repositórios.

### Fase 3: Extrair Parsers
- Criar classe abstrata `BaseParser` com método `fetch()`.
- Implementar `RSSParser` que recebe uma URL de feed e utiliza `feedparser` para extrair os dados.
- Para sites sem RSS, criar classes específicas que herdam de `BaseParser` e utilizam BeautifulSoup.
- Usar `factory.py` para instanciar o parser correto conforme a URL configurada.

### Fase 4: Criar Serviços
- Mover lógica de negócio para `AcaoService`, `NoticiaService`, `UsuarioService`.
- `NoticiaService` deve orquestrar: obter notícias dos parsers, filtrar por menção, chamar LLM, salvar via repositório.

### Fase 5: Integrar LLM
- Adicionar `openai_client.py` com configuração via `.env`.
- Implementar `relevance.py` com cache (dicionário em memória) e fallback.
- Injetar LLM no `NoticiaService`.

### Fase 6: Agendador
- Substituir loop manual por `APScheduler`.
- Definir jobs em `scheduler/jobs.py`: coleta de notícias, limpeza de registros antigos, etc.
- Iniciar scheduler no ponto de entrada.

### Fase 7: CLI e Experiência do Usuário
- Refatorar `cli/main.py` para receber ativos do usuário e interagir com os serviços.
- Implementar comando para listar notícias relevantes recentes.

### Fase 8: Testes e Documentação
- Escrever testes unitários para serviços e repositórios.
- Testes de integração para parsers (com mock das respostas RSS).
- Atualizar `README.md` com instruções de instalação e uso.

---

## Notas para o Agente (IA) e para o Desenvolvedor

- **Use logs descritivos** – para rastrear o comportamento do agendador e da LLM.
- **Não quebre o fluxo atual** – até que a refatoração esteja completa, o sistema deve continuar funcionando como antes.
- **A LLM deve ser opcional** – caso a chave da API não esteja configurada, o sistema deve cair no comportamento anterior (apenas filtro por menção).
- **Os parsers baseados em feedparser** devem ser a implementação padrão; mantenha a possibilidade de parsers customizados como fallback.

## Status Atual da Refatoração

- A configuração e o logging agora vivem em `setup/`, sem dependência de `src/`.
- O launcher legado `monitor.py` foi removido; o fluxo atual sai por `manage.py`.
- Os módulos antigos em `src/monitoring` e o CLI compatível em `src/cli` foram removidos.
- O scheduler já está integrado ao fluxo real com APScheduler, e a limpeza de artigos antigos roda em job separado.
- Há testes automatizados com `unittest` cobrindo repositórios, serviços, parser RSS e jobs do scheduler.
- O `venv` foi validado com as dependências instaladas e a suíte passa no ambiente atual.
- Artefatos gerados como `__pycache__` foram removidos do workspace.
- Próximas etapas naturais: expandir cobertura para CLI e cenários de integração mais próximos do uso real.

## Como Executar Agora

```bash
./venv/bin/python -m pip install -r requirements.txt
./venv/bin/python manage.py run_monitor --b3-csv ~/Downloads/IBOVDia_24-03-26.csv --rss ~/Downloads/rss.txt
./venv/bin/python manage.py run_scheduler --rss ~/Downloads/rss.txt
./venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

---

*Última atualização: 27/03/2026*