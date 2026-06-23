# IR-006 — Implementação: Fase 6 — Decisor de Alertas, Priorização e Ações

## 1. Arquivos Criados

* `core/intelligent_motor/fase6_decisor/__init__.py`
* `core/intelligent_motor/fase6_decisor/config.yaml`
* `core/intelligent_motor/fase6_decisor/perfis.py`
* `core/intelligent_motor/fase6_decisor/motor_regras.py`
* `core/intelligent_motor/fase6_decisor/score_final.py`
* `core/intelligent_motor/fase6_decisor/explicacao.py`
* `core/intelligent_motor/fase6_decisor/pipeline.py`
* `core/intelligent_motor/fase6_decisor/exceptions.py`
* `core/intelligent_motor/fase6_decisor/tests/test_motor_regras.py`
* `core/intelligent_motor/fase6_decisor/tests/test_score_final.py`
* `core/intelligent_motor/fase6_decisor/tests/test_perfis.py`
* `core/intelligent_motor/fase6_decisor/tests/test_pipeline.py`

## 2. Arquivos Modificados

Nenhum arquivo existente precisou ser alterado para disponibilizar a Fase 6.

## 3. Resumo

Implementação da camada final de decisão do Motor Inteligente, responsável por transformar os metadados produzidos pelas fases anteriores em uma decisão operacional contendo prioridade, ações sugeridas, score final e explicação interpretável.

A implementação inclui:

* carregamento de perfil do usuário;
* avaliação de regras configuráveis;
* cálculo de score final;
* filtragem por categorias e canais;
* geração de explicação;
* pipeline de orquestração completo;
* testes unitários básicos.

## 4. Regras Implementadas

### impacto_negativo_alto

```text
impacto = alto
sentimento = negativo
```

Resultado:

```text
prioridade = critica
acoes = email, push, dashboard_destacado
```

---

### impacto_alto_ou_urgencia

```text
impacto = alto
OU
urgencia >= 8
```

Resultado:

```text
prioridade = alta
acoes = push, dashboard
```

---

### score_heuristico_ou_relevancia

```text
score_heuristico >= threshold
OU
relevancia_global >= threshold
```

Resultado:

```text
prioridade = media
acoes = dashboard
```

---

### default

Resultado:

```text
prioridade = baixa
acoes = historico
```

## 5. Decisões Técnicas

* Fase implementada como biblioteca Python local.
* Sem dependências externas além de YAML.
* Sem APIs HTTP.
* Sem filas.
* Sem persistência própria.
* Motor de regras configurável via arquivo YAML.
* Suporte a condições simples, intervalos, operadores `e` e `ou`.
* Aplicação de filtros por categoria e canal através de perfil de usuário.
* Score final normalizado para a faixa `0.0` a `1.0`.
* Explicação baseada na regra disparada.

## 6. Desvios do RFC

Foi adicionado um mapeamento interno de canais para permitir a compatibilização entre ações lógicas e canais efetivamente habilitados pelo perfil do usuário.

Nenhum desvio estrutural relevante foi identificado.

## 7. Validação Executada

Validados os seguintes cenários:

* regra crítica;
* regra alta;
* regra média;
* regra default;
* filtros por categoria;
* filtros por canal;
* score mínimo;
* score intermediário;
* score máximo;
* preservação dos metadados produzidos pelas fases anteriores.

## 8. Limitações Conhecidas

* Não há personalização avançada de thresholds por usuário.
* Não há persistência de perfis.
* Explicações são determinísticas.
* Distribuições estatísticas ainda não foram medidas em ambiente de homologação.

## 9. Métricas

Ainda não coletadas.

Medições previstas:

* distribuição de prioridades;
* distribuição de ações;
* score final médio;
* tempo médio de execução.

## 10. Pendências

* Executar homologação com notícias classificadas pela Fase 5.
* Medir métricas reais de distribuição.
* Integrar a Fase 6 ao pipeline principal de execução.

## 11. Conformidade com o IP-006

Itens implementados:

* [x] Configuração
* [x] Perfil do Usuário
* [x] Motor de Regras
* [x] Score Final
* [x] Explicação
* [x] Pipeline
* [x] Logging
* [x] Testes Básicos

## 12. Próximos Passos

* Encadear a Fase 6 ao pipeline principal.
* Validar comportamento em lote.
* Ajustar thresholds com dados reais.
* Iniciar planejamento da Fase 7.
