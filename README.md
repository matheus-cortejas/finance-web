Projeto: monitor de notícias por ativos com Django

Como usar:

1. Instale as dependências na `venv`:

```bash
./venv/bin/python -m pip install -r requirements.txt
```

2. Prepare o banco de dados:

```bash
./venv/bin/python manage.py migrate
```

3. Crie um usuario para login:

```bash
./venv/bin/python manage.py createsuperuser
```

4. Execute a interface web:

```bash
./venv/bin/python manage.py runserver
```

5. Inicie a coleta manual quando precisar atualizar a base e processar feeds:

```bash
./venv/bin/python manage.py run_monitor --b3-csv ~/Downloads/IBOVDia_24-03-26.csv --rss ~/Downloads/rss.txt
```

Esse comando popula a base de ativos e dispara a verificação inicial. A inclusão de ativos na watchlist agora acontece pela dashboard Django.

6. Para manter o polling recorrente em execução:

```bash
./venv/bin/python manage.py run_scheduler --rss ~/Downloads/rss.txt
```

7. Rode os testes:

```bash
./venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

## Como o projeto funciona

### Fluxo principal

1. O Django sobe com as configurações de [setup/settings.py](setup/settings.py), carrega `.env`, configura o SQLite, o logging e o startup automático do monitor.
2. Quando o servidor inicia, [core/apps.py](core/apps.py) aciona [core/startup.py](core/startup.py), que pode iniciar o monitor e o scheduler em background sem travar o `runserver`.
3. A home redireciona para login quando o usuario nao esta autenticado e para o dashboard quando ja existe sessao.
4. O comando [manage.py run_monitor](core/management/commands/run_monitor.py) executa [core/management/workflows.py](core/management/workflows.py), que popula a base de ativos e faz uma coleta inicial dos feeds.
5. O comando [manage.py run_scheduler](core/management/commands/run_scheduler.py) sobe o APScheduler e mantém a varredura recorrente em execução.
6. A coleta passa por [core/scheduler/jobs.py](core/scheduler/jobs.py), que busca a watchlist atual, chama o serviço de notícias e limpa artigos antigos.
7. O processamento das notícias fica em [core/services/noticia_service.py](core/services/noticia_service.py), que faz o parsing, filtra relevância, salva notícias, gera resumo e cria alertas.
8. A relevância é avaliada em [core/llm/openai_client.py](core/llm/openai_client.py) e [core/llm/relevance.py](core/llm/relevance.py). Se não houver chave da OpenAI, o sistema cai para a heurística por menção de ticker/nome.
9. O usuário usa [core/views.py](core/views.py) e os templates em `templates/core/` para navegar entre login e dashboard.

### Mapa da codebase

- [setup/](setup/) concentra o projeto Django: settings, URLs, WSGI e ASGI.
- [core/models.py](core/models.py) guarda o domínio persistido: ativos, carteiras, notícias e alertas.
- [core/services/](core/services/) concentra a regra de negócio e a integração com banco, RSS e LLM.
- [core/parsers/](core/parsers/) isola a leitura de feeds RSS e a eventual adaptação de outras fontes.
- [core/scheduler/](core/scheduler/) define a agenda de coleta recorrente e a limpeza automática.
- [core/management/commands/](core/management/commands/) expõe os fluxos operacionais via Django management commands.
- [core/views.py](core/views.py) e `templates/` implementam a experiência web autenticada e o dashboard.
- [tests/](tests/) cobre models, serviços, scheduler, comandos e telas web.
- [setup/logger.py](setup/logger.py) concentra o logging compartilhado pela aplicação.

### O que aparece nos logs

- Inicialização do monitor, carregamento do CSV B3 e da base S&P 500.
- Execução da coleta inicial e das coletas recorrentes do scheduler.
- Cada feed RSS visitado, cada notícia filtrada e cada alerta persistido.
- Ações de login, cadastro, busca de ativo e renderização do dashboard.

Os logs principais vão para o console e para [logs/monitor.log](logs/monitor.log).

Estrutura atual:
- `setup/`: configuração global do Django, rotas e settings.
- `core/models.py`: models ORM para ativos, carteira, notícias e alertas.
- `core/services/`: regras de negócio com acesso via ORM.
- `core/parsers/`, `core/llm/` e `core/scheduler/`: parsing de feeds, análise de relevância e agendamento.
- `core/management/commands/`: comandos `run_monitor` e `run_scheduler`.
- `core/views.py`: dashboard autenticado do usuário.
- `templates/`: base visual, login e dashboard.
- [setup/logger.py](setup/logger.py): configuração central de logging.
- `tests/`: suíte de regressão do projeto.

Observações:
- A LLM é opcional; sem `OPENAI_API_KEY`, o filtro cai para a heurística por menção.
- Resumos são gerados automaticamente quando há alertas; sem OpenAI, o resumo usa fallback local.
- O conteúdo enviado à LLM é truncado (configure `ARTICLE_DESCRIPTION_MAX_CHARS` e `ARTICLE_CONTENT_MAX_CHARS`).
- Links de notícias são normalizados para remover parâmetros de tracking comuns.
- O RSS continua sendo o parser padrão e a análise segue isolada nos serviços.
- O diretório `src/` foi removido; a configuração e o logging vivem em `setup/`.
- Para ajustar o caminho do arquivo de log, use `LOG_FILE_PATH`.
- O auto-start do monitor e do scheduler no `runserver` é controlado por `DJANGO_START_MONITOR` e `DJANGO_START_SCHEDULER`.
- O logout do dashboard usa `POST` com CSRF para evitar `405 Method Not Allowed`.
- Os alertas recentes abrem a notícia em uma nova guia.

Arquivos úteis:
- [REFACTORING_GUIDE.md](REFACTORING_GUIDE.md)
- [requirements.txt](requirements.txt)
# teste-api