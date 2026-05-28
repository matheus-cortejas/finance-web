Projeto: monitor de notícias por ativos

Como usar:

1. Instale as dependências na `venv`:

```bash
./venv/bin/python -m pip install -r requirements.txt
```

2. Execute a aplicação:

```bash
./venv/bin/python monitor.py --b3-csv ~/Downloads/IBOVDia_24-03-26.csv --rss ~/Downloads/rss.txt
```

3. Rode os testes:

```bash
./venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Fluxo:
- Ao iniciar, informe códigos ou nomes (separados por vírgula). O sistema valida se existem na base (S&P500 e B3 CSV).
- Faz verificação inicial por notícias até 1 dia atrás.
- Depois sobe um scheduler que verifica feeds a cada 5 minutos; quando encontrar notícia que cita um ativo da carteira, gera log no terminal.
- Os logs completos também são gravados em `logs/monitor.log`.

Estrutura atual:
- `src/config`: configurações e logging.
- `src/database`: conexão SQLite e repositórios.
- `src/parsers`: parsers de RSS e fábrica.
- `src/services`: regras de negócio para ativos, notícias e LLM.
- `src/llm`: integração com OpenAI e cache de relevância.
- `src/cli`: ponto de entrada da aplicação.

Observações:
- A LLM é opcional; sem `OPENAI_API_KEY`, o filtro cai para a heurística por menção.
- O RSS continua sendo o parser padrão.
- O ponto de entrada compatível continua em `monitor.py`.
- Os módulos antigos em `src/monitoring` seguem como camada de compatibilidade para manter imports legados funcionando.
- Os artefatos gerados de compilação foram removidos e continuam fora do controle do projeto.
- O monitor agora usa APScheduler para o polling recorrente e para a limpeza automática de registros antigos.
- Para ajustar o caminho do arquivo de log, use `LOG_FILE_PATH`.

Arquivos úteis:
- [REFACTORING_GUIDE.md](REFACTORING_GUIDE.md)
- [requirements.txt](requirements.txt)
- [monitor.py](monitor.py)
# teste-api