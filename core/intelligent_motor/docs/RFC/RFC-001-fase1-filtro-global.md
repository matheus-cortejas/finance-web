# RFC-001 — Fase 1: Filtro Global de Relevância Financeira

**Status:** Draft
**Relacionado ao ADR:** ADR-001 — Motor Inteligente de Classificação e Priorização de Notícias Financeiras
**Versão:** 1.0
**Autor:** Equipe de Engenharia
**Última atualização:** 2026-06-01

---

# 1. Objetivo

Esta RFC define a implementação da primeira etapa do Motor Inteligente de Notícias.

A Fase 1 é responsável por:

* Filtrar notícias sem relevância financeira.
* Produzir um score contínuo de relevância financeira.
* Gerar e armazenar o embedding da notícia.
* Reduzir o volume de processamento das fases subsequentes.
* Servir como ponto único de entrada do pipeline semântico.

---

# 2. Motivação

A maioria das notícias ingeridas pelo sistema não possui impacto financeiro relevante.

Executar heurísticas complexas ou modelos de linguagem sobre todo o volume de entrada resulta em:

* Maior custo computacional.
* Maior latência.
* Maior custo operacional com LLMs.

A utilização de embeddings permite eliminar uma parcela significativa do ruído logo no início do fluxo.

---

# 3. Escopo

## Incluído

* Pré-processamento textual.
* Geração de embeddings.
* Similaridade semântica.
* Cache de embeddings.
* Decisão de descarte.
* Logging.
* Métricas operacionais.

## Não Incluído

* Relacionamento com ativos.
* Classificação de sentimento.
* Priorização de alertas.
* Chamadas para LLMs.

Esses componentes pertencem às fases posteriores.

---

# 4. Arquitetura

## Fluxo

```text
Notícia
   │
   ▼
Pré-processamento
   │
   ▼
Geração de Embedding
   │
   ▼
Similaridade com Referência Financeira
   │
   ▼
Threshold
 ┌───────┴────────┐
 ▼                ▼
Descartar      Aprovar
                    │
                    ▼
         Embedding Persistido
                    │
                    ▼
             Fase 2
```

---

# 5. Requisitos Funcionais

## RF-01

O sistema deve receber:

```python
{
    "id": Any,
    "titulo": str,
    "descricao": str,
    "conteudo": str | None
}
```

## RF-02

O sistema deve gerar um embedding semântico da notícia.

## RF-03

O sistema deve calcular a similaridade entre a notícia e uma referência financeira.

## RF-04

O sistema deve retornar um score de relevância entre 0 e 1.

## RF-05

O sistema deve descartar notícias abaixo do threshold configurado.

## RF-06

O sistema deve armazenar o embedding gerado para reutilização futura.

---

# 6. Requisitos Não Funcionais

## RNF-01 — Performance

Tempo médio por notícia:

```text
< 50 ms
```

excluindo carregamento inicial do modelo.

## RNF-02 — Reutilização

O embedding gerado deve ser reutilizado pela Fase 2.

## RNF-03 — Escalabilidade

A arquitetura deve permitir processamento paralelo.

## RNF-04 — Observabilidade

Toda decisão deve ser rastreável através de logs e métricas.

---

# 7. Modelo de Embedding

## Modelo Selecionado

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

## Justificativa

* Multilíngue.
* Excelente desempenho para português.
* Baixo consumo de memória.
* Inferência rápida.
* Vetores de 384 dimensões.

## Características

| Propriedade  | Valor       |
| ------------ | ----------- |
| Dimensões    | 384         |
| Idiomas      | Multilíngue |
| Normalização | Sim         |
| Uso de GPU   | Opcional    |

---

# 8. Referência Financeira

A referência financeira utilizada para comparação semântica será:

```text
Análise financeira, impacto econômico, resultados de empresas,
mercados, commodities, juros, câmbio, regulação,
fusões e aquisições.
```

## Regras

* Gerar embedding apenas uma vez.
* Manter em memória.
* Persistir em cache.
* Recalcular apenas quando o texto de referência mudar.

---

# 9. Pré-processamento

## Estratégia

A notícia será convertida em um único bloco textual para a geração de embeddings.

## Campos Utilizados

- titulo
- descricao
- conteudo

## Campo Preservado 

- id

## Texto gerado

```text
titulo + descricao + conteúdo_truncado
```

