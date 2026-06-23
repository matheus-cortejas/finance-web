# RFC-002 — Fase 2: Relacionamento Semântico com Ativos (Tickers)

**Status:** Draft
**Relacionado ao ADR:** ADR-001 — Motor Inteligente de Classificação e Priorização de Notícias Financeiras
**Versão:** 1.0
**Autor:** Equipe de Engenharia
**Última atualização:** 2026-06-01

---

# 1. Objetivo

Esta RFC define a implementação da segunda etapa do Motor Inteligente de Notícias.

A Fase 2 é responsável por:

* Relacionar notícias aos ativos da carteira do usuário.
* Detectar impactos potenciais mesmo sem menção explícita do ticker.
* Utilizar embeddings semânticos para associação notícia ↔ ativo.
* Produzir uma lista ordenada de tickers relacionados.
* Enriquecer os metadados da notícia para as fases posteriores.

---

# 2. Motivação

Buscar apenas códigos de negociação dentro do texto não é suficiente.

Exemplo:

```text
Preço do petróleo sobe após decisão da OPEP.
```

Mesmo sem mencionar explicitamente:

```text
PETR4
PRIO3
RECV3
```

a notícia possui forte relação semântica com empresas do setor.

A utilização de embeddings permite capturar essas relações de forma automática e escalável.

---

# 3. Escopo

## Incluído

* Consulta de embeddings dos ativos.
* Similaridade semântica notícia ↔ ativo.
* Seleção de tickers relacionados.
* Cache persistente dos embeddings dos ativos.
* Logging.
* Métricas operacionais.

## Não Incluído

* Heurísticas de relevância.
* Sentimento.
* Priorização.
* Chamadas para LLM.
* Descarte de notícias.

---

# 4. Arquitetura

```text
Embedding da Notícia
        │
        ▼
Consulta dos Embeddings
dos Ativos da Carteira
        │
        ▼
Cálculo de Similaridade
        │
        ▼
Aplicação de Threshold
        │
        ▼
Tickers Relacionados
        │
        ▼
Fase 3
```

---

# 5. Requisitos Funcionais

## RF-01

Receber o embedding normalizado produzido pela Fase 1.

---

## RF-02

Receber a carteira do usuário.

```python
[
    "PETR4",
    "VALE3",
    "ITUB4"
]
```

---

## RF-03

Consultar embeddings previamente armazenados dos ativos.

---

## RF-04

Calcular similaridade semântica entre notícia e ativo.

---

## RF-05

Selecionar ativos acima do threshold configurado.

---

## RF-06

Retornar ativos ordenados por score decrescente.

---

## RF-07

Nunca descartar notícias.

Mesmo sem ativos relacionados:

```python
{
    "tickers_relacionados": []
}
```

a notícia continuará para a próxima fase.

---

# 6. Requisitos Não Funcionais

## RNF-01 — Performance

Tempo médio:

```text
< 5 ms
```

para carteiras com até 50 ativos.

---

## RNF-02 — Reutilização

Deve reutilizar o mesmo modelo carregado pela Fase 1.

---

## RNF-03 — Persistência

Embeddings dos ativos devem ser persistidos.

---

## RNF-04 — Observabilidade

Toda decisão deve ser registrada em logs estruturados.

---

# 7. Mapeamento dos Ativos

Cada ativo deve possuir uma descrição semântica.

Exemplo:

```json
{
  "PETR4": "Petrobras petróleo energia combustíveis offshore exploração refino",
  "VALE3": "Vale mineração minério de ferro commodities China siderurgia"
}
```

---

# 8. Embeddings dos Ativos

## Modelo

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

---

## Regras

* Normalizados.
* Persistidos.
* Reutilizados.
* Recalculados apenas quando o mapeamento mudar.

---

## Chaves

```text
asset:PETR4
asset:VALE3
asset:ITUB4
```

---

# 9. Similaridade

Como os embeddings são normalizados:

```python
similaridade = dot(
    embedding_noticia,
    embedding_ativo
)
```

---

# 10. Política de Decisão

## Threshold Inicial

```text
0.70
```

---

## Regra

```text
similaridade > threshold
```

Ativo relacionado.

---

## Regra

```text
similaridade <= threshold
```

Ativo ignorado.

---

# 11. Contrato de Entrada

```python
{
    "id": 123,
    "relevancia_global": 0.82,
}
```

---

# 12. Contrato de Saída

```python
{
    "id": 123,
    "relevancia_global": 0.82,
    "tickers_relacionados": [
        "PETR4",
        "PRIO3"
    ]
}
```

---

# 13. Interface Pública

```python
relacionar_tickers(
    noticia: Dict[str, Any],
    carteira_usuario: List[str]
) -> List[str]
```

---

# 14. Logging

## Logging

A Fase 2 deverá reutilizar o módulo:

core/intelligent_motor/fase1_global_filter/logging.py

Mantendo o mesmo contrato estrutural de logs definido na Fase 1.

## INFO

```text
TICKER_RELATED
NO_TICKER_RELATED
```

## WARNING

```text
TICKER_WITHOUT_EMBEDDING
```

## ERROR

```text
ASSET_STORE_ERROR
```

---

# 15. Métricas

## Contadores

```text
fase2_tickers_consultados
fase2_tickers_relacionados
```

## Performance

```text
fase2_tempo_medio_ms
fase2_tempo_p95_ms
```

---

# 16. Estratégia de Testes

## Unitários

Validar:

```python
dot(a,a) == 1
```

---

## Integração

### Petróleo

```text
Petrobras anuncia novo campo no pré-sal
```

Resultado esperado:

```text
PETR4
```

---

### Receita de bolo

Resultado esperado:

```python
[]
```

---

### Carteira vazia

Resultado esperado:

```python
[]
```

---

# 17. Critérios de Aceitação

* [ ] AssetStore implementado.
* [ ] Embeddings persistidos.
* [ ] Similaridade funcionando.
* [ ] Threshold configurável.
* [ ] Logging implementado.
* [ ] Métricas implementadas.
* [ ] Cobertura mínima ≥ 80%.
* [ ] Integração com Fase 1 validada.

---

# 18. Evoluções Futuras

## Curto Prazo

* Atualização automática de embeddings.
* Cache distribuído.

## Médio Prazo

* Relação ativo → setor → subsetor.
* Múltiplas descrições por ativo.

## Longo Prazo

* Embeddings especializados em mercado financeiro.
* Indexação vetorial.

```
```
