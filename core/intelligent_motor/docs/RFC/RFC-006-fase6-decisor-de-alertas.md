# RPC-006 — Implementação: Fase 6 — Decisor de Alertas (Prioridade e Ação)

## 1. Objetivo

Implementar a camada final do Motor Inteligente responsável por transformar os metadados enriquecidos das Fases 1–5 em uma decisão operacional para o usuário.

A Fase 6 deve:

- Determinar a prioridade da notícia.
- Definir quais ações devem ser executadas.
- Calcular um score final para ordenação.
- Aplicar preferências do perfil do usuário.
- Gerar uma explicação legível da decisão.
- Produzir o JSON final consumido pelo `noticia_service.py`.

---

## 2. Escopo da Implementação

### Entrada

Notícia enriquecida pelas fases anteriores contendo, no mínimo:

- relevancia_global
- tickers_relacionados
- score_heuristico
- relevancia_binaria
- sentimento
- impacto
- urgencia
- categoria
- explicacao

### Saída

Adicionar ao objeto:

```json
{
  "prioridade": "critica",
  "acao_sugerida": [
    "email",
    "push",
    "dashboard_destacado"
  ],
  "score_final": 0.826,
  "regra_disparada": "impacto_negativo_alto",
  "explicacao": "Impacto alto com sentimento negativo: requer atenção imediata."
}
```

Mantendo todos os metadados acumulados anteriormente.

---

## 3. Arquivos a Implementar

### Estrutura

```text
core/intelligent_motor/fase6_decisor/

├── __init__.py
├── config.yaml
├── perfis.py
├── motor_regras.py
├── score_final.py
├── explicacao.py
├── pipeline.py
├── exceptions.py

└── tests/
    ├── test_motor_regras.py
    ├── test_score_final.py
    └── test_pipeline.py
```

---

## 4. Configuração

Criar:

```yaml
fase6:

  regras:

    - nome: impacto_negativo_alto

      condicoes:
        e:
          - impacto: alto
          - sentimento: negativo

      prioridade: critica

      acoes:
        - email
        - push
        - dashboard_destacado

      explicacao: >
        Impacto alto com sentimento negativo:
        requer atenção imediata.

    - nome: impacto_alto_ou_urgencia

      condicoes:
        ou:
          - impacto: alto
          - urgencia:
              min: 8

      prioridade: alta

      acoes:
        - push
        - dashboard

      explicacao: >
        Alto impacto ou urgência elevada.

    - nome: score_heuristico_ou_relevancia

      condicoes:
        ou:
          - score_heuristico:
              min: 10
          - relevancia_global:
              min: 0.85

      prioridade: media

      acoes:
        - dashboard

      explicacao: >
        Relevância significativa detectada.

    - nome: default

      condicoes: {}

      prioridade: baixa

      acoes:
        - historico

      explicacao: >
        Notícia registrada apenas para histórico.

  score_final:

    max_score_heuristico: 20
    max_urgencia: 10

    pesos:
      relevancia_global: 0.4
      score_heuristico: 0.4
      urgencia: 0.2

  acoes_canais:

    email: email
    push: push_notification
    dashboard: dashboard_entry
    dashboard_destacado: dashboard_destaque
    historico: historic_only

  perfil_padrao:

    canais_habilitados:
      - email
      - push
      - dashboard

    notificar_apenas_categorias: []

    thresholds_personalizados: null

  logging:
    level: INFO
```

---

## 5. perfis.py

Implementar:

### Classe

```python
class PerfilUsuario
```

Responsabilidades:

- Carregar perfil padrão.
- Validar canais.
- Validar categorias.
- Expor métodos utilitários.

### Métodos

```python
categoria_permitida(categoria)
```

Retorna:

```python
True | False
```

---

```python
canal_habilitado(canal)
```

Retorna:

```python
True | False
```

---

## 6. motor_regras.py

Implementar motor genérico de regras.

### Função principal

```python
avaliar_regras(
    metadados,
    regras
)
```

Retorna:

```python
{
    "nome": "...",
    "prioridade": "...",
    "acoes": [...],
    "explicacao": "..."
}
```

---

### Suportar

#### Igualdade simples

```yaml
impacto: alto
```

---

#### Intervalo

```yaml
urgencia:
  min: 8
```

---

#### Intervalo completo

```yaml
urgencia:
  min: 5
  max: 8
```

---

#### Operador OR

```yaml
ou:
  - impacto: alto
  - urgencia:
      min: 8
```

---

#### Operador AND

```yaml
e:
  - impacto: alto
  - sentimento: negativo
```

---

### Ordem

As regras devem ser avaliadas em sequência.

A primeira regra válida encerra a avaliação.

---

