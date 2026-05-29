# Plano de Implementacao - Evolucao do Sistema Inteligente de Monitoramento Financeiro

## Objetivo
Transformar o produto atual em um sistema inteligente de apoio a decisao, adicionando classificacao estruturada, relevancia hibrida, priorizacao automatica e personalizacao por perfil de investidor, sem quebrar o fluxo atual de coleta, dashboard e alertas.

## Escopo e premissas
- Manter a base Django atual e evoluir o dominio sem reescrever o pipeline inteiro.
- Preservar fallback heuristico quando LLM estiver indisponivel.
- Entregas incrementais, com feature flags e migrações reversiveis.

## Mapa do baseline (referencia rapida)
- Servico de ingestao e regras atuais: core/services/noticia_service.py
- Classificacao binaria LLM: core/llm/openai_client.py e core/llm/relevance.py
- Dominio persistido: core/models.py
- Scheduler e workflows: core/scheduler/ e core/management/
- Dashboard: core/views.py e templates/core/dashboard.html

## Fase 0 - Diagnostico e alinhamento tecnico
**Objetivo:** reduzir risco antes de mudar o core.

Entregas:
- Checklist do fluxo atual (coleta, relevancia, resumo, alerta, dashboard).
- Mapa de dependencias e pontos de extensao.
- Definicao de JSON schema da classificacao LLM e dos pesos do motor de relevancia.

Tarefas:
- Documentar fluxo atual (1 pagina) e pontos de extensao.
- Definir esquema de classificacao (campos obrigatorios, tipos e ranges).
- Definir pesos padrao e regras de priorizacao (nivel Critica/Alta/Media/Baixa).

## Fase 1 - Modelo de dados e migrações
**Objetivo:** preparar o banco para armazenar classificacao, perfil e interacoes.

Entregas:
- Novos models e migrations aplicadas.
- Indices e constraints para consultas rapidas.

Tarefas sugeridas:
- Adicionar modelo PerfilInvestidor (1:1 com User): perfil_risco, horizonte, setores_preferidos, sensibilidade_negativo, frequencia_alertas.
- Adicionar modelo NoticiaClassificacao (1:1 com Noticia): sentimento, impacto, urgencia, setor, tipo_evento, tickers_relacionados (JSON), relevancia_llm, provider, status.
- Adicionar modelo NoticiaScore (1:1 com Noticia + User): score_final, prioridade, motivos (JSON), calculado_em.
- Adicionar modelo InteracaoNoticia (User + Noticia): abriu, ignorou, tempo_leitura, origem.
- Adicionar modelo FonteRSS (opcional): url, nome, confiabilidade, ativo.
- Incluir indices em Noticia (publicado_em, impacto) e NoticiaScore (prioridade, score_final).
- Criar migrations e atualizar admin para novas entidades.

## Fase 2 - Classificacao estruturada via LLM
**Objetivo:** substituir resposta binaria por saida JSON validada e persistida.

Entregas:
- Prompt com schema fixo.
- Parser e validacao robusta (fallback local).

Tarefas:
- Criar funcao classify_article(...) em core/llm/ para retornar JSON estruturado.
- Validar saida com schema (campos obrigatorios e valores permitidos).
- Persistir em NoticiaClassificacao com status (ok, fallback, error).
- Manter fallback heuristico quando nao houver OpenAI.

## Fase 3 - Motor de relevancia hibrido
**Objetivo:** transformar classificacao em score para ranking.

Entregas:
- Servico de scoring com pesos configuraveis.
- Persistencia de score e prioridade por usuario.

Tarefas:
- Implementar calculate_relevance_score(classificacao, perfil, carteira, fonte).
- Converter score para prioridade (Critica/Alta/Media/Baixa).
- Persistir resultado em NoticiaScore.
- Salvar motivos do score (JSON) para auditoria.

## Fase 4 - Pipeline e refatoracoes do fluxo
**Objetivo:** encaixar a classificacao no pipeline sem regressao.

Entregas:
- Pipeline atualizado com novos passos.
- Feature flag para ativar/desativar scoring.

Tarefas:
- Atualizar core/services/noticia_service.py para:
  - salvar Noticia
  - executar classificacao estruturada
  - calcular score e prioridade por usuario
  - criar alerta quando prioridade >= configurado
- Separar responsabilidades em servicos menores (ingestao, classificacao, scoring, alerta).
- Adicionar logs estruturados (info/warn) para diagnostico.

## Fase 5 - Perfil do usuario e configuracoes
**Objetivo:** permitir personalizacao real do sistema.

Entregas:
- UI simples para editar perfil.
- Defaults automáticos ao criar usuario.

Tarefas:
- Criar formulario de PerfilInvestidor no dashboard.
- Adicionar preferencias de alerta (frequencia, thresholds).
- Ajustar score para respeitar perfil (ex: conservador prioriza negativo).

## Fase 6 - Memoria e aprendizado leve
**Objetivo:** ajustar relevancia com base em interacoes.

Entregas:
- Registro de interacoes basicas.
- Ajuste heuristico dos pesos do usuario.

Tarefas:
- Registrar abertura e ignorado de alertas (endpoint simples ou tracking no dashboard).
- Atualizar pesos do usuario a partir de estatisticas simples.
- Expor um resumo de preferencia ajustada no admin.

## Fase 7 - Dashboard inteligente
**Objetivo:** mostrar priorizacao, sentimento e contexto.

Entregas:
- Lista de noticias ranqueadas.
- Sinais de impacto e sentimento no feed.

Tarefas:
- Atualizar templates/core/dashboard.html para exibir prioridade, impacto e sentimento.
- Adicionar filtros por prioridade/sector.
- Exibir motivos de score (tooltip ou detalhe).

## Fase 8 - Observabilidade e testes
**Objetivo:** reduzir risco de regressao e melhorar confiabilidade.

Entregas:
- Suite de testes atualizada.
- Logs e metricas basicas.

Tarefas:
- Testes unitarios para parser JSON, scoring e priorizacao.
- Testes de integracao para pipeline completo.
- Logs com ids de noticia e usuario.

## Refatoracoes planejadas (alvos principais)
- core/models.py: adicionar modelos e campos novos.
- core/llm/openai_client.py: novo endpoint de classificacao JSON.
- core/llm/relevance.py: renomear ou encapsular para suportar classificacao.
- core/services/noticia_service.py: orquestracao do pipeline e armazenamento.
- core/views.py e templates/core/dashboard.html: UI de perfil e ranking.
- core/scheduler/jobs.py: controlar criterios de corte e prioridade.

## Feature flags e rollout
- Habilitar classificacao estruturada via setting (ex: ENABLE_STRUCTURED_CLASSIFICATION).
- Habilitar scoring por usuario via setting (ex: ENABLE_PRIORITY_ENGINE).
- Manter fallback heuristico ativo por default ate estabilizar.

## Definicao de pronto (DoD)
- Pipeline executa fim a fim sem regressao do fluxo atual.
- Classificacao estruturada salva e auditavel.
- Ranking e prioridade aparecem no dashboard.
- Alertas respeitam perfil do usuario.
- Testes chave passam e logs mostram score/motivos.

## Riscos e mitigacoes
- Saida LLM inconsistente: validar schema e aplicar fallback.
- Latencia de classificacao: processar em batch ou async quando necessario.
- Sobre-notificacao: thresholds por usuario e prioridade minima.

## Proximos passos sugeridos
1. Aprovar schema JSON e modelos propostos.
2. Implementar Fase 1 e Fase 2 com migrations.
3. Ajustar pipeline e colocar feature flags.
4. Atualizar dashboard e testes.
