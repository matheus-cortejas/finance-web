# Guia do TCC — do corpus à avaliação das variantes da Fase 2

Guia operacional de ponta a ponta: preparar os ativos, gerar uma execução base,
montar a planilha de anotação, anotar, importar e medir as variantes
**A0–A4** da Fase 2 (associação notícia → ticker).

> **Convenção de shell.** Os exemplos usam `./venv/bin/python` (Linux/macOS).
> No Windows, troque por `.\venv\Scripts\python.exe`. No Docker, use
> `docker compose run --rm web python manage.py …`.

---

## 1. Objetivo

O trabalho do artigo relaciona notícias a tickers (Fase 2) com um **único**
cosseno global (bi-encoder) e limiar `θ = 0.35`, o que gera muitas associações
espúrias — empresas apenas do "mesmo setor" acabam marcadas como corretas.
Este TCC testa um conjunto **controlado** de variantes para reduzir isso sem
perder recall, e mede o custo de cada uma.

Perguntas de pesquisa (RQ):

| RQ | Pergunta | Variantes envolvidas |
|----|----------|----------------------|
| **RQ1** | Qual a eficiência/tempo da cascata? | A0–A4 (`tempo_medio_s`, `fase2_tempo_s`) |
| **RQ2** | Gating por setor melhora a precisão mantendo recall? | A1 vs A0 |
| **RQ3** | Guarda lexical / reranking superam o denso puro? | A2, A3 |
| **RQ4** | LLM local + escalonamento reduz custo? | A4 (`fase2_uso`) |
| **RQ5** | Qual o valor informacional dos alertas? | Fase 4/5 (anotação) |

---

## 2. Conceitos rápidos

**As fases do pipeline** (`core/intelligent_motor/`):

1. **Fase 1** — filtro global de relevância financeira (embedding × centroides).
2. **Fase 2** — associação notícia → ticker. *É o foco do TCC.*
3. **Fase 3** — score heurístico (11 pesos somados).
4. **Fase 4** — gate: aprovação/rejeição direta por score + faixa do LLM.
5. **Fase 5** — classificação rica (sentimento, impacto, categoria…) com LLM.
6. **Fase 6** — saída fora do escopo (o pipeline para na 5).

**Variantes da Fase 2:**

| Variante | Configuração | O que faz |
|----------|--------------|-----------|
| **A0** | `fase2.estrategia=similaridade` | Baseline: cosseno contra todos os ativos. |
| **A1** | `fase2.estrategia=similaridade_setor` | Restringe aos ativos do setor detectado na notícia. |
| **A2** | `fase2.estrategia=similaridade_setor_lexical` | A1 + guarda lexical (tickers citados por regex, com `peso_lexical`). |
| **A3** | `fase2.rerank.enabled=true` | Reranking dos `top_n` candidatos com cross-encoder. |
| **A4** | `fase2.llm.enabled=true` | LLM (local → nuvem) escolhe os tickers afetados. |

A3 e A4 são **pós-etapas**: podem ser combinadas com A0/A1/A2 (ex.: A2+A3+A4).
Toda falha é segura — se o cross-encoder não carregar ou o LLM não responder, o
resultado da similaridade é mantido e o fato fica registrado (ver §9).

**Como as cadeias "curinga" funcionam no A1/A2.** Ativos sem setor, com setor
`Outros`/`Não se aplica`, ou notícias cujo setor não foi detectado, **não
derrubam recall**: o A1 cai para o comportamento A0 nesses casos. Por isso a
setorização (§4) importa, mas nunca zera um resultado.

---

## 3. Pré-requisitos e setup

```bash
python -m venv venv
./venv/bin/python -m pip install -r requirements.txt

./venv/bin/python manage.py migrate
./venv/bin/python manage.py bootstrap        # ativos + feeds + coleta inicial
./venv/bin/python manage.py createsuperuser
./venv/bin/python manage.py runserver
```

