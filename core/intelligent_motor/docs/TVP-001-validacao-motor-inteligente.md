# TVP-001 — Plano de Validação e Homologação do Motor Inteligente de Notícias

**Status:** Draft
**Versão:** 1.0
**Relacionado a:**

* ADR-001 — Motor Inteligente de Classificação e Priorização de Notícias
* RFC-001 — Fase 1: Filtro Global de Relevância Financeira
* RFC-002 a RFC-006 — Demais fases do pipeline

**Última atualização:** 2026-06-01

---

# 1. Objetivo

Este documento define a estratégia oficial de validação do Motor Inteligente de Notícias.

O objetivo é garantir que cada fase do pipeline:

* Execute sem erros.
* Produza resultados consistentes.
* Permita calibração controlada.
* Atenda aos requisitos definidos nos RFCs.
* Esteja apta para integração em produção.

---

# 2. Escopo

O plano cobre:

| Fase   | Componente                 |
| ------ | -------------------------- |
| Fase 1 | Filtro Financeiro Global   |
| Fase 2 | Relacionamento com Ativos  |
| Fase 3 | Heurística Contextual      |
| Fase 4 | Relevância Binária via LLM |
| Fase 5 | Classificação Rica         |
| Fase 6 | Motor de Alertas           |

---

# 3. Critério Geral de Aceitação

## Importante

O sistema não precisa reproduzir exatamente um gabarito manual.

Por utilizar:

* Embeddings;
* Similaridade semântica;
* Heurísticas;
* Modelos de linguagem;

é esperado que existam divergências pontuais.

O foco da validação é:

### Funcionalidade

* O código executa corretamente.
* Não existem erros críticos.
* O pipeline conclui o processamento.

### Consistência

Notícias claramente financeiras devem receber scores maiores que notícias não financeiras.

### Calibrabilidade

Thresholds e pesos podem ser ajustados para aproximar o comportamento desejado.

---

# 4. Ambiente de Testes

## Dependências

```bash
pip install sentence-transformers
pip install openai
pip install google-generativeai
pip install redis
pip install pyyaml
```

---

## Serviços Recomendados

| Serviço    | Obrigatório    |
| ---------- | -------------- |
| Redis      | Não            |
| SQLite     | Sim (fallback) |
| OpenAI API | Fase 4 e 5     |
| Gemini API | Opcional       |

---

## Configuração

Cada fase deve possuir:

```text
config.yaml
```

com parâmetros independentes.

---

# 5. Estratégia de Validação

Cada fase será validada individualmente antes da integração completa.

Fluxo:

```text
Validação Unitária
        ↓
Validação de Integração
        ↓
Calibração
        ↓
Homologação
        ↓
Integração Completa
```

---

# 6. Validação da Fase 1

## Objetivo

Validar a capacidade de identificar relevância financeira global.

---

## Entrada

Arquivo:

```text
noticias_teste_fase1.json
```

---

## Métricas

### Taxa de Aceitação

```text
aceitas / total
```

### Taxa de Descarte

```text
descartadas / total
```

### Distribuição dos Scores

Analisar:

```text
mínimo
máximo
média
mediana
```

---

## Casos Esperados

| Tipo            | Resultado Esperado |
| --------------- | ------------------ |
| Petrobras       | > threshold        |
| Selic           | > threshold        |
| Dividendos      | > threshold        |
| Receita de bolo | < threshold        |
| Futebol         | < threshold        |

---

## Aprovação

A fase será aprovada quando:

* Não houver erros.
* Os scores apresentarem coerência semântica.
* O threshold puder ser ajustado sem alterações de código.

---

# 7. Validação da Fase 2

## Objetivo

Validar a associação semântica entre notícias e ativos.

---

## Entrada

Carteira exemplo:

```json
[
  "PETR4",
  "VALE3",
  "ITUB4",
  "PRIO3",
  "BBAS3"
]
```

---

## Casos Esperados

| Notícia                    | Resultado |
| -------------------------- | --------- |
| Petrobras aumenta produção | PETR4     |
| Vale expande mineração     | VALE3     |
| Banco Central altera juros | opcional  |
| Inflação sobe              | opcional  |
| Receita de bolo            | vazio     |

---

## Métrica Principal

```text
Precision@Ticker
```

---

## Aprovação

Ticker claramente relacionado deve ser identificado.

---

# 8. Validação da Fase 3

## Objetivo

Validar a aplicação correta das regras heurísticas.

---

## Métricas

### Score Médio

### Distribuição dos Critérios

Contabilizar ativações por regra:

