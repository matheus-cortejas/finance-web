# IP-001 — Plano de Implementação da Fase 1 (Filtro Global de Relevância Financeira)

**Status:** Aprovado para Implementação  
**Relacionado a:** RFC-001 — Fase 1: Filtro Global de Relevância Financeira  
**Prioridade:** Alta

---

# 1. Objetivo

Implementar a Fase 1 do Motor Inteligente responsável por:

- pré-processamento textual;
- geração de embeddings;
- cálculo de relevância financeira global;
- cache de embeddings;
- descarte precoce de notícias irrelevantes.

Ao final da implementação deverá existir uma API interna capaz de receber uma notícia e retornar:

```python
{
    "id": Any,
    "relevancia_global": float,
    "embedding_noticia": List[float]
}
```

ou:

```python
None
```

quando a notícia não atingir o threshold mínimo.

---

# 2. Restrições Arquiteturais

A Fase 1 é um componente desacoplável do Motor Inteligente.

Ela NÃO deve possuir dependência direta de:

- FastAPI
- Flask
- Django
- Celery
- RabbitMQ
- Kafka
- PostgreSQL
- ORM
- Banco de dados da aplicação principal
- Pipeline de ingestão
- Pipeline de alertas
- Serviços externos da aplicação principal

Ela deve funcionar exclusivamente como biblioteca Python reutilizável.

## Entrada

A Fase 1 recebe uma notícia no seguinte formato:

```python
{
    "id": Any,
    "titulo": str,
    "descricao": str,
    "conteudo": str | None
}
```

## Saída (Notícia Aceita)

```python
{
    "id": Any,
    "relevancia_global": float,
    "embedding_noticia": List[float]
}
```

## Saída (Notícia Rejeitada)

```python
None
```

## Regras

### id

- obrigatório;
- identificador único da notícia;
- utilizado apenas para rastreabilidade;
- não participa do cálculo do embedding;
- não participa do cálculo da similaridade;
- não participa do cálculo da relevância;
- deve ser propagado integralmente para a saída;
- deve permanecer imutável durante todo o processamento.

### titulo

- obrigatório;
- utilizado no pré-processamento.

### descricao

- obrigatória;
- utilizada no pré-processamento.

### conteudo

- opcional;
- utilizado quando disponível;
- sujeito ao truncamento definido neste IP.

Toda integração externa será responsabilidade dos componentes consumidores.

---

# 3. Não Implementar

Não criar:

- APIs HTTP
- Endpoints
- Interfaces gráficas
- Dashboards
- Docker
- Kubernetes
- Prometheus
- Grafana
- Observabilidade avançada
- Autenticação
- Autorização
- Integrações externas
- Mensageria
- Banco relacional adicional

Esses itens pertencem a outros módulos.

---

# 4. Modo de Execução

Objetivo:

```text
Produzir código.
```

Não produzir:

- explicações;
- justificativas;
- documentação adicional;
- exemplos didáticos;
- propostas alternativas;
- replanejamento da arquitetura;
- análises de trade-offs.

Quando uma decisão estiver definida no RFC ou neste IP:

```text
implementar.
```

Não solicitar confirmação para tarefas previstas neste documento.

---

# 5. Política de Testes

Durante a implementação:

Não executar:

```text
pytest
coverage
benchmark
profiling
```

Criar apenas os arquivos de teste previstos.

A execução dos testes será realizada posteriormente pelo operador.

---

# 6. Critério de Resposta da LLM

Ao concluir uma etapa retornar apenas:

```text
STATUS: OK

CRIADOS:
- arquivo_a.py
- arquivo_b.py

MODIFICADOS:
- arquivo_c.py

PRÓXIMA ETAPA:
ETAPA X
```

Não incluir explicações.

---

# 7. Critérios de Conclusão

A implementação será considerada concluída quando:

- [ ] Todos os módulos previstos existirem.
- [ ] Todos os arquivos previstos existirem.
- [ ] O contrato definido no RFC-001 for respeitado.
- [ ] O cache Redis estiver implementado.
- [ ] O fallback SQLite estiver implementado.
- [ ] Os testes previstos estiverem criados.
- [ ] O pipeline retornar resultados válidos.

---

# 8. Estrutura de Diretórios

Criar:

```text
core/intelligent_motor/
└── fase1_global_filter/
    ├── __init__.py
    ├── config.yaml
    ├── embedding_generator.py
    ├── similarity.py
    ├── cache_manager.py
    ├── pipeline.py
    ├── exceptions.py
    └── tests/
```

---

# 9. Ordem Obrigatória de Implementação

Executar exatamente nesta sequência:

```text
ETAPA 1 → Configuração
ETAPA 2 → Pré-processamento
ETAPA 3 → Embeddings
ETAPA 4 → Similaridade
ETAPA 5 → Cache
ETAPA 6 → Pipeline
ETAPA 7 → Logging
ETAPA 8 → Geração dos Testes
ETAPA 9 → Checklist de Validação
```

Não iniciar a próxima etapa antes da conclusão da anterior.

---

# 10. ETAPA 1 — Configuração

## Arquivo

```text
config.yaml
```

## Conteúdo mínimo

