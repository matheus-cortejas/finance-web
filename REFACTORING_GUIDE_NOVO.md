# Guia de Refatoração e Evolução do Projeto

## Visão Geral

Este documento define a arquitetura alvo, decisões tecnológicas e o plano de refatoração para transformar o MVP "Go Horse" em um sistema estruturado, escalável e de fácil manutenção, baseando-se no framework **Django** como fundação web. 

A escolha do Django visa acelerar as entregas do *Product Backlog*, resolvendo nativamente a gestão de usuários (Auth), persistência de dados (ORM) e interface administrativa (Admin).

## Estado Atual (Pós-MVP Go Horse)

- O projeto já possui a lógica core isolada (Parsers, Services, Integração LLM).
- Coleta funcional utilizando `feedparser` com classificação de relevância via OpenAI (com fallback heurístico).
- A base já foi migrada para Django com ORM, auth e dashboard autenticado.
- Os comandos `run_monitor` e `run_scheduler` substituem o fluxo antigo de CLI e loop manual.
- O legado em `src/` foi removido; configuração e logging agora vivem em `setup/`.
- A suíte de testes cobre models, services, scheduler, comandos e dashboard web.

## Leitura Guiada da Base Atual

Se a ideia for entender o projeto por fluxo, esta é a ordem mais útil:

1. [setup/settings.py](setup/settings.py) define o ambiente global, o banco, os caminhos padrão, as variáveis de monitoramento e o logging.
2. [core/apps.py](core/apps.py) e [core/startup.py](core/startup.py) decidem se o monitor e o scheduler sobem automaticamente quando o servidor inicia.
3. [setup/urls.py](setup/urls.py) e [core/urls.py](core/urls.py) conectam o domínio web ao dashboard e ao login do Django.
4. [core/views.py](core/views.py) cuida da experiência autenticada: cadastro, login, dashboard, busca e adição de ativos.
5. [core/models.py](core/models.py) representa o estado persistido do sistema: ativos, carteiras, notícias e alertas.
6. [core/services/](core/services/) concentra as regras reais do produto: ingestão de ativos, coleta de notícias, vínculo com carteiras e avaliação de relevância.
7. [core/parsers/](core/parsers/) define como cada feed é lido; o `RSSParser` é o padrão, e a fábrica permite trocar a origem sem mudar o serviço.
8. [core/llm/](core/llm/) encapsula a classificação de relevância, com fallback heurístico quando a OpenAI não está disponível.
9. [core/scheduler/](core/scheduler/) mantém a varredura automática dos feeds e a limpeza dos registros antigos.
10. [core/management/commands/](core/management/commands/) expõe tudo isso via terminal para uso operacional e testes.
11. [tests/](tests/) confirma que os fluxos acima continuam funcionando juntos.

### Fluxo em tempo de execução

- O servidor sobe e, se habilitado, dispara o monitor em background.
- A home redireciona para login quando o usuario nao esta autenticado e para o dashboard quando ja existe sessao.
- O monitor faz a primeira varredura, monta a base de ativos e prepara o scheduler.
- O scheduler repete a coleta a cada intervalo configurado e limpa notícias antigas diariamente.
- Quando um feed traz uma noticia relacionada a um ativo da carteira, o sistema persiste a noticia, gera o resumo, registra o alerta e abre a noticia em nova guia na dashboard.
- O usuário entra pela home, autentica e passa a usar a carteira e os alertas diretamente pela interface web.

### Papel de cada camada

- **Configuração**: [setup/settings.py](setup/settings.py) e [setup/urls.py](setup/urls.py).
- **Domínio**: [core/models.py](core/models.py) e [core/admin.py](core/admin.py).
- **Regras de negócio**: [core/services/](core/services/).
- **Entrada de dados**: [core/parsers/](core/parsers/).
- **Classificação semântica**: [core/llm/](core/llm/).
- **Automação**: [core/scheduler/](core/scheduler/).
- **Interface web**: [core/views.py](core/views.py) e `templates/`.
- **Operação**: [core/management/commands/](core/management/commands/) e [logs/monitor.log](logs/monitor.log).

### Compatibilidade e legado

- [setup/logger.py](setup/logger.py) concentra o logging compartilhado pelo monitor, scheduler e comandos.
- O banco legado `data.db` foi removido; o banco ativo é `db.sqlite3`.
- O auto-start do monitor e do scheduler no `runserver` é controlado por `DJANGO_START_MONITOR` e `DJANGO_START_SCHEDULER`.

## Arquitetura Alvo (Padrão Django)

A arquitetura manterá a separação de lógica de negócio já construída, mas o roteamento, persistência e comandos de terminal serão envelopados no padrão Django:

1. **Camada de Dados (Models)** – Utilização do Django ORM nativo, substituindo repositórios customizados.
2. **Serviços** – Contêm a regra de negócio (mantidos quase intactos, apenas atualizando as chamadas de banco para usar o ORM).
3. **Parsers e LLM Analyzer** – Módulos isolados e agnósticos importados pelos Serviços.
4. **Scheduler e CLI** – Transformados em **Django Management Commands** para garantir o contexto correto do banco de dados.
5. **Autenticação e Interface** – Uso do `django.contrib.auth` para usuários/carteiras e o Django Admin para gestão inicial do sistema.

### Tecnologias

