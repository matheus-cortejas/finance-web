# RFC-003 — Fase 3: Heurística Contextual (Score Interpretável)

## Status

Proposto

## Objetivo

Introduzir uma camada heurística rápida, interpretável e determinística capaz de estimar a relevância potencial de uma notícia para investidores antes da utilização de modelos LLM.

A Fase 3 não descarta notícias. Seu papel é enriquecer os metadados da notícia com um score heurístico que será utilizado pelas fases posteriores para tomada de decisão e priorização.

---

## Motivação

Após a Fase 1 (relevância global) e a Fase 2 (relacionamento semântico com ativos), o sistema já possui:

- Embedding da notícia
- Score de relevância global
- Lista de tickers relacionados

Entretanto, ainda não existe uma medida interpretável que sintetize sinais clássicos utilizados por analistas humanos, como:

- presença explícita de tickers;
- eventos macroeconômicos;
- notícias negativas;
- urgência;
- credibilidade da fonte.

A Fase 3 fornece essa camada de interpretação.

---

## Escopo

A fase será responsável por:

- analisar texto da notícia;
- aplicar critérios heurísticos configuráveis;
- produzir score inteiro;
- registrar critérios ativados;
- anexar resultado ao objeto da notícia.

A fase não:

- consulta LLMs;
- gera embeddings;
- descarta notícias;
- altera resultados de fases anteriores.

---

## Critérios Avaliados

### Critério A — Ticker Explícito

Detecta presença explícita de tickers B3 no texto.

Peso padrão: +5

---

### Critério B — Setor Relacionado

Ativado quando a Fase 2 retorna ao menos um ticker relacionado.

Peso padrão: +4

---

### Critério C — Impacto Macroeconômico

Detecta palavras-chave macroeconômicas.

Exemplos:

- selic
- inflação
- juros
- copom
- ipca

Peso padrão: +4

---

### Critério D — Impacto Negativo

Detecta eventos potencialmente prejudiciais.

Exemplos:

- prejuízo
- fraude
- crise
- multa
- recuperação judicial

Peso padrão: +3

---

### Critério E — Urgência

Detecta situações de atenção imediata.

Exemplos:

- urgente
- alerta
- emergencial

Peso padrão: +2

---

### Critério F — Fonte Confiável (Opcional)

A disponibilidade da fonte depende do coletor RSS utilizado.

Como nem todos os feeds fornecem essa informação de forma
estruturada, a ausência da fonte NÃO deve impedir a execução da Fase 3.

Quando o campo `fonte` estiver ausente:

- nenhum ponto é adicionado;
- nenhum ponto é removido;
- o critério é considerado não avaliado.

A implementação deve funcionar normalmente sem este campo.

---

## Cálculo do Score

O score é calculado pela soma dos pesos dos critérios ativados.

Exemplo:

Ticker explícito (+5)
Setor relacionado (+4)
Negativo (+3)

Resultado:

Score = 12

---

## Saída

A fase adicionará os seguintes campos ao objeto da notícia:

```json
{
  "score_heuristico": 12,
  "criterios_ativados": [
    "ticker",
    "setor",
    "negativo"
  ]
}
```

---

## Integração com o Pipeline

### Integração com o Pipeline Existente

A Fase 3 não deve receber dados diretamente da notícia original.

Ela deve operar sobre o objeto enriquecido produzido pelas fases anteriores.

Estrutura mínima esperada:

```python
{
    "id": 40,
    "titulo": "...",
    "descricao": "...",
    "conteudo": "...",

    "relevancia_global": 0.2954,
    "embedding_noticia": [...],

    "tickers_relacionados": [
        "NVDA",
        "ABEV3"
    ]
}
```

Campos obrigatórios:

titulo
descricao
tickers_relacionados

Campos opcionais:

conteudo
id

Campos ignorados pela Fase 3:

embedding_noticia
relevancia_global

A Fase 3 utilizará apenas o texto consolidado da notícia e a lista de tickers relacionados produzida pela Fase 2.

Após execução, o pipeline deverá enriquecer o mesmo objeto:

```python
{
    noticia_pipeline["score_heuristico"] = score
    noticia_pipeline["criterios_ativados"] = criterios
}
```

Exemplo:

```python
{
    ...
    "tickers_relacionados": ["NVDA"],
    "score_heuristico": 11,
    "criterios_ativados": [
        "ticker",
        "setor",
        "negativo"
    ]
}
```

---

## Observabilidade

A fase deverá registrar:

- score final;
- critérios ativados;
- tempo de execução.

Exemplo:

```text
INFO fase3
score=12
criterios=ticker,setor,negativo
tempo=0.3ms
```

---

## Tratamento de Falhas

A fase deve ser resiliente.

Em caso de erro:

- registrar evento;
- retornar score 0;
- nunca interromper o pipeline.

---

## Métricas

Serão coletadas:

- fase3_score_medio
- fase3_tempo_medio_ms
- fase3_distribuicao_scores

---

## Decisões Arquiteturais

### DA-001

Critérios devem ser implementados como funções independentes.

### DA-002

Pesos e listas de palavras devem ser configuráveis externamente.

### DA-003

Nenhum critério deve depender de LLM.

### DA-004

A fase deve executar em menos de 5 ms por notícia.

---

## Compatibilidade Futura

A estrutura permite:

- inclusão de novos critérios;
- alteração de pesos sem mudança de código;
- calibração contínua baseada em dados reais.