```yaml
fase1:
  modelo: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

  texto_referencia: >
    Análise financeira, impacto econômico,
    resultados de empresas,
    mercados, commodities,
    juros, câmbio,
    regulação,
    fusões e aquisições

  threshold_relevancia: 0.55

  cache:
    backend: redis
    ttl_segundos: 86400
```

## Critério de Aceitação

- [ ] Configuração carregável.
- [ ] Possibilidade de override por ENV.

---

# 11. ETAPA 2 — Pré-processamento

## Arquivo

```text
preprocessor.py
```

## Função

```python
preprocessar_texto()
```

## Responsabilidades

### Concatenação

```python
titulo + descricao + conteudo
```

### Limpeza

Remover:

- múltiplos espaços;
- quebras de linha;
- caracteres de controle.

### Truncamento

```text
350 palavras
```

## Critério de Aceitação

Entrada:

```python
{
  "titulo": "...",
  "descricao": "...",
  "conteudo": "..."
}
```

Saída:

```python
str
```

---

# 12. ETAPA 3 — Embedding Generator

## Arquivo

```text
embedding_generator.py
```

## Classe

```python
EmbeddingGenerator
```

## Responsabilidades

- carregar modelo uma única vez;
- gerar embeddings normalizados;
- reutilizar instância carregada.

## Método

```python
gerar(texto: str) -> List[float]
```

## Configuração obrigatória

```python
normalize_embeddings=True
```

## Critério de Aceitação

- [ ] Retorna vetor.
- [ ] Vetor possui 384 dimensões.
- [ ] Singleton funcional.

---

# 13. ETAPA 4 — Similaridade

## Arquivo

```text
similarity.py
```

## Função

```python
calcular_similaridade()
```

## Implementação

Como os embeddings são normalizados:

```python
dot_product
```

## Critério de Aceitação

- [ ] Similaridade calculada corretamente.

---

# 14. ETAPA 5 — Cache

## Arquivo

```text
cache_manager.py
```

## Interface

```python
CacheManager
```

## Implementações

### RedisCache

Obrigatória.

### SQLiteCache

Obrigatória.

## Chave

```python
sha256(texto_preprocessado)
```

## Critério de Aceitação

Mesma notícia processada duas vezes:

```text
Primeira execução → MISS
Segunda execução → HIT
```

---

# 15. ETAPA 6 — Pipeline Principal

## Arquivo

```text
pipeline.py
```

## Método público

```python
avaliar_relevancia_global()
```

## Regra

O campo `id` deve ser preservado durante todo o pipeline e copiado para a saída sem qualquer modificação

## Fluxo

### Passo 1

Validar presença dos campos obrigatórios:

```python
id
titulo
descricao
```

### Passo 2

Pré-processar.

### Passo 3

Gerar hash.

### Passo 4

Consultar cache.

### Passo 5

Gerar embedding.

### Passo 6

Obter embedding da referência.

### Passo 7

Calcular similaridade.

### Passo 8

Aplicar threshold.

### Passo 9

Retornar resultado.

## Contrato

### Aceita

```python
{
    "id": 12345,
    "relevancia_global": 0.82,
    "embedding_noticia": [...]
}
```

### Descarta

```python
None
```

---

# 16. ETAPA 7 — Logging

## Eventos Obrigatórios

### INFO

```text
ACCEPT
DISCARD
CACHE_HIT
CACHE_MISS
```

### ERROR

```text
MODEL_ERROR
CACHE_ERROR
```

## Campos mínimos

```text
timestamp
id
fase
hash
score
decisao
tempo_ms
```

---

# 17. ETAPA 8 — Geração dos Testes

Criar:

```text
tests/
├── test_embedding.py
├── test_similarity.py
├── test_cache.py
└── test_pipeline.py
```

## Casos mínimos

### Embedding

- carregamento;
- dimensão;
- normalização.

### Similaridade

- identidade;
- ortogonalidade.

### Cache

- hit;
- miss;
- expiração.

### Pipeline

- aprovação;
- descarte;
- contrato.

---

# 18. ETAPA 9 — Checklist de Validação

Preparar validação para execução posterior.

Dataset mínimo:

```text
20 notícias financeiras
20 notícias não financeiras
```

Casos obrigatórios:

### Financeiras

- Petrobras
- Selic
- Dividendos
- Resultado trimestral

### Não Financeiras

- Futebol
- Receita culinária
- Celebridades
- Entretenimento

Resultado esperado:

```text
Financeiras → score alto
Não financeiras → score baixo
```

---

# 19. Entregáveis

Arquivos obrigatórios:

```text
config.yaml
preprocessor.py
embedding_generator.py
similarity.py
cache_manager.py
pipeline.py
exceptions.py

tests/test_embedding.py
tests/test_similarity.py
tests/test_cache.py
tests/test_pipeline.py
```

---

# 20. Documento Obrigatório Pós-Implementação

Após concluir o IP-001 gerar:

```text
IR-001-fase1-global-filter.md
```

Contendo:

- arquivos criados;
- arquivos modificados;
- decisões técnicas tomadas;
- desvios do RFC;
- limitações conhecidas;
- pendências;
- próximos passos.