# IP-004 — Plano de Implementação da Fase 4 (Classificação Binária Condicional via LLM)

**Status:** Aprovado para Implementação  
**Relacionado a:** RFC-004 — Fase 4: Classificação Binária Condicional via LLM de Baixo Custo  
**Prioridade:** Alta

---

# 1. Objetivo

Implementar a Fase 4 responsável por:

* classificação binária de notícias via LLM;
* reutilização da infraestrutura OpenAI existente;
* utilização de cache para reduzir custos;
* aplicação condicional baseada no score heurístico;
* fallback em caso de falhas externas.

Ao final deverá existir uma API interna capaz de receber:

```python
noticia
```

e

```python
score_heuristico
```

retornando:

```python
1
```

ou

```python
0
```

---

# 2. Restrições Arquiteturais

A Fase 4 deve funcionar exclusivamente como biblioteca Python.

Não criar:

* APIs HTTP
* FastAPI
* Flask
* Django
* Celery
* Kafka
* RabbitMQ
* Banco relacional adicional

A implementação deve reutilizar:

* cliente OpenAI existente;
* sistema de cache existente;
* infraestrutura de logging existente;
* sistema de configuração já utilizado pelo projeto.

---

# 3. Estrutura de Diretórios

```text
core/intelligent_motor/
└── fase4_llm_gate/
    ├── __init__.py
    ├── config.yaml
    ├── prompt_builder.py
    ├── llm_classifier.py
    ├── pipeline.py
    ├── exceptions.py
    └── tests/
```

---

# 4. Ordem Obrigatória de Implementação

```text
ETAPA 1 → Configuração
ETAPA 2 → Prompt Builder
ETAPA 3 → Cliente LLM
ETAPA 4 → Cache
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
fase4:

  score_aprovacao_direta: 7

  score_rejeicao_direta: 2

  faixa_llm:
    minimo: 3
    maximo: 6

  llm:
    provider: openai
    model: gpt-4o-mini

  fallback_resultado: 1

  cache:
    enabled: true
```

Critérios:

* [ ] Configuração carregável.
* [ ] Faixas configuráveis.
* [ ] Modelo configurável.
* [ ] Fallback configurável.

---

# 6. ETAPA 2 — Prompt Builder

Arquivo:

```text
prompt_builder.py
```

Função:

```python
build_prompt()
```

Responsabilidade:

Gerar o prompt enviado à LLM.

Entradas:

```python
titulo
descricao
conteudo
criterios_ativados
```

Formato mínimo:

```text
Você é um classificador de notícias financeiras.

Determine se esta notícia possui potencial relevância para investidores.

Responda apenas:

1
ou
0

Título:
...

Descrição:
...

Critérios ativados:
...
```

Critérios:

* [ ] Prompt curto.
* [ ] Resposta estritamente binária.
* [ ] Critérios heurísticos incluídos.

---

# 7. ETAPA 3 — Cliente LLM

Arquivo:

```text
llm_classifier.py
```

Classe:

```python
LLMClassifier
```

Método principal:

```python
classificar()
```

Fluxo:

```text
Receber prompt
↓
Enviar para OpenAI
↓
Receber resposta
↓
Normalizar saída
↓
Retornar 0 ou 1
```

Modelo inicial:

```text
gpt-4o-mini
```

Critérios:

* [ ] Integração funcional.
* [ ] Retorna apenas 0 ou 1.
* [ ] Tratamento de erros implementado.

---

# 8. ETAPA 4 — Cache

Arquivo:

```text
llm_classifier.py
```

Responsabilidades:

* gerar hash do prompt;
* consultar cache;
* reutilizar respostas anteriores;
* armazenar novas respostas.

Fluxo:

```text
Prompt
↓
Hash
↓
Cache hit?
├─ Sim → Retorna resultado
└─ Não → Chama OpenAI
```

Critérios:

* [ ] Cache funcional.
* [ ] Hash consistente.
* [ ] Evita chamadas duplicadas.

---

# 9. ETAPA 5 — Pipeline

Arquivo:

```text
pipeline.py
```

Função pública:

```python
classificar_noticia()
```

Fluxo:

```text
Receber score heurístico
↓
score >= 7
↓
Retorna 1

score <= 2
↓
Retorna 0

3 <= score <= 6
↓
Executa LLM
↓
Retorna resultado
```

Critérios:

* [ ] Bypass para scores altos.
* [ ] Bypass para scores baixos.
* [ ] Chamada da LLM apenas quando necessário.

---

# 10. ETAPA 6 — Logging

Eventos obrigatórios:

```text
LLM_CLASSIFICATION
CACHE_HIT
CACHE_MISS
LLM_FALLBACK
```

Campos mínimos:

```text
timestamp
fase
hash
score
decisao
tempo_ms
```

Exemplo:

```json
{
  "fase": "fase4",
  "hash": "abc123",
  "score": 5,
  "decisao": 1,
  "tempo_ms": 240
}
```

---

# 11. ETAPA 7 — Testes

Criar:

```text
tests/
├── test_prompt_builder.py
├── test_llm_classifier.py
└── test_pipeline.py
```

Casos mínimos:

### Prompt Builder

* gera prompt válido;
* inclui critérios;
* inclui notícia.

### LLM Classifier

* resposta "1";
* resposta "0";
* resposta inválida;
* timeout;
* erro OpenAI.

### Pipeline

* score alto;
* score baixo;
* score intermediário;
* cache hit;
* fallback.

---

# 12. ETAPA 8 — Checklist de Validação

Dataset mínimo:

```text
50 notícias financeiras
```

Distribuição recomendada:

```text
20 claramente relevantes
20 claramente irrelevantes
10 ambíguas
```

Casos obrigatórios:

### Score Alto

Entrada:

```text
score = 8
```

Resultado esperado:

```text
1
```

Sem chamada à LLM.

---

### Score Baixo

Entrada:

```text
score = 2
```

Resultado esperado:

```text
0
```

Sem chamada à LLM.

---

### Score Intermediário

Entrada:

```text
score = 5
```

Resultado esperado:

```text
LLM acionada
```

---

### Cache

Executar mesma notícia duas vezes.

Resultado esperado:

```text
Segunda execução via cache
```

---

### Fallback

Simular falha OpenAI.

Resultado esperado:

```text
Retorno = 1
```

---

# 13. Entregáveis

Arquivos obrigatórios:

```text
config.yaml
prompt_builder.py
llm_classifier.py
pipeline.py
exceptions.py
```

---

# 14. Documento Obrigatório Pós-Implementação

Após concluir o IP-004 gerar:

```text
IR-004-fase4-classificacao-binaria-llm.md
```

Contendo:

* arquivos criados;
* arquivos modificados;
* decisões técnicas tomadas;
* desvios do RFC;
* limitações conhecidas;
* métricas de cache;
* custos observados;
* pendências;
* próximos passos.

---