```text
ticker_explicito
fonte_confiavel
macroeconomia
urgencia
negatividade
```

---

## Casos Esperados

### Forte impacto

```text
PETR4 despenca após investigação de fraude
```

Resultado:

```text
score > 10
```

---

### Sem relevância

```text
Cachorro salva família de incêndio
```

Resultado:

```text
score < 3
```

---

# 9. Validação da Fase 4

## Objetivo

Garantir que o LLM barato seja utilizado apenas nos casos de incerteza.

---

## Critérios

| Score | Comportamento Esperado |
| ----- | ---------------------- |
| ≤ 2   | Rejeição direta        |
| 3–6   | Chamada LLM            |
| ≥ 7   | Aprovação direta       |

---

## Métricas

### Chamadas ao LLM

```text
llm_calls / total_noticias
```

---

### Economia de Inferência

```text
1 - (llm_calls / total)
```

---

## Aprovação

A LLM deve ser acionada somente para a faixa intermediária.

---

# 10. Validação da Fase 5

## Objetivo

Validar a classificação rica.

---

## Campos Obrigatórios

```json
{
  "sentimento": "",
  "impacto": "",
  "urgencia": 0,
  "categoria": ""
}
```

---

## Validações

### Sentimento

Valores permitidos:

* positivo
* neutro
* negativo

### Impacto

* baixo
* médio
* alto

### Urgência

```text
0–10
```

### Categoria

Categorias registradas no ADR.

---

## Aprovação

100% das respostas devem produzir JSON válido.

---

# 11. Validação da Fase 6

## Objetivo

Validar a decisão operacional.

---

## Regras

### Crítica

```text
impacto = alto
AND
sentimento = negativo
```

---

### Alta

```text
impacto = alto
OR
urgencia >= 8
```

---

### Média

```text
score_heuristico >= 10
OR
relevancia_global >= 0.85
```

---

### Baixa

Demais casos.

---

## Aprovação

A regra mais restritiva deve prevalecer.

---

# 12. Teste End-to-End

## Objetivo

Validar o pipeline completo.

---

## Fluxo

```text
Notícia
   ↓
Fase 1
   ↓
Fase 2
   ↓
Fase 3
   ↓
Fase 4
   ↓
Fase 5
   ↓
Fase 6
   ↓
JSON Final
```

---

## Dataset Recomendado

| Tipo            | Quantidade |
| --------------- | ---------- |
| Financeiras     | 50         |
| Macroeconômicas | 20         |
| Corporativas    | 20         |
| Não financeiras | 50         |

Total:

```text
140 notícias
```

---

# 13. Métricas de Homologação

## Operacionais

### Latência

```text
Tempo médio por notícia
Tempo P95
Tempo P99
```

### Cache

```text
Hit Rate
Miss Rate
```

### Consumo

```text
Chamadas LLM Barata
Chamadas LLM Forte
```

---

## Qualidade

### Precision

```text
noticias_relevantes_detectadas
/
noticias_detectadas
```

### Recall

```text
noticias_relevantes_detectadas
/
noticias_relevantes_existentes
```

### F1 Score

Calculado após rotulação manual.

---

# 14. Processo de Calibração

## Thresholds Ajustáveis

### Fase 1

```yaml
threshold_relevancia
```

---

### Fase 2

```yaml
threshold_similaridade
```

---

### Fase 4

```yaml
limite_rejeicao
limite_aprovacao
```

---

### Fase 6

```yaml
pesos_score_final
regras_prioridade
```

---

## Estratégia

1. Executar dataset rotulado.
2. Comparar com gabarito manual.
3. Ajustar thresholds.
4. Reexecutar.
5. Registrar métricas.
6. Repetir até estabilização.

---

# 15. Critério de Go-Live

O sistema será considerado apto para produção quando:

* [ ] Todas as fases passarem nos testes unitários.
* [ ] Todos os contratos JSON forem respeitados.
* [ ] Nenhuma fase gerar exceções críticas.
* [ ] Cobertura mínima ≥ 80%.
* [ ] Precision e Recall aceitáveis para o negócio.
* [ ] Latência dentro dos limites operacionais.
* [ ] Integração end-to-end validada.
* [ ] Aprovação formal da equipe de produto.

---

# 16. Artefatos Gerados

Durante a homologação devem ser produzidos:

```text
resultados_fase1.json
resultados_fase2.json
resultados_fase3.json
resultados_fase4.json
resultados_fase5.json
resultados_fase6.json

metricas_validacao.csv

relatorio_homologacao.md
```

Esses artefatos constituem a evidência oficial de validação do Motor Inteligente antes da entrada em produção.
