# IP-006 — Plano de Implementação da Fase 6 (Decisor de Alertas, Priorização e Ações)

**Status:** Aprovado para Implementação
**Relacionado a:** RFC-006 — Fase 6: Decisor de Alertas, Priorização e Ações
**Prioridade:** Alta

---

# 1. Objetivo

Implementar a Fase 6 responsável por:

* transformar metadados analíticos em decisões acionáveis;
* definir prioridade final da notícia;
* determinar canais de entrega;
* calcular score final para ordenação;
* aplicar preferências de usuário;
* produzir explicação interpretável da decisão.

Ao final deverá existir uma API interna capaz de receber:

```python
noticia_pipeline
```

e retornar:

```python
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

---

# 2. Restrições Arquiteturais

A Fase 6 deve funcionar exclusivamente como biblioteca Python.

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

* sistema de configuração existente;
* infraestrutura de logging existente;
* objetos produzidos pelas Fases 1 a 5;
* mecanismos de cache já disponíveis quando necessário.

---

# 3. Estrutura de Diretórios

```text
core/intelligent_motor/
└── fase6_decisor/
    ├── __init__.py
    ├── config.yaml
    ├── perfis.py
    ├── motor_regras.py
    ├── score_final.py
    ├── explicacao.py
    ├── pipeline.py
    ├── exceptions.py
    └── tests/
```

---

# 4. Ordem Obrigatória de Implementação

```text
ETAPA 1 → Configuração
ETAPA 2 → Perfil do Usuário
ETAPA 3 → Motor de Regras
ETAPA 4 → Score Final
ETAPA 5 → Explicação
ETAPA 6 → Pipeline
ETAPA 7 → Logging
ETAPA 8 → Testes
ETAPA 9 → Checklist
```

---

# 5. ETAPA 1 — Configuração

Arquivo:

```text
config.yaml
```

Conteúdo mínimo:

```yaml
fase6:

  regras:

    - nome: impacto_negativo_alto

      condicoes:
        impacto: alto
        sentimento: negativo

      prioridade: critica

      acoes:
        - email
        - push
        - dashboard_destacado

      explicacao: >
        Impacto alto com sentimento negativo:
        requer atenção imediata.

    - nome: default

      condicoes: {}

      prioridade: baixa

      acoes:
        - historico

      explicacao: >
        Notícia armazenada apenas para histórico.

  score_final:

    pesos:

      relevancia_global: 0.4

      score_heuristico: 0.4

      urgencia: 0.2

    max_score_heuristico: 20

    max_urgencia: 10

  perfil_padrao:

    canais_habilitados:
      - email
      - push
      - dashboard

    notificar_apenas_categorias: []
```

Critérios:

* [ ] Configuração carregável.
* [ ] Regras configuráveis.
* [ ] Pesos configuráveis.
* [ ] Perfil padrão configurável.

---

# 6. ETAPA 2 — Perfil do Usuário

Arquivo:

```text
perfis.py
```

Classe:

```python
PerfilUsuario
```

Responsabilidades:

* carregar preferências;
* validar canais;
* validar categorias;
* aplicar restrições de notificação.

Interface mínima:

```python
perfil.categoria_permitida()
perfil.canal_habilitado()
```

Critérios:

* [ ] Perfil padrão funcional.
* [ ] Categorias filtráveis.
* [ ] Canais filtráveis.

---

# 7. ETAPA 3 — Motor de Regras

Arquivo:

```text
motor_regras.py
```

Função principal:

```python
avaliar_regras()
```

Fluxo:

```text
Receber notícia
↓
Percorrer regras
↓
Avaliar condições
↓
Primeira regra válida
↓
Retornar decisão
```

Tipos suportados:

### Igualdade

```yaml
impacto: alto
```

### Intervalo

```yaml
urgencia:
  min: 8
```

### Operador OR

```yaml
ou:
  - impacto: alto
  - urgencia:
      min: 8
```

### Operador AND

```yaml
e:
  - impacto: alto
  - sentimento: negativo
```

Critérios:

* [ ] Condições simples.
* [ ] Intervalos.
* [ ] Operador OR.
* [ ] Operador AND.
* [ ] Regra default.

---

# 8. ETAPA 4 — Score Final

Arquivo:

```text
score_final.py
```

Função:

```python
calcular_score_final()
```

Fórmula:

```text
score_final =
    relevancia_global * peso1 +
    score_heuristico_normalizado * peso2 +
    urgencia_normalizada * peso3
