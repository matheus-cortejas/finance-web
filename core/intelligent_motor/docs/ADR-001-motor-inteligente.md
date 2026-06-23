# ADR-001 — Motor Inteligente de Classificação e Priorização de Notícias Financeiras

**Status:** Proposto
**Data:** 2026-06-01
**Autores:** Equipe de Arquitetura
**Decisores:** Time de Produto e Engenharia

---

# 1. Contexto

O sistema atual de processamento de notícias utiliza regras simples para identificar eventos relevantes para investidores.

Com o aumento do volume de notícias e a necessidade de personalização por carteira, tornou-se necessário desenvolver um mecanismo capaz de:

* Filtrar ruído de conteúdo não financeiro;
* Relacionar notícias a ativos específicos;
* Priorizar notícias por impacto potencial;
* Reduzir custos de inferência com LLMs;
* Produzir metadados estruturados para alertas e dashboards.

A solução deve ser escalável, interpretável e economicamente viável para processamento contínuo de notícias.

---

# 2. Problema

Determinar automaticamente:

1. Se uma notícia possui relevância financeira;
2. Quais ativos da carteira podem ser impactados;
3. O nível de impacto e urgência da notícia;
4. Qual ação deve ser tomada pelo sistema de alertas.

O processo deve minimizar chamadas a modelos de linguagem mais caros e manter explicabilidade suficiente para auditoria e ajuste operacional.

---

# 3. Decisão Arquitetural

Será implementado um pipeline híbrido composto por:

* Embeddings semânticos;
* Heurísticas interpretáveis;
* Modelos LLM de múltiplos níveis;
* Motor de decisão de alertas.

A arquitetura segue uma estratégia de funil, onde etapas mais baratas eliminam grande parte do volume antes da utilização de modelos mais custosos.

---

# 4. Arquitetura Proposta

```text
Notícia
   │
   ▼
[Fase 1]
Filtro Financeiro Global
   │
   ▼
[Fase 2]
Relacionamento com Ativos
   │
   ▼
[Fase 3]
Score Heurístico
   │
   ▼
[Fase 4]
LLM de Baixo Custo (Condicional)
   │
   ▼
[Fase 5]
LLM de Classificação Rica
   │
   ▼
[Fase 6]
Motor de Priorização e Alertas
   │
   ▼
JSON Estruturado
```

---

# 5. Componentes

## 5.1 Fase 1 — Filtro Financeiro Global

### Objetivo

Eliminar notícias sem relevância financeira.

### Implementação

Modelo:

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Referência semântica:

```text
Análise financeira, impacto econômico, resultados de empresas,
mercados, commodities, juros, câmbio, regulação,
fusões e aquisições.
```

### Cálculo

```text
relevancia_global =
cosine(embedding_noticia, embedding_referencia)
```

### Threshold Inicial

```text
0.55
```

### Resultado

```json
{
  "relevancia_global": 0.87
}
```

### Regra

```text
relevancia_global < 0.55
```

→ Encerrar processamento.

---

## 5.2 Fase 2 — Relacionamento com Ativos

### Objetivo

Identificar ativos potencialmente impactados pela notícia.

### Estratégia

Cada ativo possuirá um embedding previamente calculado.

Exemplo:

```text
PETR4 Petrobras petróleo energia offshore combustíveis
```

```text
VALE3 Vale mineração minério ferro China commodities
```

### Processamento

```text
similaridade =
cosine(embedding_noticia, embedding_ativo)
```

### Threshold

```text
0.70
```

### Resultado

```json
{
  "tickers_relacionados": [
    "PETR4",
    "PRIO3"
  ]
}
```

---

## 5.3 Fase 3 — Score Heurístico

### Objetivo

Produzir um score interpretável para priorização inicial.

### Critérios

| Critério              | Peso |
| --------------------- | ---: |
| Ticker explícito      |    5 |
| Setor relacionado     |    4 |
| Evento macroeconômico |    4 |
| Indicador negativo    |    3 |
| Indicador de urgência |    2 |
| Fonte confiável       |    3 |

### Fórmula

```text
score_heuristico =
soma(pesos_acionados)
```

