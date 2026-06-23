# IR-001 — Implementação: Fase 1 — Filtro Global de Relevância Financeira

**Status:** Concluído
**Autor:** Equipe de Engenharia
**Data:** 2026-06-01

---

## 1. Arquivos Criados

- core/intelligent_motor/fase1_global_filter/config.yaml
- core/intelligent_motor/fase1_global_filter/__init__.py
- core/intelligent_motor/fase1_global_filter/preprocessor.py
- core/intelligent_motor/fase1_global_filter/embedding_generator.py
- core/intelligent_motor/fase1_global_filter/similarity.py
- core/intelligent_motor/fase1_global_filter/cache_manager.py
- core/intelligent_motor/fase1_global_filter/pipeline.py
- core/intelligent_motor/fase1_global_filter/exceptions.py
- core/intelligent_motor/fase1_global_filter/logging.py
- core/intelligent_motor/fase1_global_filter/validation_checklist.yaml

Testes unitários criados:

- core/intelligent_motor/fase1_global_filter/tests/test_embedding.py
- core/intelligent_motor/fase1_global_filter/tests/test_similarity.py
- core/intelligent_motor/fase1_global_filter/tests/test_cache.py
- core/intelligent_motor/fase1_global_filter/tests/test_pipeline.py

---

## 2. Arquivos Modificados

Nenhum arquivo existente foi modificado além das adições listadas.

---

## 3. Decisões Técnicas

- Modelo de embeddings: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (conforme RFC/IP).
- Geração de embeddings normalizados via `SentenceTransformer` com `normalize_embeddings=True`.
- Similaridade calculada por produto escalar (dot product) assumindo embeddings normalizados.
- Cache: implementação preferencial `RedisCache` com fallback `SQLiteCache` local.
- Chave de cache: `sha256(texto_preprocessado)` para notícias; referência em `ref:financeiro`.
- Pipeline implementado como biblioteca desacoplada com função pública `avaliar_relevancia_global()`.

---

## 4. Desvios do RFC/IP

- O módulo logging.py foi implementado.
- As chamadas de logging não foram integradas em todos os pontos previstos do pipeline.
- Eventos ACCEPT, DISCARD, CACHE_HIT, CACHE_MISS, MODEL_ERROR e CACHE_ERROR não são garantidamente emitidos durante a execução.
- A integração completa do logging permanece como pendência técnica.

## 4.1 Divergências Conhecidas

- O contrato de saída atualmente retorna apenas:
  - id
  - relevancia_global

  O campo embedding_noticia permanece disponível internamente
  através do cache e não é exposto ao consumidor.

- Logging estruturado e métricas operacionais permanecem
  planejados para versões futuras.

- A interface pública recebe um objeto notícia completo,
  divergindo da assinatura inicialmente prevista no RFC.

---

## 5. Limitações Conhecidas

- Requer a presença do pacote `sentence_transformers` para carregar o modelo real; testes usam mocks.
- A integração com Redis depende de serviço externo; o código faz fallback automático para SQLite quando o Redis não está disponível.
- Métricas de produção, exposição de métricas e instrumentação externa não foram implementadas (fora do escopo).
- Observabilidade avançada (Prometheus/Grafana) e infraestrutura não foram criadas (fora do escopo).

---

## 6. Pendências

- Validar e calibrar `threshold_relevancia` em dados reais.
- Provisionar e configurar Redis em ambiente de execução (opcional para performance).
- Executar suíte de testes e corrigir eventuais incompatibilidades de ambiente.
- Integrar `avaliar_relevancia_global()` no pipeline externo (Fase 2) e validar contratos.
- Adicionar métricas e contadores operacionais (cache hits/misses, latências, contadores de decisão).

---

## 7. Próximos Passos

- Executar os testes unitários criados e ajustar implementações conforme necessidade.
- Calibrar threshold utilizando datasets rotulados (conforme checklist de validação).
- Integrar com o componente de relacionamento com ativos (Fase 2).
- Implantar cache Redis em ambiente de staging e avaliar ganhos de desempenho.

---

Fim do documento.