```

Normalização:

```text
score_heuristico / max_score_heuristico

urgencia / max_urgencia
```

Faixa esperada:

```text
0.0 até 1.0
```

Critérios:

* [ ] Score consistente.
* [ ] Pesos configuráveis.
* [ ] Normalização correta.

---

# 9. ETAPA 5 — Explicação

Arquivo:

```text
explicacao.py
```

Função:

```python
gerar_explicacao()
```

Responsabilidade:

Produzir texto final baseado na regra disparada.

Exemplo:

```text
Impacto alto com sentimento negativo: requer atenção imediata.
```

Critérios:

* [ ] Texto sempre presente.
* [ ] Compatível com regra disparada.

---

# 10. ETAPA 6 — Pipeline

Arquivo:

```text
pipeline.py
```

Função pública:

```python
decidir_alerta()
```

Entrada mínima:

```python
{
    "relevancia_global": 0.85,
    "score_heuristico": 12,
    "sentimento": "negativo",
    "impacto": "alto",
    "urgencia": 8,
    "categoria": "commodities"
}
```

Fluxo:

```text
Receber notícia
↓
Carregar perfil
↓
Avaliar regras
↓
Aplicar restrições do perfil
↓
Calcular score final
↓
Gerar explicação
↓
Retornar resultado
```

Saída:

```python
{
    ...
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

Critérios:

* [ ] Pipeline funcional.
* [ ] Compatível com Fase 5.
* [ ] Não altera metadados anteriores.

---

# 11. ETAPA 7 — Logging

Eventos obrigatórios:

```text
FASE6_RULE_MATCH
FASE6_PROFILE_FILTER
FASE6_SCORE_CALCULATED
FASE6_DECISION
FASE6_ERROR
```

Campos mínimos:

```text
timestamp
regra
prioridade
acoes
score_final
```

Exemplo:

```json
{
  "fase": "fase6",
  "regra": "impacto_negativo_alto",
  "prioridade": "critica",
  "score_final": 0.826
}
```

---

# 12. ETAPA 8 — Testes

Criar:

```text
tests/
├── test_motor_regras.py
├── test_score_final.py
├── test_perfis.py
├── test_pipeline.py
```

Casos mínimos:

### Motor de Regras

* igualdade;
* intervalo;
* OR;
* AND;
* regra default.

### Score Final

* score intermediário;
* score máximo;
* score mínimo.

### Perfil

* categoria permitida;
* categoria bloqueada;
* canal habilitado;
* canal desabilitado.

### Pipeline

* regra crítica;
* regra média;
* fallback default;
* filtro por perfil.

---

# 13. ETAPA 9 — Checklist de Validação

Dataset mínimo:

```text
50 notícias classificadas pela Fase 5
```

Casos obrigatórios:

### Impacto Alto + Sentimento Negativo

Resultado esperado:

```text
Prioridade crítica
```

---

### Urgência Alta

Resultado esperado:

```text
Prioridade alta
```

---

### Categoria Não Permitida

Resultado esperado:

```text
Prioridade baixa
Ação histórico
```

---

### Todos os Canais Desabilitados

Resultado esperado:

```text
Ação histórico
```

---

### Score Final

Resultado esperado:

```text
Valor entre 0.0 e 1.0
```

---

# 14. Entregáveis

Arquivos obrigatórios:

```text
config.yaml
perfis.py
motor_regras.py
score_final.py
explicacao.py
pipeline.py
exceptions.py
```

---

# 15. Documento Obrigatório Pós-Implementação

Após concluir o IP-006 gerar:

```text
IR-006-fase6-decisor-alertas.md
```

Contendo:

* arquivos criados;
* arquivos modificados;
* regras implementadas;
* decisões técnicas tomadas;
* desvios do RFC;
* métricas de distribuição de prioridades;
* métricas de distribuição de ações;
* limitações conhecidas;
* pendências;
* próximos passos.

---

# 16. Compatibilidade com a Fase 7

A saída da Fase 6 deverá ser compatível com o contrato arquitetural definido pelo ADR-001.

Campos produzidos:

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

A responsabilidade de executar:

```text
envio de email
push notification
dashboard
persistência
```

permanece exclusivamente nas camadas superiores do sistema.

---

Fim do documento.
