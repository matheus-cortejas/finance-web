# RFC-005 — Fase 5: Classificação Rica e Enriquecimento Semântico via LLM

**Status:** Proposto
**Autor:** Equipe de Engenharia
**Data:** 2026-06-XX

---

# 1. Contexto

As fases anteriores do Motor Inteligente possuem responsabilidades distintas:

- Fase 1: filtrar notícias sem relevância financeira;
- Fase 2: relacionar notícias com ativos;
- Fase 3: produzir score heurístico interpretável;
- Fase 4: decidir se a notícia é relevante utilizando classificação binária condicional.

Ao final da Fase 4, o sistema já sabe que uma notícia possui potencial relevância para investidores.

Entretanto, ainda não existem informações suficientes para determinar:

- potencial impacto da notícia;
- urgência de reação;
- natureza do evento;
- efeito esperado sobre os ativos relacionados.

É necessária uma etapa de enriquecimento semântico capaz de transformar notícias relevantes em metadados estruturados de negócio.

---

# 2. Problema

A classificação binária produzida pela Fase 4 responde apenas à pergunta:

```text
A notícia é relevante?
```

Porém o sistema de alertas necessita responder perguntas adicionais:

```text
O impacto é alto ou baixo?

A notícia exige ação imediata?

O efeito esperado é positivo ou negativo?

Qual é o tipo principal do evento?
```

Sem essas informações torna-se impossível priorizar adequadamente notificações, dashboards e alertas futuros.

---

# 3. Decisão

Será criada uma nova etapa denominada:

**Fase 5 — Classificação Rica e Enriquecimento Semântico via LLM**

A fase utilizará um modelo OpenAI para gerar metadados estruturados a partir de notícias previamente aprovadas pela Fase 4.

A saída deverá conter:

- sentimento;
- impacto;
- urgência;
- categoria;
- explicação.

---

# 4. Fluxo Decidido

```text
Notícia aprovada pela Fase 4
        │
        ▼

Classificação Rica via LLM
        │
        ▼

Validação da Resposta
        │
        ├──► Resposta válida
        │         │
        │         ▼
        │   Retorna metadados
        │
        └──► Falha
                  │
                  ▼
          Fallback Heurístico
                  │
                  ▼
           Retorna metadados
```

A Fase 5 nunca deverá interromper o pipeline.

---

# 5. Campos Produzidos

## 5.1 Sentimento

Representa o efeito esperado da notícia sobre os ativos ou mercado relacionados.

Valores permitidos:

```text
positivo
neutro
negativo
```

---

## 5.2 Impacto

Representa a magnitude potencial da notícia.

Valores permitidos:

```text
baixo
medio
alto
```

---

## 5.3 Urgência

Representa a necessidade de reação imediata.

Faixa:

```text
0 a 10
```

Onde:

```text
0 = nenhuma urgência

10 = urgência máxima
```

---

## 5.4 Categoria

Representa a classificação principal da notícia.

Categorias iniciais:

```text
resultados
regulacao
commodities
macroeconomia
empresa
tecnologia
outros
```

A lista poderá ser expandida futuramente.

---

## 5.5 Explicação

Resumo interpretativo curto destinado a justificar a classificação produzida.

Exemplo:

```text
Redução da produção da OPEP impacta diretamente empresas do setor de petróleo.
```

A explicação deverá conter apenas uma frase objetiva.

---

# 6. Provedor Escolhido

A implementação inicial utilizará exclusivamente OpenAI.

Motivações:

- simplicidade operacional;
- infraestrutura já existente;
- menor custo de manutenção;
- alinhamento com as fases anteriores.

---

# 7. Decisões Arquiteturais

## 7.1 Separação de Responsabilidades

A Fase 5 não decidirá relevância.

A responsabilidade da fase é exclusivamente enriquecer notícias já aprovadas.

---

## 7.2 Cache Obrigatório

As respostas deverão utilizar cache compartilhado com o restante do sistema.

Objetivos:

- reduzir custo;
- reduzir latência;
- evitar chamadas duplicadas.

---

## 7.3 Fallback Obrigatório

Em caso de:

- timeout;
- indisponibilidade da OpenAI;
- resposta inválida;
- erro de parsing;

o sistema deverá utilizar classificação heurística local.

O pipeline nunca deverá ser interrompido.

---

## 7.4 Saída Estruturada

A resposta da fase deverá ser convertida para uma estrutura padronizada.

Formato lógico:

```json
{
  "sentimento": "negativo",
  "impacto": "alto",
  "urgencia": 8,
  "categoria": "commodities",
  "explicacao": "Redução da produção da OPEP impacta diretamente o setor de petróleo."
}
```

---

## 7.5 Explicação Concisa

A explicação deverá ser curta e objetiva.

A Fase 5 não possui responsabilidade de gerar resumos completos da notícia.

---

# 8. Consequências

## Benefícios

- maior capacidade de priorização;
- melhor experiência de alertas;
- enriquecimento semântico consistente;
- melhor suporte a dashboards futuros.

## Custos

- aumento de latência para notícias aprovadas;
- dependência de LLM externa;
- necessidade de monitoramento de custos.

---

# 9. Critérios de Sucesso

A Fase 5 será considerada bem-sucedida quando:

- produzir metadados válidos para notícias aprovadas;
- manter alta taxa de respostas válidas;
- utilizar fallback apenas em situações excepcionais;
- permitir futura implementação da Fase 6 sem alterações estruturais.

---

# 10. Fora do Escopo

Não fazem parte desta RFC:

- resumo completo da notícia;
- geração de relatórios;
- recomendação de compra ou venda;
- personalização por usuário;
- múltiplos provedores LLM;
- análise fundamentalista;
- previsão de mercado.

---

# 11. Referências

- RFC-001 — Fase 1: Filtro Global de Relevância
- RFC-002 — Fase 2: Relacionamento com Tickers
- RFC-003 — Fase 3: Heurística Contextual
- RFC-004 — Fase 4: Classificação Binária Condicional via LLM

---

Fim do documento.