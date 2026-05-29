# Proposta de Evolução do Projeto — Sistema Inteligente de Monitoramento Financeiro

## Visão Geral

O projeto atual consiste em uma plataforma de monitoramento financeiro que coleta notícias através de feeds RSS, identifica possíveis relações com ativos da carteira do usuário e utiliza um modelo de linguagem (LLM) para determinar relevância e gerar resumos automáticos.

### Fluxo Atual

1. Coleta de notícias via RSS
2. Identificação de ticker/nome relacionado à carteira
3. Avaliação de relevância utilizando LLM
4. Geração de resumo automático
5. Exibição em dashboard
6. Envio de alertas ao usuário

Embora funcional, o sistema atualmente atua principalmente como um agregador inteligente de notícias. O objetivo desta evolução é transformá-lo em um Sistema Inteligente de Apoio à Decisão Financeira, adicionando camadas de inferência, personalização e priorização automatizada.

---

# Objetivo da Evolução

Transformar o sistema em uma plataforma inteligente capaz de:

* Interpretar semanticamente notícias financeiras
* Personalizar alertas conforme perfil do investidor
* Classificar impacto e risco das notícias
* Priorizar eventos relevantes automaticamente
* Adaptar comportamento com base em interações do usuário
* Reduzir ruído informacional

---

# Nova Proposta de Arquitetura Inteligente

## Pipeline Geral

```text
RSS -> Pré-processamento -> Match com carteira ->
LLM Classifier -> Motor de Relevância ->
Motor de Priorização -> Dashboard/Alertas
```

---

# Componentes Inteligentes Propostos

# 1. Perfil Inteligente do Usuário

## Objetivo

Adicionar contexto ao processo de decisão do sistema.

## Dados do Perfil

* Tickers acompanhados
* Setores de interesse
* Perfil de risco
* Horizonte de investimento
* Sensibilidade a notícias negativas
* Frequência desejada de alertas

## Exemplo

Usuário conservador:

* notícias negativas recebem peso maior
* notícias especulativas recebem menor prioridade

Usuário agressivo:

* notícias de volatilidade recebem maior destaque

---

# 2. Classificação Estruturada de Notícias

## Objetivo

Transformar a saída da LLM em dados estruturados que possam ser processados pelo sistema.

## Exemplo de Resposta Esperada

```json
{
  "relevancia": 0.91,
  "sentimento": "negativo",
  "impacto": "alto",
  "urgencia": 8,
  "setor": "tecnologia",
  "tickers_relacionados": ["AAPL", "MSFT"],
  "tipo_evento": "resultado_trimestral"
}
```

## Benefícios

* Permite tomada de decisão automatizada
* Facilita ranking de notícias
* Permite filtros avançados
* Possibilita análises futuras

---

# 3. Motor de Relevância

## Objetivo

Criar uma lógica híbrida entre IA e heurísticas.

## Critérios de Pontuação

| Critério                     | Peso |
| ---------------------------- | ---- |
| Afeta ativo da carteira      | +5   |
| Impacto alto                 | +4   |
| Sentimento negativo          | +3   |
| Fonte confiável              | +2   |
| Alta urgência                | +2   |
| Setor prioritário do usuário | +3   |

## Fórmula Conceitual

```text
score_final =
impacto +
urgencia +
afinidade_usuario +
peso_carteira +
confiabilidade_fonte
```

## Resultado

O sistema deixa de apenas resumir notícias e passa a priorizar automaticamente eventos relevantes.

---

# 4. Sistema de Priorização Inteligente

## Objetivo

Reduzir excesso de notificações e destacar apenas eventos importantes.

## Categorias de Prioridade

* Crítica
* Alta
* Média
* Baixa

## Regras Exemplos

* Impacto alto + ativo em carteira -> alerta imediato
* Impacto baixo + setor irrelevante -> apenas dashboard
* Notícias duplicadas -> agrupamento automático

---

# 5. Memória e Aprendizado de Preferências

## Objetivo

Adaptar o sistema ao comportamento do usuário.

## Métricas Observadas

* Notícias abertas
* Notícias ignoradas
* Tempo de leitura
* Tipos de notícia mais acessados

## Exemplos

Se o usuário:

* ignora frequentemente notícias sobre petróleo
* abre constantemente notícias de tecnologia

O sistema ajusta automaticamente os pesos de relevância.

## Implementação Inicial

Não é necessário Machine Learning complexo.
Pode ser feito com:

* histórico simples
* pesos heurísticos
* estatísticas de interação

---

# 6. Classificação de Sentimento Financeiro

## Objetivo

Avaliar impacto emocional/econômico das notícias.

## Categorias

* Muito positivo
* Positivo
* Neutro
* Negativo
* Muito negativo

## Aplicações

* Alertas críticos
* Visualizações no dashboard
* Indicadores de risco

---

# 7. Dashboard Inteligente

## Funcionalidades Futuras

* Ranking de notícias mais relevantes
* Heatmap de sentimento
* Distribuição por setor
* Linha temporal de impacto
* Indicadores de risco da carteira

---

# Possível Estrutura Técnica

## Backend

* Python
* API REST
* Serviço de ingestão RSS
* Serviço de classificação IA

## IA

* OpenAI API
* Classificação estruturada
* Prompt engineering
* JSON output

## Banco de Dados

* PostgreSQL
* Histórico de notícias
* Perfis de usuário
* Logs de interação

## Frontend

* Dashboard web
* Sistema de alertas
* Feed personalizado

---

# Diferencial Acadêmico

A proposta deixa de ser apenas um sistema de resumo automático e passa a atuar como:

## Sistema Inteligente de Apoio à Decisão

Características inteligentes:

* inferência contextual
* classificação semântica
* personalização
* priorização automática
* adaptação baseada em comportamento
* apoio à tomada de decisão

---

# Possíveis Títulos para o Artigo

## Opção 1

Sistema Inteligente de Monitoramento Financeiro Baseado em Modelos de Linguagem e Perfil do Investidor

## Opção 2

Uso de Modelos de Linguagem na Priorização Inteligente de Notícias Financeiras

## Opção 3

Sistema Inteligente de Apoio à Decisão Financeira Utilizando NLP e Personalização de Alertas

---

# Escopo Realista para Entrega

## Essencial

* Perfil do usuário
* Score de relevância
* Classificação estruturada
* Ranking/priorização

## Opcional

* Aprendizado de preferências
* Dashboard avançado
* Estatísticas de uso

## Não Prioritário

* Fine-tuning
* Multiagentes complexos
* MCP completo
* Treinamento de modelos próprios

---

# Resultado Esperado

Ao final da evolução, o sistema deverá ser capaz de:

* coletar notícias automaticamente
* interpretar conteúdo semanticamente
* classificar impacto financeiro
* adaptar-se ao perfil do investidor
* priorizar eventos relevantes
* reduzir sobrecarga informacional
* apoiar tomada de decisão financeira

Isso transforma o projeto em um Sistema