# RFC-004 — Fase 4: Classificação Binária Condicional via LLM de Baixo Custo

**Status:** Aprovado  
**Autor:** Equipe de Engenharia  
**Data:** 2026-06-02

---

# 1. Contexto

A Fase 3 (Heurística Contextual) produz um `score_heuristico` baseado em critérios configuráveis, permitindo classificar notícias segundo sua potencial relevância para investidores.

Entretanto, existe uma faixa intermediária de incerteza onde as heurísticas não são suficientes para determinar com confiança se a notícia deve avançar para as próximas etapas do pipeline.

Atualmente:

- Scores altos possuem forte evidência de relevância.
- Scores baixos possuem forte evidência de irrelevância.
- Scores intermediários geram falsos positivos e falsos negativos.

É necessário introduzir um mecanismo de decisão mais preciso para essa faixa intermediária sem incorrer no custo de utilizar modelos mais sofisticados em todas as notícias.

---

# 2. Problema

As heurísticas da Fase 3 são eficientes e baratas, porém possuem limitações inerentes:

- Não compreendem contexto semântico.
- Não distinguem relevância real de simples presença de palavras-chave.
- Podem classificar incorretamente notícias ambíguas.

Por outro lado, encaminhar todas as notícias para modelos avançados aumenta significativamente o custo operacional.

É necessário um mecanismo intermediário que:

- Seja barato.
- Seja rápido.
- Reduza falsos positivos.
- Reduza falsos negativos.
- Diminua o volume enviado para as fases posteriores.

---

# 3. Decisão

Será criada uma nova etapa denominada:

**Fase 4 — Classificação Binária Condicional via LLM de Baixo Custo**

A fase utilizará um modelo OpenAI econômico para decidir se uma notícia possui relevância potencial para investidores.

A decisão será binária:

- `1` → Relevante
- `0` → Irrelevante

O modelo será acionado apenas quando o score heurístico estiver dentro da faixa de incerteza.

---

# 4. Fluxo Decidido

```text
Score Heurístico
       │
       ▼

score >= 7
       │
       └──► Relevante (1)

score <= 2
       │
       └──► Irrelevante (0)

3 <= score <= 6
       │
       ▼
LLM Barata
       │
       ├──► 1 = Relevante
       └──► 0 = Irrelevante
```

Somente notícias classificadas como relevantes continuarão para as próximas fases do pipeline.

---

# 5. Provedor Escolhido

A implementação inicial utilizará exclusivamente OpenAI.

Modelo inicial:

```text
gpt-4o-mini
```

Motivações:

- Baixo custo.
- Baixa latência.
- Facilidade de integração.
- Infraestrutura OpenAI já existente no projeto.
- Menor complexidade operacional.

---

# 6. Decisões Arquiteturais

## 6.1 Reutilização da infraestrutura existente

A Fase 4 deverá reutilizar componentes já existentes sempre que possível.

Especialmente:

- Cliente OpenAI já utilizado pelo motor anterior.
- Configuração centralizada.
- Sistema de logging existente.
- Sistema de cache já utilizado pela Fase 1.

Evita-se duplicação de código e reduz-se manutenção futura.

---

## 6.2 Não implementar múltiplos provedores inicialmente

Embora a especificação original considere OpenAI e Gemini, apenas OpenAI será suportado nesta entrega.

Motivos:

- Redução de complexidade.
- Menor superfície de testes.
- Menor custo de manutenção.
- Não há necessidade operacional atual para múltiplos provedores.

A arquitetura deverá permitir expansão futura caso necessário.

---

## 6.3 Classificação exclusivamente binária

A Fase 4 não produzirá:

- sentimento
- urgência
- impacto
- setor
- score contínuo

Seu único objetivo é decidir:

```text
0 ou 1
```

Qualquer classificação adicional permanece responsabilidade das fases posteriores.

---

## 6.4 Uso de Prompt Minimalista

O prompt deverá permanecer curto para minimizar:

- custo por chamada
- latência
- consumo de tokens

A informação principal enviada ao modelo será:

- título
- descrição
- conteúdo (quando disponível)
- critérios heurísticos ativados

---

## 6.5 Aproveitamento dos Critérios da Fase 3

Os critérios ativados pela heurística deverão ser enviados ao modelo sempre que disponíveis.

Exemplo:

```text
Critérios ativados:
- ticker
- macro
- impacto
```

Essa informação fornece contexto adicional ao modelo com custo mínimo de tokens.

---

## 6.6 Cache Obrigatório

As respostas da Fase 4 deverão utilizar cache compartilhado com o restante do sistema.

Objetivos:

- Evitar chamadas repetidas.
- Reduzir custo.
- Reduzir latência.
- Melhorar escalabilidade.

O cache será indexado por hash do prompt gerado.

---

## 6.7 Estratégia de Fallback

Em caso de falha da OpenAI:

- timeout
- indisponibilidade
- erro de autenticação
- rate limit

será utilizado um valor configurável.

Valor inicial recomendado:

```text
fallback = 1
```

Motivação:

É preferível permitir que uma notícia potencialmente relevante avance para as próximas etapas do que descartá-la prematuramente.

---

# 7. Consequências

## Benefícios

- Redução significativa do volume enviado para modelos mais caros.
- Menor quantidade de falsos positivos.
- Melhor precisão geral do pipeline.
- Baixo custo operacional.
- Fácil manutenção.

## Custos

- Dependência de API externa.
- Pequeno aumento de latência para notícias ambíguas.
- Necessidade de monitoramento de custos e rate limits.

---

# 8. Critérios de Sucesso

A Fase 4 será considerada bem-sucedida quando:

- Notícias claramente irrelevantes forem descartadas antes da Fase 5.
- O custo total por notícia permanecer baixo.
- A latência média permanecer dentro dos limites definidos.
- A quantidade de chamadas à LLM forte diminuir significativamente.

---

# 9. Fora do Escopo

Não fazem parte desta RFC:

- Classificação de sentimento.
- Extração de entidades.
- Resumo automático.
- Múltiplos provedores LLM.
- Fine-tuning de modelos.
- Personalização por usuário.

Essas funcionalidades poderão ser consideradas em RFCs futuras.

---

# 10. Referências

- RFC-001 — Fase 1: Filtro Global de Relevância
- RFC-002 — Fase 2: Relacionamento com Tickers
- RFC-003 — Fase 3: Heurística Contextual

---

Fim do documento.