## 7. score_final.py

Implementar:

```python
calcular_score_final(
    metadados,
    config
)
```

Fórmula:

```text
score_final =
(relevancia_global × peso_relevancia)
+
(score_heuristico_normalizado × peso_heuristico)
+
(urgencia_normalizada × peso_urgencia)
```

---

Normalizações:

```text
score_heuristico_normalizado =
score_heuristico / max_score_heuristico
```

```text
urgencia_normalizada =
urgencia / max_urgencia
```

---

Resultado:

```python
round(score, 4)
```

---

## 8. explicacao.py

Implementar:

```python
gerar_explicacao(regra)
```

Inicialmente:

```python
return regra["explicacao"]
```

Objetivo futuro:

- Explicações dinâmicas.
- Templates.
- Personalização por usuário.

---

## 9. pipeline.py

Implementar:

```python
decidir_alerta(
    noticia,
    perfil=None
)
```

Fluxo:

### Passo 1

Carregar configuração.

---

### Passo 2

Carregar perfil.

Caso:

```python
perfil is None
```

Utilizar:

```yaml
perfil_padrao
```

---

### Passo 3

Executar:

```python
avaliar_regras()
```

---

### Passo 4

Aplicar filtros do perfil.

#### Categoria não permitida

Transformar para:

```python
prioridade = "baixa"
acoes = ["historico"]
```

---

#### Canal desabilitado

Remover ação.

Exemplo:

Antes:

```python
["email", "push", "dashboard"]
```

Depois:

```python
["dashboard"]
```

---

#### Nenhuma ação restante

Forçar:

```python
["historico"]
```

---

### Passo 5

Calcular:

```python
score_final
```

---

### Passo 6

Adicionar ao objeto:

```python
prioridade
acao_sugerida
score_final
regra_disparada
explicacao
```

---

### Passo 7

Retornar notícia enriquecida.

---

## 10. Logging

Registrar:

### Regra aplicada

```text
FASE6_RULE_MATCH
```

Campos:

```text
regra
prioridade
acoes
```

---

### Aplicação de perfil

```text
FASE6_PROFILE_FILTER
```

Campos:

```text
categoria_permitida
canais_filtrados
```

---

### Resultado final

```text
FASE6_RESULT
```

Campos:

```text
prioridade
score_final
regra
```

---

## 11. Exceções

Criar:

```python
class Fase6Error(Exception):
    pass
```

---

Tratar:

### Configuração inválida

Utilizar regra default hardcoded.

---

### Perfil inválido

Forçar:

```python
prioridade = "baixa"
acoes = ["historico"]
```

---

### Campo ausente

Considerar condição não satisfeita.

Não interromper pipeline.

---

## 12. Testes Unitários

### test_motor_regras.py

Validar:

- igualdade simples
- min
- max
- AND
- OR
- prioridade da primeira regra válida
- regra default

---

### test_score_final.py

Caso:

```python
relevancia_global = 0.5
score_heuristico = 10
urgencia = 5
```

Resultado esperado:

```python
0.5
```

---

Caso máximo:

```python
relevancia_global = 1
score_heuristico = 20
urgencia = 10
```

Resultado esperado:

```python
1.0
```

---

### test_pipeline.py

Validar:

#### Categoria bloqueada

Resultado:

```python
prioridade = baixa
acoes = ["historico"]
```

---

#### Canal removido

Resultado:

```python
["dashboard"]
```

---

#### Todos os canais removidos

Resultado:

```python
["historico"]
```

---

## 13. Critérios de Aceitação

### Funcionais

- Regras avaliadas corretamente.
- Primeira regra válida interrompe busca.
- Perfil aplicado corretamente.
- Score calculado corretamente.
- JSON final enriquecido.

### Não Funcionais

- Sem dependências pesadas.
- Tempo médio inferior a 1 ms.
- Configuração totalmente externa em YAML.
- Compatível com pipeline atual.

---

## 14. Entrega Esperada

Ao final da implementação a Fase 6 deverá produzir o objeto final consumido pelo sistema de alertas:

```json
{
  "titulo": "...",
  "relevancia_global": 0.87,
  "score_heuristico": 12,
  "sentimento": "negativo",
  "impacto": "alto",
  "urgencia": 8,
  "categoria": "commodities",

  "prioridade": "critica",

  "acao_sugerida": [
    "email",
    "push",
    "dashboard_destacado"
  ],

  "score_final": 0.826,

  "regra_disparada": "impacto_negativo_alto",

  "explicacao": "Impacto alto com sentimento negativo: requer atenção imediata."
}
```

Esta fase encerra o fluxo analítico do Motor Inteligente e entrega a decisão operacional final para consumo pelo `noticia_service.py`.