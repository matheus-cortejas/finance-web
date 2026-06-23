# IP-002 — Plano de Implementação da Fase 2 (Relacionamento Semântico com Ativos)

**Status:** Aprovado para Implementação
**Relacionado a:** RFC-002 — Fase 2: Relacionamento Semântico com Ativos
**Prioridade:** Alta

---

# 1. Objetivo

Implementar a Fase 2 responsável por:

* armazenamento de embeddings dos ativos;
* consulta de ativos da carteira;
* cálculo de similaridade;
* relacionamento semântico com tickers.

Ao final deverá existir uma API interna capaz de receber:

```python
embedding_noticia
```

e

```python
carteira_usuario
```

retornando:

```python
[
    "PETR4",
    "PRIO3"
]
```

---

# 2. Restrições Arquiteturais

A Fase 2 deve funcionar exclusivamente como biblioteca Python.

Não criar:

* APIs HTTP
* FastAPI
* Flask
* Django
* Celery
* Kafka
* RabbitMQ
* Banco relacional adicional

---

# 3. Estrutura de Diretórios

```text
core/intelligent_motor/
└── fase2_tickers/
    ├── __init__.py
    ├── config.yaml
    ├── ativos_mapeamento.json
    ├── asset_embedding_store.py
    ├── similarity.py
    ├── pipeline.py
    ├── exceptions.py
    └── tests/
```

---

# 4. Ordem Obrigatória de Implementação

```text
ETAPA 1 → Configuração
ETAPA 2 → Mapeamento dos Ativos
ETAPA 3 → Asset Store
ETAPA 4 → Similaridade
ETAPA 5 → Pipeline
ETAPA 6 → Logging
ETAPA 7 → Testes
ETAPA 8 → Checklist
```

---

# 5. ETAPA 1 — Configuração

Arquivo:

```text
config.yaml
```

Conteúdo mínimo:

```yaml
fase2:
  threshold_similaridade: 0.70

  cache:
    backend: sqlite

  mapeamento_ativos: ativos_mapeamento.json
```

Critérios:

* [ ] Configuração carregável.
* [ ] Threshold configurável.

---

# 6. ETAPA 2 — Mapeamento dos Ativos

Arquivo:

```text
ativos_mapeamento.json
```

Tickers obrigatórios:

```text
PETR4
VALE3
PRIO3
ITUB4
BBAS3
BBDC4
WEGE3
ABEV3
```

Critério:

* [ ] Arquivo válido.
* [ ] Todos os ativos possuem descrição.

---

# 7. ETAPA 3 — Asset Store

Arquivo:

```text
asset_embedding_store.py
```

Classe:

```python
AssetEmbeddingStore
```

Responsabilidades:

* carregar descrições;
* gerar embeddings;
* persistir embeddings;
* recuperar embeddings.

Critérios:

* [ ] Geração funcional.
* [ ] Persistência funcional.
* [ ] Consulta funcional.

---

# 8. ETAPA 4 — Similaridade

Arquivo:

```text
similarity.py
```

Função:

```python
cosine_similarity()
```

Implementação:

```python
dot_product
```

Critério:

* [ ] Similaridade correta.

---

# 9. ETAPA 5 — Pipeline

Arquivo:

```text
pipeline.py
```

Função pública:

```python
relacionar_tickers()
```

Fluxo:

```text
Receber embedding da notícia
↓
Consultar ativos
↓
Calcular similaridade
↓
Aplicar threshold
↓
Ordenar
↓
Retornar tickers
```

Critérios:

* [ ] Retorna lista.
* [ ] Respeita threshold.
* [ ] Ordenação correta.

---

# 10. ETAPA 6 — Logging

Eventos obrigatórios:

```text
TICKER_RELATED
NO_TICKER_RELATED
TICKER_WITHOUT_EMBEDDING
```

Campos mínimos:

```text
timestamp
fase
ticker
score
tempo_ms
```

---

# 11. ETAPA 7 — Testes

Modificar:

```text
tests/
├── test_asset_store.py
├── test_similarity.py
└── test_pipeline.py
```

da Fase 1.

Casos mínimos:

### Asset Store

* geração;
* persistência;
* consulta.

### Similaridade

* identidade;
* vetores distintos.

### Pipeline

* ticker relacionado;
* carteira vazia;
* nenhum ticker relacionado.

---

# 12. ETAPA 8 — Checklist de Validação

Dataset mínimo:

```text
20 notícias financeiras
```

Carteira:

```text
PETR4
VALE3
ITUB4
BBAS3
```

Casos obrigatórios:

### Petróleo

Resultado esperado:

```text
PETR4
PRIO3
```

### Mineração

Resultado esperado:

```text
VALE3
```

### Bancos

Resultado esperado:

```text
ITUB4
BBAS3
BBDC4
```

---

# 13. Entregáveis

Arquivos obrigatórios:

```text
config.yaml
ativos_mapeamento.json
asset_embedding_store.py
similarity.py
pipeline.py
exceptions.py

```

---

# 14. Documento Obrigatório Pós-Implementação

Após concluir o IP-002 gerar:

```text
IR-002-fase2-relacionamento-tickers.md
```

Contendo:

* arquivos criados;
* arquivos modificados;
* decisões técnicas tomadas;
* desvios do RFC;
* limitações conhecidas;
* pendências;
* próximos passos.

```
```