| Componente      | Escolha               |
|-----------------|-----------------------|
| Linguagem       | Python 3.10+          |
| Framework Web   | Django                |
| Banco de dados  | SQLite (dev) / PostgreSQL (prod) via Django ORM |
| Agendamento     | APScheduler (rodando via Management Command) |
| RSS/Feeds       | feedparser            |
| Scraping (HTML) | BeautifulSoup4 + requests (fallback) |
| LLM             | OpenAI API (GPT-3.5-turbo) |
| Configuração    | python-dotenv + Django Settings |

## Nova Estrutura de Pastas

O projeto sairá do modelo genérico de pastas para a padronização de "projetos" e "aplicativos" do Django.

    projeto/
    ├── .env
    ├── .gitignore
    ├── requirements.txt
    ├── README.md
    ├── REFACTORING_GUIDE.md            # este arquivo
    │
    ├── setup/                          # Configurações globais do Django
    │   ├── __init__.py
    │   ├── settings.py                 # Integra com .env
    │   ├── urls.py
    │   └── wsgi.py / asgi.py
    │
    ├── core/                           # App principal contendo as regras de negócio
    │   ├── __init__.py
    │   ├── admin.py                    # Registro dos models para painel admin web
    │   ├── apps.py
    │   ├── models.py                   # Models ORM do domínio
    │   ├── views.py                    # Rotas do dashboard do usuário
    │   ├── urls.py                     # Rotas do app
    │   │
    │   ├── management/
    │   │   └── commands/               # Substitui a CLI e o scheduler legados
    │   │       ├── run_monitor.py      # Comando para iniciar o polling manualmente
    │   │       └── run_scheduler.py    # Comando para iniciar o APScheduler com acesso ao DB
    │   │
    │   ├── parsers/                    # Parsing de feeds RSS
    │   ├── services/                   # Regras de negócio com ORM
    │   ├── llm/                        # Análise de relevância com fallback heurístico
    │   └── scheduler/                  # Agendamento recorrente e coleta inicial
    │
    └── manage.py                       # Ponto de entrada padrão do Django


## Plano de Refatoração para o Django (Passo a Passo)

### Fase 1: Fundação Django
- Criar o projeto base e o app principal (`django-admin startproject setup .` e `python manage.py startapp core`).
- Configurar variáveis de ambiente (`.env`) no `settings.py` (API keys, caminhos, configurações de banco).
- Mover as pastas `parsers/`, `services/`, `llm/` e `utils/` para dentro da pasta `core/`.

### Fase 2: Mapeamento Objeto-Relacional (O Fim dos Repositórios)
- Eliminar a pasta antiga `database/` e suas classes de repositório.
- Criar os modelos em `core/models.py`:
  - `Ativo` (ticker e nome).
  - `Carteira` (OneToOne com `django.contrib.auth.models.User`, ManyToMany com `Ativo`).
  - `Noticia` (dados da notícia, link, data, impacto).
  - `Alerta` (relação entre Notícia, Ativo e Usuário).
- Rodar migrações (`makemigrations` e `migrate`).
- Registrar modelos no `core/admin.py` para ganhar acesso à interface web nativa de administração.

### Fase 3: Adaptação dos Serviços
- Atualizar `NoticiaService`, `UsuarioService` e outros serviços dentro de `core/services/` para que parem de chamar repositórios customizados e passem a usar o ORM, ex: `Noticia.objects.create()`.
- Garantir que a lógica de "Classificação de Impacto" e o "Filtro de Relevância" não sofram regressões e operem independentes da camada de banco.

### Fase 4: CLI e Scheduler via Management Commands
- Criar a pasta `core/management/commands/`.
- Migrar o script principal do terminal para um comando (ex: `python manage.py run_monitor`).
- Migrar a configuração do `APScheduler` para um comando persistente (`python manage.py run_scheduler`).

### Fase 5: Entrega das Histórias (Web & Experiência)
- Com a persistência sólida e nativa, criar Views em `core/views.py` para renderizar o dashboard.
- Utilizar o sistema de login nativo do Django para associar usuários às suas carteiras, sem precisar reinventar rotinas de autenticação.
- Exibir carteira, alertas e formulário de inclusão de ativos na interface web.
- Validar o fluxo com testes de integração da dashboard e do login.

## Notas para o Agente (IA) e para o Desenvolvedor

- **Use logs descritivos** – continue rastreando o comportamento do agendador e da LLM[cite: 1]. No Django, configure o `LOGGING` no `settings.py` para capturar os outputs dos *Management Commands*.
- **Mantenha os Services "Puros"** – evite a tentação de colocar regras de negócio complexas (como chamadas à API da OpenAI) dentro do método `save()` dos `models.py` do Django. O fluxo deve continuar sendo orquestrado pelos arquivos dentro de `core/services/`.
- **A LLM deve ser opcional** – caso a chave da API não esteja configurada no `.env`, o sistema deve realizar o fallback suave para o comportamento anterior (apenas filtro por menção do ticker).
- **Os parsers baseados em feedparser** continuam sendo a implementação padrão; a estrutura agnóstica dos parsers deve ser respeitada para permitir integrações com novas APIs REST no futuro.

## Status Atual da Refatoração (Concluído)

- A migração para Django foi concluída com auth, ORM, admin, management commands e dashboard autenticado.
- A lógica estática (parsers e consultas ao LLM) permanece separada e funcional.
- A refatoração preservou apenas os launchers mínimos de compatibilidade; o restante do legado em `src/` foi removido.
- Resultado validado: a suíte de testes do repositório está verde.

---
*Última atualização: 29/04/2026*