### Faixa

```text
0 a 20
```

---

## 5.4 Fase 4 — LLM de Relevância Binária

### Objetivo

Resolver casos ambíguos.

### Estratégia

| Score | Ação          |
| ----- | ------------- |
| ≥ 7   | Aprovar       |
| ≤ 2   | Rejeitar      |
| 3–6   | Consultar LLM |

### Modelo Sugerido

* GPT-4o Mini
* Gemini Flash
* Claude Haiku

### Saída

```json
{
  "relevancia_binaria": 1
}
```

---

## 5.5 Fase 5 — Classificação Rica

### Objetivo

Gerar metadados de negócio.

### Campos

```json
{
  "sentimento": "positivo",
  "impacto": "alto",
  "urgencia": 8,
  "categoria": "commodities"
}
```

### Categorias

* resultados
* regulacao
* commodities
* macroeconomia
* empresa
* tecnologia
* outros

### Modelos Sugeridos

* GPT-4o
* Claude Opus
* Gemini Pro

### Fallback

Classificação heurística baseada em palavras-chave e score acumulado.

---

## 5.6 Fase 6 — Motor de Priorização

### Objetivo

Determinar a ação operacional.

### Regras

| Condição                           | Prioridade | Ação                     |
| ---------------------------------- | ---------- | ------------------------ |
| Impacto alto + sentimento negativo | Crítica    | Email + Push + Dashboard |
| Impacto alto ou urgência ≥ 8       | Alta       | Push + Dashboard         |
| Score ≥ 10 ou relevância ≥ 0.85    | Média      | Dashboard                |
| Demais casos                       | Baixa      | Histórico                |

### Score de Ordenação

```text
score_final =
(relevancia_global × 0.4)
+
(score_heuristico / 20 × 0.4)
+
(urgencia / 10 × 0.2)
```

---

# 6. Contrato de Saída

Todos os componentes produzirão um objeto padronizado.

```json
{
  "relevancia_global": 0.87,
  "tickers_relacionados": ["PETR4", "PRIO3"],
  "score_heuristico": 12,
  "relevancia_binaria": 1,
  "sentimento": "negativo",
  "impacto": "alto",
  "urgencia": 8,
  "categoria": "commodities",
  "prioridade": "critica",
  "acao_sugerida": "email_push_dashboard",
  "explicacao": "Redução da produção da OPEP impacta diretamente o setor de petróleo"
}
```

---

# 7. Consequências

## Benefícios

* Redução significativa de chamadas para LLMs caros.
* Arquitetura explicável e auditável.
* Personalização por carteira.
* Fácil ajuste de thresholds.
* Escalabilidade para grande volume de notícias.

## Trade-offs

* Necessidade de manutenção de embeddings de ativos.
* Ajuste periódico de thresholds.
* Possibilidade de falsos positivos em similaridade semântica.
* Dependência de qualidade das descrições dos ativos.

---

# 8. Plano de Implementação

## Etapa 1 — Infraestrutura

* Instalar sentence-transformers.
* Criar módulo `core/intelligent_motor`.
* Implementar cache de embeddings.

## Etapa 2 — Motor Semântico

* Implementar Fase 1.
* Implementar Fase 2.
* Gerar embeddings da carteira.

## Etapa 3 — Motor Heurístico

* Implementar dicionários de palavras.
* Implementar cálculo de score.

## Etapa 4 — Integração com LLMs

* Cliente LLM econômico.
* Cliente LLM avançado.
* Estratégias de fallback.

## Etapa 5 — Alertas

* Implementar motor de decisão.
* Integrar ao `noticia_service.py`.

## Etapa 6 — Validação

* Testar com 50+ notícias reais.
* Ajustar thresholds.
* Medir precisão e custo operacional.

---

# 9. Métricas de Sucesso

## Técnicas

* Precision
* Recall
* F1 Score
* Taxa de descarte na Fase 1
* Taxa de aprovação por fase

## Negócio

* Redução de alertas irrelevantes
* Tempo médio até notificação
* Taxa de abertura dos alertas
* Redução de custo por notícia processada

```
```