---

## Limpeza

Remover:

* múltiplos espaços;
* quebras de linha;
* caracteres de controle.

---

## Truncamento

Limitar:

```text
350 palavras
```

ou aproximadamente:

```text
512 tokens
```

---

# 10. Cache

## Objetivo

Evitar recomputação de embeddings.

---

## Chave

```python
sha256(texto_preprocessado)
```

---

## Backends Suportados

### Redis (preferencial)

```text
TTL padrão: 24h
```

### SQLite

Fallback local.

---

## Estrutura

```python
emb:{hash}
```

para notícias.

```python
ref_key = "ref:financeiro_mult"
```

para referência.

---

# 11. Algoritmo de Similaridade

Como os embeddings são normalizados:

```python
similaridade = dot(emb_noticia, emb_referencia)
```

Não é necessário recalcular normas.

---

## Faixa Esperada

```text
0.0 → irrelevante
1.0 → altamente relevante
```

---

# 12. Política de Decisão

## Threshold Inicial

```text
0.55
```

---

## Regras

### Aprovação

```text
score >= 0.55
```

### Descarte

```text
score < 0.55
```

---

## Ajuste Futuro

O threshold deverá ser recalibrado utilizando:

* Precision
* Recall
* Curva ROC
* AUC

sobre dados reais.

---

# 13. Contrato de Saída

## Sucesso

```json
{
  "id": 1, 
  "relevancia_global": 0.82,
}
```

---

## Descarte

```python
None
```

---

# 14. Interface Pública

## Método Principal

```python
avaliar_relevancia_global(
    noticia: Dict[str, Any]
)
```

---

## Exemplo

```python
resultado = avaliar_relevancia_global(
    titulo="Taxa Selic sobe para 13,75%",
    descricao="Copom aumenta juros",
    conteudo="..."
)
```

---

# 15. Tratamento de Falhas

| Evento             | Ação                   |
| ------------------ | ---------------------- |
| Texto vazio        | Descartar              |
| Falha no cache     | Recalcular             |
| Redis indisponível | Fallback SQLite        |
| Falha no modelo    | Encerrar inicialização |
| Dimensão inválida  | Erro crítico           |

---

# 16. Logging

## Log Estruturado

```text
fase=fase1
chave=<hash>
score=0.67
decision=ACCEPT
tempo_ms=12
```

---

## Eventos Obrigatórios

* início de processamento;
* cache hit;
* cache miss;
* descarte;
* aprovação;
* erro.

---

# 17. Métricas (não implementado)

## Contadores

```text
fase1_entrada_total
fase1_aceitas
fase1_descartadas
```

## Performance

```text
fase1_tempo_medio_ms
fase1_tempo_p95_ms
```

## Cache

```text
fase1_cache_hits
fase1_cache_misses
```

---

# 18. Estratégia de Testes

## Unitários

### Similaridade

Validar:

```python
cos(a,a) == 1
cos(a,b) == 0
```

---

## Integração

Casos:

### Financeiro

```text
Petrobras anuncia aumento de dividendos
```

Resultado esperado:

```text
score > 0.70
```

---

### Não Financeiro

```text
Receita de bolo de cenoura
```

Resultado esperado:

```text
score < 0.40
```

---

### Ambíguo

```text
Governo altera regras do setor elétrico
```

Resultado esperado:

```text
score ≈ 0.55–0.70
```

---

# 19. Critérios de Aceitação

A implementação será considerada concluída quando:

* [ ] Modelo carregado corretamente.
* [ ] Cache Redis funcional.
* [ ] Fallback SQLite funcional.
* [ ] Similaridade calculada corretamente.
* [ ] Threshold configurável.
* [ ] Logging estruturado implementado.
* [ ] Métricas expostas.
* [ ] Cobertura mínima de testes ≥ 80%.
* [ ] Integração com Fase 2 validada.

---

# 20. Evoluções Futuras

## Curto Prazo

* Ajuste automático de threshold.
* Cache distribuído.
* Batch embeddings.

## Médio Prazo

* Ensemble de múltiplos embeddings.
* Referências financeiras por categoria.
* Aprendizado supervisionado para relevância.

## Longo Prazo

* Modelo proprietário treinado em notícias financeiras.
* Fine-tuning com feedback dos usuários.
* Ranking contextual por perfil de investidor.

```
```
