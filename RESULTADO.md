# Resultado - Fases 7 e 8

## Feito
- Dashboard com ranking de noticias por score, badges de prioridade/sentimento/impacto e tooltip de motivos.
- Filtros por prioridade e setor no ranking.
- Alertas recentes exibem sinais de impacto, sentimento e score do usuario.
- Testes unitarios para parser JSON (normalizacao), scoring e priorizacao.
- Testes de integracao para pipeline com motor de prioridade e thresholds.
- Logs com ids de noticia e usuario na etapa de score e alerta.

## Feito x Esperado
| Item | Esperado | Feito | Observacoes |
| --- | --- | --- | --- |
| Ranking de noticias | Lista ranqueada no dashboard | OK | Usa NoticiaScore por usuario |
| Sinais de impacto e sentimento | Exibir impacto e sentimento no feed | OK | Badges em alertas e ranking |
| Filtros prioridade/sector | Filtros no dashboard | OK | GET por prioridade e setor |
| Motivos do score | Tooltip/detalhe | OK | Tooltip "Motivos" com resumo |
| Testes unitarios | Parser JSON, scoring e priorizacao | OK | Adicionados em core/tests.py |
| Testes integracao | Pipeline completo | OK | Pipeline com motor de prioridade e thresholds |
| Logs de ids | Ids de noticia e usuario | OK | Logs no scoring e alertas |
| Metricas | Basicas | Nao implementado | Somente logs nesta entrega |
