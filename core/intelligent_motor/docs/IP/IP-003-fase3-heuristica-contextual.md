# IP-003 — Plano de Implementação da Fase 3

## Objetivo

Implementar a Fase 3 do Intelligent Motor responsável pelo cálculo de score heurístico interpretável.

---

# História 1

Implementar infraestrutura da fase

## Tasks

### T3.1

Criar diretório:

```text
core/intelligent_motor/fase3_heuristica/
```

### T3.2

Criar arquivos base:

```text
__init__.py
config.yaml
criterios.py
pipeline.py
exceptions.py
logging.py
```

### T3.3

Adicionar configuração padrão.

---

# Entregável

Estrutura da fase criada.

---

# História 2

Implementar critérios heurísticos

## Tasks

### T3.4

Implementar:

```python
avaliar_ticker_explicito()
```

### T3.5

Implementar:

```python
avaliar_setor_relacionado()
```

### T3.6

Implementar:

```python
avaliar_palavras_macro()
```

### T3.7

Implementar:

```python
avaliar_palavras_negativas()
```

### T3.8

Implementar:

```python
avaliar_palavras_urgencia()
```

### T3.9

Implementar:

```python
avaliar_fonte_confiavel()
```

---

# Entregável

Todos os critérios implementados e testáveis individualmente.

---

# História 3

Implementar cálculo do score

## Tasks

### T3.10

Implementar:

```python
calcular_score_heuristico()
```

### T3.11

Registrar critérios ativados.

### T3.12

Retornar:

```python
{
    "score_heuristico": int,
    "criterios_ativados": []
}
```

---

# Entregável

Score calculado corretamente.

---

# História 4

Implementar pipeline

## Tasks

### T3.13

Criar função:

```python
avaliar_heuristica()
```

### T3.14

Receber resultado enriquecido das fases anteriores.

### T3.15

Executar todos os critérios.

### T3.16

Adicionar resultado ao payload.

---

# Entregável

Pipeline funcional.

---

# História 5

Implementar observabilidade

## Tasks

### T3.17

Criar módulo de logging.

### T3.18

Registrar:

- score
- critérios ativados
- tempo

### T3.19

Criar eventos de erro.

---

# Entregável

Logs padronizados.

---

# História 6

Criar testes

## Tasks

### T3.20

Testar ticker explícito.

### T3.21

Testar setor relacionado.

### T3.22

Testar palavras macro.

### T3.23

Testar palavras negativas.

### T3.24

Testar palavras urgentes.

### T3.25

Testar fonte confiável.

### T3.26

Testar cálculo completo do score.

### T3.27

Testar pipeline integrado.

---

# Entregável

Cobertura mínima de testes dos critérios e pipeline.

---

# Critérios de Aceitação

- Score calculado corretamente.
- Critérios configuráveis via YAML.
- Nenhum uso de LLM.
- Tempo médio inferior a 5 ms.
- Pipeline não interrompe execução em caso de erro.
- Logs gerados corretamente.
- Testes automatizados aprovados.

---

# Dependências

Entrada:

- Fase 1 concluída.
- Fase 2 concluída.

Saída utilizada por:

- Fase 4 (Gate de LLM).
- Fase 6 (Priorização de Alertas).