O laboratório fica em `http://localhost:8000/lab/` (usuário **staff**).

### Device / GPU

- `EMBEDDING_DEVICE=cpu|cuda|auto` (o default da interface é `auto`).
- Com GPU: `cuda`; sem GPU, mantenha `cpu`.
- Em Docker com GPU: `docker compose -f compose.yaml -f compose.gpu.yaml up -d --build`.

### A3 — cross-encoder

Já incluso: `sentence-transformers` está no `requirements.txt`. O modelo padrão
(`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`) é baixado sob demanda na primeira
execução do A3 (precisa de rede uma vez; depois fica em cache local).

### A4 — LLM local (opcional, requer GPU para boa latência)

O provedor local é qualquer endpoint **OpenAI-compatível**. Com
[Ollama](https://ollama.com):

```bash
ollama pull llama3.1:8b
ollama serve          # expõe http://localhost:11434/v1
```

Para escalonar para a nuvem quando o local falhar, defina a chave:

```bash
# .env
OPENAI_API_KEY=sk-...
```

Sem GPU e sem `OPENAI_API_KEY`, o A4 continua funcionando no modo seguro
(mantém a similaridade) — só não produz ganho.

> Em Docker, o container precisa alcançar o Ollama do host. Use
> `base_url: http://host.docker.internal:11434/v1`.

---

## 4. Passo 1 — Setorizar os ativos

O A1/A2 dependem de `Ativo.setor`. A classificação é por palavras-chave
(`core/intelligent_motor/setores.py`), alimentada pelo nome e pela
`descricao_embedding` (fallback: `ativos_mapeamento.json`).

```bash
# Preenche só os ativos sem setor e exporta o mapeamento para revisão
./venv/bin/python manage.py seed_setores --export exports/setores_ativos.json
```

**Revise** `exports/setores_ativos.json`. O classificador deixa uma fração em
`Outros` (no corpus local, ~20–25%). Corrija os casos óbvios e reaplique:

```bash
# Aplica os overrides revisados (sobrescreve só os tickers do JSON)
./venv/bin/python manage.py seed_setores --from-json exports/setores_ativos.json
```

Flags úteis:

| Flag | Efeito |
|------|--------|
| `--from-json PATH` | Aplica um `{ticker: setor}` revisado como override. |
| `--export PATH` | Grava o mapeamento calculado. |
| `--force` | Reprocessa mesmo os ativos já preenchidos. |
| `--source b3\|sp500` | Restringe a um subconjunto. |

Taxonomia usada (`SETORES_ANOTACAO`):

```
Petróleo e Gás · Mineração e Siderurgia · Químicos e Petroquímica ·
Energia Elétrica · Saneamento · Bancos · Serviços Financeiros ·
Construção e Materiais · Bens de Capital · Transporte e Logística ·
Consumo Cíclico · Alimentos e Bebidas · Comércio e Varejo ·
Saúde e Farmacêutico · Tecnologia e Software · Telecomunicações ·
Papel e Celulose · Agropecuária · Imobiliário · Educação · Outros ·
Macro/Mercado · Não se aplica
```

> `Macro/Mercado` e `Não se aplica` são rótulos de **notícia** (usados na
> anotação), não de ativo.

---

## 5. Passo 2 — Criar a execução base (no `/lab/`)

A execução base serve de **fonte dos candidatos** pré-preenchidos na planilha.
Regra anti-retrabalho: queremos candidatos **generosos** (união regex ∪ top-N do
Fase 2), para poder medir qualquer variante depois sem reanotar.

No painel `/lab/`, crie uma execução com:

| Campo | Valor | Por quê |
|-------|-------|---------|
| Modelo | `paraphrase-multilingual-MiniLM-L12-v2` (ou o do artigo) | Mesmo embedding de tudo. |
| Limite | vazio | Cobrir o corpus inteiro. |
| `stop_after` | `5` | Precisa de Fase 2 (candidatos) + Fases 3/4/5 (score/alerta/campos). |
| `usar_llm` | desmarcado | Base roda com fallback heurístico, sem exigir `OPENAI_API_KEY`. |
| Fase 2 · θ similaridade | **0.25** | Limiar baixo → mais candidatos pré-preenchidos. |
| Fase 2 · top-K | **15** | Generoso, mas limitado. |
| Fase 2 · estratégia | A0 | A base não precisa de gating; o objetivo aqui é juntar candidatos. |

Os candidatos na planilha serão
`tickers_encontrados` (regex) **∪** `tickers_relacionados` (Fase 2 do run). Com
`θ=0.25` e `top_k=15`, essa união já cobre as respostas de A0–A4.

Processe o run (worker):

```bash
./venv/bin/python manage.py run_experiments --once
# ou, para um run específico:
./venv/bin/python manage.py run_experiments --run-id 3
```

Ao terminar, os artefatos saem em `exports/lab/run-3/`.

---

## 6. Passo 3 — Gerar a amostra de anotação

```bash
./venv/bin/python manage.py build_annotation_sample --run-id 3 --output exports/anotacao
```

Saída em `exports/anotacao/anotacao/`:

- **`anotacao.csv`** — uma linha por notícia, todas as fases juntas.
- **`diagnostico.csv`** — o que cada fase "pensou" (para conferir depois).
- **`LEIA-ME.txt`** — a legenda completa das colunas e a taxonomia.

**Estratificação** (padrão, 500 linhas):

| Faixa | Nº padrão | Flag |
|-------|-----------|------|
| Descartadas na Fase 1 | 130 | `--n-descartadas` |
| Score heurístico ≤ 2 | 110 | `--n-baixo` |
| Score 3–6 (zona cinza) | 150 | `--n-cinza` |
| Score ≥ 7 | 110 | `--n-alto` |
| Mínimo com ticker explícito | 100 | `--min-explicito` |

Outras flags: `--seed` (42), `--content-chars` (1500), `--name`, `--output`.

> A amostra é **estratificada por score**, não aleatória simples: assim a
> anotação cobre os casos difíceis (fronteira) que separam as variantes.

Verifique o mix antes de anotar:

```bash
./venv/bin/python -c "import csv;print(len(list(csv.DictReader(open('exports/anotacao/anotacao/anotacao.csv',encoding='utf-8-sig')))),'linhas')"
```

---

## 7. Passo 4 — Anotar (`anotacao.csv`)

Abra em planilha (Excel/LibreOffice/Google Sheets). **Uma linha por notícia**;
a chave é `noticia_id`. Colunas de anotação:

| Coluna | Alvo | Valores |
|--------|------|---------|
| `rel_financeira` | Fase 1 | `0`/`1` |
| `rel_alerta` | Fase 4 | `0`/`1` |
| `setor` | setorização | taxonomia de §4 (use `Macro/Mercado` para notícia geral) |
| `setor_secundario` | setorização | opcional |
| `candidatos` | Fase 2 | **já pré-preenchido** — só referência, não edite |
| `tickers_corretos` | Fase 2 | subconjunto de `candidatos`, separado por `\|`; `NENHUM` se nenhum |
| `tickers_faltantes` | Fase 2 | tickers que faltaram (opcional, recall) |
| `sentimento` | Fase 5 | `positivo` / `neutro` / `negativo` |
| `impacto` | Fase 5 | `baixo` / `medio` / `alto` |
| `urgencia` | Fase 5 | `alta` / `media` / `baixa` (aceita 0–10; ≥7→alta, ≥4→média) |
| `categoria` | Fase 5 | `resultados` / `regulacao` / `commodities` / `macroeconomia` / `empresa` / `tecnologia` / `outros` |
| `confianca` | — | `1` (baixa) a `3` (alta) |
| `observacao` | — | livre |
| `anotador` | — | seu nome/ID (útil se um 2º anotador entrar depois) |

**Regra de ouro dos tickers.** Marque **correto** só quando a notícia
**menciona** a empresa ou a **afeta materialmente** de forma não especulativa.
"Mesmo setor" **não** basta.

> Exemplo: notícia da PETR4 → `PETR4` correto; `BRKM5`, `PRIO3`, `DOW`, `AVY`
> incorretos (mesmo setor / correlação apenas).

**Sinais de "anotei, nenhum correto".**

- Colunas de tickers: escreva `NENHUM` (aceitos também `-`, `n/a`, `na`, `vazio`, `sem`).
- Campos vazios = **não anotado** → a linha não entra na métrica daquela fase.
- Isso importa para a Fase 2: a métrica só considera linhas com
  `tickers_corretos` **ou** `tickers_faltantes` preenchidos (inclusive `NENHUM`).

**Dicas de produtividade.** Ordene por `score`/`fonte`, filtre por `candidatos`
não vazio, e mantenha `confianca=1` para linhas duvidosas (elas podem ganhar
uma segunda olhada sem viesar o restante).

---

## 8. Passo 5 — Importar a anotação

O comando recebe o CSV como **argumento posicional**:

```bash
# 1) confira antes de gravar
./venv/bin/python manage.py import_labels exports/anotacao/anotacao/anotacao.csv --dry-run

# 2) importe de fato
./venv/bin/python manage.py import_labels exports/anotacao/anotacao/anotacao.csv --anotador "matheus"
```

Saída: `criados=N atualizados=N ignorados=N inválidos=N`.

- **ignorados** = linha sem nenhum campo preenchido.
- **inválidos** = `noticia_id` ausente/não numérico ou inexistente no banco.
- Reimportar é seguro: usa `update_or_create` por `noticia_id`.
- `--anotador` é o default para linhas sem a coluna preenchida.

---

## 9. Passo 6 — Rodar as variantes (A0–A4) e a varredura

Cada variante é uma `ExperimentRun` nova. Crie no `/lab/` (a UI é a forma
suportada de criar execuções) e processe com o worker.

**Cada execução** deve usar o **mesmo** modelo de embeddings e o mesmo recorte
de notícias da base — só mude o bloco da Fase 2. Sugestão de grade:

| Run | `estrategia` | `θ_sim` | `top_k` | `rerank` | `llm` |
|-----|--------------|---------|---------|----------|-------|
| A0 | `similaridade` | 0,35 | — | — | — |
| A1 | `similaridade_setor` | 0,35 | — | — | — |
| A2 | `similaridade_setor_lexical` | 0,35 | — | — | — |
| A3 | A2 | 0,35 | — | ✅ | — |
| A4 | A2 | 0,35 | — | — | ✅ |

**Varredura de limiar/top-K:** repita A0–A2 com `θ_sim ∈ {0,25; 0,30; 0,35; 0,40; 0,45}`
e `top_k ∈ {5, 10, 20}`. Os gráficos de varredura (`score_heuristico`,
`relevancia_global`, `fase1_sweep`) e o comparador já cobrem parte disso.

> A3/A4 já recebem `top_n` próprio (quantos candidatos entram no rerank/LLM).
> Combine A3 com `θ` baixo + `top_n` alto para dar margem ao cross-encoder.

Para combinar várias etapas numa só run, marque simultaneamente
`estrategia=A2` + `rerank.enabled` + `llm.enabled`.

**A4 — duas modalidades.** `provider=local` usa o Ollama e só escala para a
nuvem se falhar; `provider=openai` vai direto para a nuvem (exige
`OPENAI_API_KEY`). Rode as duas para medir o custo (RQ4).

---

## 10. Passo 7 — Métricas e gráficos

```bash
./venv/bin/python manage.py compute_metrics --run-id 3
./venv/bin/python manage.py compute_metrics --all --json > exports/metricas.json
```

Resultado fica em `ExperimentRun.metricas`. Estrutura relevante:

```jsonc
{
  "cobertura": 0.98, "labeled_total": 500, "erros": 0, "tempo_medio_s": 0.42,
  "fase1": { "metricas": { "precision":…, "recall":…, "f1":… }, "avaliadas": 480 },
  "fase2": {                       // métricas por par (conjunto de tickers)
    "metricas": {
      "itens": 500, "tp": …, "fp": …, "fn": …,
      "precision": 0.71, "recall": 0.64, "f1": 0.67,
      "exatos": 312, "acuracia_conjunto": 0.624
    },
    "avaliadas": 500
  },
  "fase4": { "metricas": { … }, "avaliadas": 500 },
  "score_heuristico": { "best": { "threshold": 7, "f1": … } },
  "fase1_sweep":      { "best": { "threshold": 0.55, "f1": … } },
  "fase2_uso": {                  // o que A3/A4 realmente fizeram
    "estrategia:similaridade_setor_lexical": 498,
    "rerank:aplicado": 495, "rerank:indisponivel": 3,
    "llm:local": 470, "llm:openai": 20, "llm:fallback": 8
  }
}
```

Como ler:

- **Fase 2** usa `pair_metrics_sets`: TP/FP/FN somados **por par**. O
  "verdadeiro" é `tickers_corretos ∪ tickers_faltantes` — por isso é importante
  preencher `tickers_faltantes` quando o candidato nem apareceu na lista.
- `acuracia_conjunto` = fração de notícias em que o conjunto previsto é
  **exatamente** o verdadeiro (métrica dura).
- `fase2_uso` responde RQ1/RQ4: quantas linhas usaram rerank/LLM, qual provedor
  e quantas caíram em fallback.
- `labeled_total`/`avaliadas` mostram cobertura da anotação (o que ficou de fora).

**Gráficos** (gerados automaticamente ao fim do worker; botão "Regenerar
gráficos" ou comando):

```bash
./venv/bin/python manage.py generate_run_charts --run-id 3
```

Vão para `exports/lab/run-3/`: os 4 gráficos do artigo, varreduras, matrizes de
confusão, `resumo.txt`, `metricas.csv` e `amostra_fase4.csv`. O `resumo.txt`
agora lista também a estratégia e os modos A3/A4 ativos.

Compare execuções em `/lab/compare/` (θ rel. / θ sim. lado a lado).

---

## 11. Referência de configuração

`config.yaml` (bloco `fase2`) — defaults do sistema; o `/lab/` grava em
`ExperimentRun.config["overrides"]` só o que difere, e `config["efetivo"]` tem o
resultado final.

```yaml
fase2:
  threshold_similaridade: 0.35     # θ do cosseno (A0 base do artigo)
  estrategia: similaridade         # A0 | similaridade_setor | similaridade_setor_lexical
  top_k: null                      # limite de tickers por notícia
  peso_lexical: 0.0                # bônus p/ ticker citado (A2)

  rerank:                          # A3
    enabled: false
    modelo: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
    top_n: 20
    threshold: 0.5
    manter_minimo: 1               # se nada passar, mantém os N melhores

  llm:                             # A4
    enabled: false
    provider: local                # local | openai
    model: llama3.1:8b             # ex.: gpt-4o-mini quando provider=openai
    base_url: http://localhost:11434/v1
    timeout_seconds: 30
    max_tokens: 300
    temperature: 0.0
    top_n: 20
    escalar_para:                  # usado se o local falhar
      provider: openai
      model: gpt-4o-mini
```

Validações (o `/lab/` recusa antes de criar o run): `θ` e thresholds em `[0,1]`;
`top_k`/`top_n` em `[1,100]`; `provider ∈ {local, openai}`; se `llm.enabled`,
o `model` não pode ser vazio.

Variáveis de ambiente principais:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `EMBEDDING_DEVICE` | `cpu` | `cpu`, `cuda` ou `auto`. |
| `EMBEDDING_MODELS` | `paraphrase-multilingual-MiniLM-L12-v2` | Sugestões na UI. |
| `LAB_MODELS_DIR` | `core/intelligent_motor/models` | Modelos locais. |
| `OPENAI_API_KEY` | — | Habilita nuvem (Fases 4/5 e escalonamento A4). |
| `EXPERIMENT_CACHE_ENABLED` | `0` | Cache da Fase 1. |
| `LAB_CHARTS_DIR` | `exports/lab` | Artefatos por execução. |

---

## 12. Ordem recomendada (resumo)

```bash
# 0. setup
./venv/bin/python manage.py migrate
./venv/bin/python manage.py bootstrap

# 1. setores (revisar e reaplicar)
./venv/bin/python manage.py seed_setores --export exports/setores_ativos.json
#   ... revise o JSON ...
./venv/bin/python manage.py seed_setores --from-json exports/setores_ativos.json

# 2. run base no /lab/ (stop_after=5, θ=0.25, top_k=15) e processar
./venv/bin/python manage.py run_experiments --once

# 3. amostra de anotação
./venv/bin/python manage.py build_annotation_sample --run-id 3

# 4. anotar exports/anotacao/anotacao/anotacao.csv   (o gargalo)

# 5. importar
./venv/bin/python manage.py import_labels exports/anotacao/anotacao/anotacao.csv --dry-run
./venv/bin/python manage.py import_labels exports/anotacao/anotacao/anotacao.csv --anotador "matheus"

# 6. rodar as variantes no /lab/ (A0–A4) e processar cada uma
./venv/bin/python manage.py run_experiments --once

# 7. métricas + gráficos por execução
./venv/bin/python manage.py compute_metrics --all
./venv/bin/python manage.py generate_run_charts --run-id <id>
```

---

## 13. Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| `import_labels` reclama de argumento | usou `--csv` | passe o caminho como **posicional** (§8). |
| Fase 2 `avaliadas: 0` | nenhuma linha com tickers anotados | preencha `tickers_corretos` **ou** `tickers_faltantes` (use `NENHUM`). |
| `fase2_uso` sem `rerank:*` | A3 desmarcado no run | marque `rerank.enabled` (§9). |
| `rerank: indisponivel` | modelo não carregou / sem rede 1ª vez | verifique `sentence-transformers` e baixe o modelo. |
| `llm: fallback` em massa | Ollama fora do ar / URL errada | `ollama serve`; em Docker use `host.docker.internal`. |
| A1 não muda nada vs A0 | setores em `Outros` ou notícias sem setor detectado | revise §4; curingas caem para A0 por design. |
| Run base não tem Fase 2 | `stop_after < 2` | crie com `stop_after=5`. |
| Muitos `inválidos` no import | IDs fora do banco / CSV do export antigo | confira `noticia_id` e rode o `build_annotation_sample` do run correto. |

---

## 14. Escopo e trabalho futuro

- **Sentimento global**, não *entity-aware* por ticker (alinha com a Fase 5).
- **Sem kappa de Cohen** (anotador único); o campo `anotador` fica pronto para
  um 2º anotador e cálculo de concordância depois.
- **Fase 6** fora do pipeline (para na 5).
- A varredura A0–A4 é manual pelo `/lab/`; um comando `run_sweep` que cria as
  execuções da grade automaticamente é um ganho natural (ver §9).

---

## 15. Testes

```bash
./venv/bin/python manage.py test core pipeline_lab -v 2
```

Cobrem coleta, exportação, criação/métricas de execuções, store de embeddings,
o pipeline sem LLM, o catálogo de modelos, a UI do `/lab/` e agora **A3/A4**
(seleção por limiar, parser do LLM, escalonamento e integração com
`relacionar_tickers`). Nenhum teste carrega modelo real nem acessa a rede.
