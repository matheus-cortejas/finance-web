# IR-003 — Implementação: Fase 3 — Heurística Contextual

**Status:** Concluído
**Autor:** Equipe de Engenharia
**Data:** 2026-06-02

---

## 1. Arquivos Criados

- core/intelligent_motor/fase3_heuristica/config.yaml
- core/intelligent_motor/fase3_heuristica/__init__.py
- core/intelligent_motor/fase3_heuristica/criterios.py
- core/intelligent_motor/fase3_heuristica/pipeline.py
- core/intelligent_motor/fase3_heuristica/exceptions.py
- core/intelligent_motor/fase3_heuristica/logging.py
- core/intelligent_motor/fase3_heuristica/validation_checklist.yaml

Testes unitários criados:

- core/intelligent_motor/fase3_heuristica/tests/test_criterios.py
- core/intelligent_motor/fase3_heuristica/tests/test_pipeline.py

---

## 2. Arquivos Modificados

Nenhum arquivo existente foi modificado além das adições listadas.

---

## 3. Decisões Técnicas

- Critérios implementados como funções independentes em `criterios.py`.
- Pesos e listas de palavras configuráveis via `config.yaml`.
- Pipeline expõe `avaliar_heuristica(noticia)` que enriquece o objeto com `score_heuristico` e `criterios_ativados`.
- Logging reutiliza o módulo de logging da Fase 1 para manter consistência.
- A implementação foi expandida em relação ao RFC original, adicionando critérios complementares:
  - impacto
  - tendência positiva
  - tendência negativa
  - ambiguidade
- O critério de fonte confiável pode utilizar o domínio extraído da URL da notícia quando o campo `fonte` não estiver disponível.
- O critério de ticker explícito foi ampliado para suportar tickers com 4 ou 5 letras seguidas de um dígito.

---

## 4. Desvios e Limitações

### Desvios em relação ao RFC/IP

- Foram adicionados critérios heurísticos não previstos na versão inicial do RFC:
  - impacto
  - tendência positiva
  - tendência negativa
  - ambiguidade

- A identificação de fonte confiável foi adaptada para funcionar mesmo quando a notícia não possui o campo `fonte`, utilizando o domínio extraído da URL.

### Limitações Resolvidas

- O carregamento da configuração YAML ocorria múltiplas vezes durante a avaliação dos critérios. Recomenda-se cache da configuração ou injeção do objeto de configuração pelo pipeline.
- A estrutura atual das listas de palavras no YAML exige validação cuidadosa para evitar agrupamento incorreto de múltiplos termos em uma única string.
- Tempo de execução não foi medido em ambiente produtivo.

---

## 5. Pendências

### Curto prazo

- Implementar cache de configuração (`config.yaml`) para evitar leituras repetidas em disco.
- Normalizar automaticamente listas de palavras carregadas do YAML.
- Definir comportamento oficial para casos de tendência positiva e negativa simultâneas.

### Médio prazo

- Calibrar pesos e palavras-chave utilizando dados reais.
- Revisar listas de palavras periodicamente conforme evolução do mercado financeiro.
- Instrumentar métricas operacionais (tempo médio, distribuição de scores, frequência de critérios ativados).

### Integração

- Integrar a Fase 3 ao pipeline principal.
- Validar fluxo completo Fase 1 → Fase 2 → Fase 3.
- Preparar integração com a Fase 4 (decisor de uso de LLM).

## 5. Pendências

- Calibrar pesos e palavras-chave com dados reais.
- Integrar a fase ao pipeline principal e validar end-to-end.

---

Fim do documento.
