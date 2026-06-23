# IP-005 — Plano de Implementação da Fase 5 (Classificação Rica e Enriquecimento Semântico via LLM)

**Status:** Aprovado para Implementação
**Relacionado a:** RFC-005 — Fase 5: Classificação Rica e Enriquecimento Semântico via LLM
**Prioridade:** Alta

---

# 1. Objetivo

Implementar a Fase 5 responsável por:

* enriquecimento semântico de notícias aprovadas pela Fase 4;
* classificação estruturada utilizando LLM;
* geração de metadados de negócio;
* reutilização da infraestrutura OpenAI existente;
* utilização de cache para redução de custos;
* fallback heurístico para garantir resiliência.

Ao final deverá existir uma API interna capaz de receber:

```python
noticia_pipeline
```

e retornar:

```python
{
    "sentimento": "positivo",
    "impacto": "alto",
    "urgencia": 8,
    "categoria": "commodities",
    "explicacao": "Redução da produção da OPEP impacta diretamente o setor de petróleo."
}
```

---

# 2. Restrições Arquiteturais

A Fase 5 deve funcionar exclusivamente como biblioteca Python.

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
* sistema de configuração utilizado pelo projeto.

---

# 3. Estrutura de Diretórios

```text
core/intelligent_motor/
└── fase5_rich_classification/
    ├── __init__.py
    ├── config.yaml
    ├── prompt_builder.py
    ├── llm_classifier.py
    ├── validator.py
    ├── fallback.py
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
ETAPA 4 → Validação
ETAPA 5 → Cache
ETAPA 6 → Fallback
ETAPA 7 → Pipeline
ETAPA 8 → Logging
ETAPA 9 → Testes
ETAPA 10 → Checklist
```

---

# 5. ETAPA 1 — Configuração

Arquivo:

```text
config.yaml
```

Conteúdo mínimo:

```yaml
fase5:

  llm:

    provider: openai

    model: gpt-4o

    temperature: 0.0

    max_tokens: 150

  fallback:

    enabled: true

  cache:

    enabled: true

  max_content_chars: 800
```

Critérios:

* [ ] Configuração carregável.
* [ ] Modelo configurável.
* [ ] Limites configuráveis.
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

Gerar prompt para classificação rica.

Entradas:

```python
titulo
descricao
conteudo
tickers_relacionados
score_heuristico
```

Saída esperada da LLM:

```json
{
  "sentimento": "...",
  "impacto": "...",
  "urgencia": 0,
  "categoria": "...",
  "explicacao": "..."
}
```

Critérios:

* [ ] Prompt curto.
* [ ] JSON obrigatório.
* [ ] Sem texto adicional.
* [ ] Explicação obrigatória.

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
Extrair JSON
↓
Retornar dicionário
```

Modelo inicial:

```text
gpt-4o
```

Critérios:

* [ ] Integração funcional.
* [ ] Tratamento de erros.
* [ ] Parsing de JSON.

---

# 8. ETAPA 4 — Validação

Arquivo:

```text
validator.py
```

Função:

```python
validar_resposta()
```

Campos obrigatórios:

```text
sentimento
impacto
urgencia
categoria
explicacao
```

Validações mínimas:

### Sentimento

```text
positivo
neutro
negativo
```

### Impacto

```text
baixo
medio
alto
```

### Urgência

```text
0 <= urgencia <= 10
```

### Categoria

```text
string não vazia
```

### Explicação

```text
string não vazia
```

Critérios:

* [ ] Respostas inválidas rejeitadas.
* [ ] Respostas válidas aprovadas.

---

# 9. ETAPA 5 — Cache

Arquivo:

```text
llm_classifier.py
```

Responsabilidades:

* gerar hash do prompt;
* consultar cache;
* reutilizar respostas anteriores;
* armazenar novos resultados.

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

# 10. ETAPA 6 — Fallback

Arquivo:

```text
fallback.py
```

Responsabilidade:

Produzir classificação válida quando:

* OpenAI falhar;
* timeout ocorrer;
* JSON inválido for recebido;
* validação falhar.

Saída mínima:

```python
{
    "sentimento": "...",
    "impacto": "...",
    "urgencia": ...,
    "categoria": "...",
    "explicacao": "Classificação produzida por fallback heurístico."
}
```

Critérios:

* [ ] Nunca retorna campos ausentes.
* [ ] Nunca interrompe o pipeline.

---

# 11. ETAPA 7 — Pipeline

Arquivo:

```text
pipeline.py
```

Função pública:

```python
classificar_noticia_rica()
```

Entrada mínima esperada:

```python
{
    "titulo": "...",
    "descricao": "...",
    "conteudo": "...",

    "tickers_relacionados": [...],

    "score_heuristico": 8,

    "relevancia_binaria": 1
}
```

Fluxo:

```text
Receber notícia
↓
Montar prompt
↓
Consultar cache
↓
Executar LLM
↓
Validar resposta
↓
Fallback se necessário
↓
Enriquecer objeto
↓
Retornar objeto atualizado
```

Exemplo:

```python
{
    ...
    "sentimento": "negativo",
    "impacto": "alto",
    "urgencia": 8,
    "categoria": "commodities",
    "explicacao": "Redução da produção da OPEP impacta diretamente o setor de petróleo."
}
```

---

# 12. ETAPA 8 — Logging

Eventos obrigatórios:

```text
LLM_CLASSIFICATION
CACHE_HIT
CACHE_MISS
LLM_FALLBACK
VALIDATION_ERROR
```

Campos mínimos:

```text
timestamp
fase
hash
modelo
tempo_ms
```

Exemplo:

```json
{
  "fase": "fase5",
  "modelo": "gpt-4o",
  "tempo_ms": 1250
}
```

---

# 13. ETAPA 9 — Testes

Criar:

```text
tests/
├── test_prompt_builder.py
├── test_llm_classifier.py
├── test_validator.py
├── test_fallback.py
└── test_pipeline.py
```

Casos mínimos:

### Prompt Builder

* gera prompt válido;
* inclui notícia;
* exige JSON.

### Validator

* resposta válida;
* campo ausente;
* urgência inválida;
* categoria vazia.

### LLM Classifier

* JSON válido;
* JSON inválido;
* timeout;
* erro OpenAI.

### Fallback

* gera classificação completa;
* gera explicação.

### Pipeline

* cache hit;
* cache miss;
* validação aprovada;
* validação falha;
* fallback.

---

# 14. ETAPA 10 — Checklist de Validação

Dataset mínimo:

```text
50 notícias aprovadas pela Fase 4
```

Distribuição recomendada:

```text
15 positivas
15 negativas
10 neutras
10 macroeconômicas
```

Casos obrigatórios:

### Resposta Válida

Resultado esperado:

```text
Classificação aceita
```

---

### JSON Inválido

Resultado esperado:

```text
Fallback acionado
```

---

### Timeout

Resultado esperado:

```text
Fallback acionado
```

---

### Cache

Executar mesma notícia duas vezes.

Resultado esperado:

```text
Segunda execução via cache
```

---

# 15. Entregáveis

Arquivos obrigatórios:

```text
config.yaml
prompt_builder.py
llm_classifier.py
validator.py
fallback.py
pipeline.py
exceptions.py
```

---

# 16. Documento Obrigatório Pós-Implementação

Após concluir o IP-005 gerar:

```text
IR-005-fase5-classificacao-rica.md
```

Contendo:

* arquivos criados;
* arquivos modificados;
* decisões técnicas tomadas;
* desvios do RFC;
* limitações conhecidas;
* métricas de cache;
* métricas de fallback;
* custos observados;
* pendências;
* próximos passos.

---

# 17. Compatibilidade com a Fase 6

A saída da Fase 5 deverá ser compatível com o contrato arquitetural definido pelo ADR-001.

Campos produzidos:

```json
{
  "sentimento": "negativo",
  "impacto": "alto",
  "urgencia": 8,
  "categoria": "commodities",
  "explicacao": "Redução da produção da OPEP impacta diretamente o setor de petróleo."
}
```

A responsabilidade de gerar:

```text
prioridade
acao_sugerida
```

permanece exclusivamente na Fase 6.

---

Fim do documento.