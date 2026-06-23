"""
export_metrics.py

Script de apoio para análise das métricas coletadas pelo
pipeline_orchestrator instrumentado (pipeline_metrics.py).

Uso típico (rodar a partir da raiz do projeto Django, com o
ambiente virtual ativado):

    python export_metrics.py

Saídas geradas (em ./analise_metricas/):
    - metricas.csv              -> todas as métricas, em formato tabular
    - resumo.txt                -> resumo textual (contagens, médias, etc.)
    - fig_score_heuristico.png  -> histograma do score com os cortes de corte
    - fig_decisao_pipeline.png  -> funil de decisão (descarte/bypass/LLM)
    - fig_tickers_origem.png    -> cobertura B3 vs S&P500
    - fig_tempo_por_fase.png    -> tempo médio (s) por fase
    - amostra_fase4.csv         -> amostra para anotação manual da Fase 4
                                    (com coluna 'relevancia_manual' vazia)

Este script depende apenas de pandas e matplotlib (não depende do Django),
então pode ser rodado em qualquer máquina, bastando copiar o arquivo
pipeline_metrics.jsonl gerado durante a coleta.
"""

import json
import os
import sys

import pandas as pd
import matplotlib.pyplot as plt


METRICS_PATH = os.environ.get("PIPELINE_METRICS_PATH", "pipeline_metrics.jsonl")
OUTPUT_DIR = "analise_metricas"


def carregar_dataframe(path: str) -> pd.DataFrame:
    registros = []
    if not os.path.exists(path):
        print(f"Arquivo de métricas não encontrado: {path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            try:
                registros.append(json.loads(linha))
            except json.JSONDecodeError:
                continue

    df = pd.DataFrame(registros)
    if "publicado_em" in df.columns:
        df["publicado_em"] = pd.to_datetime(df["publicado_em"], errors="coerce")
    if "registrado_em" in df.columns:
        df["registrado_em"] = pd.to_datetime(df["registrado_em"], errors="coerce")
    return df


def gerar_resumo(df: pd.DataFrame, path: str) -> None:
    n_total = len(df)
    n_descartadas_f1 = (df.get("fase1_aprovada") == False).sum()  # noqa: E712
    n_avaliadas_f4 = (df.get("fase1_aprovada") == True).sum()  # noqa: E712
    n_relevantes = (df.get("relevancia_binaria") == 1).sum()

    if "provider_fase4" in df.columns:
        contagem_provider = df["provider_fase4"].value_counts(dropna=False)
    else:
        contagem_provider = pd.Series(dtype=int)

    periodo_inicio = df["publicado_em"].min() if "publicado_em" in df.columns else None
    periodo_fim = df["publicado_em"].max() if "publicado_em" in df.columns else None

    linhas = []
    linhas.append("=== Resumo da coleta - Motor Inteligente ===\n")
    linhas.append(f"Total de notícias processadas: {n_total}")
    linhas.append(f"Período coberto: {periodo_inicio} até {periodo_fim}")
    linhas.append("")
    linhas.append(f"Descartadas na Fase 1 (relevância global): {n_descartadas_f1} "
                   f"({(n_descartadas_f1 / n_total * 100):.1f}%)" if n_total else "")
    linhas.append(f"Avançaram para Fase 2-4: {n_avaliadas_f4}")
    linhas.append(f"Classificadas como relevantes (Fase 4 = 1): {n_relevantes}")
    linhas.append("")
    linhas.append("Decisão na Fase 4 por provider (bypass vs openai):")
    for nome, qtd in contagem_provider.items():
        linhas.append(f"  - {nome}: {qtd}")
    linhas.append("")

    if "score_heuristico" in df.columns:
        desc = df["score_heuristico"].describe()
        linhas.append("Estatísticas do score_heuristico:")
        linhas.append(str(desc))
        linhas.append("")

    if {"n_tickers_b3", "n_tickers_sp500", "n_tickers_outros"}.issubset(df.columns):
        linhas.append("Cobertura média de tickers relacionados por notícia:")
        linhas.append(f"  - B3:     {df['n_tickers_b3'].mean():.2f}")
        linhas.append(f"  - S&P500: {df['n_tickers_sp500'].mean():.2f}")
        linhas.append(f"  - Outros: {df['n_tickers_outros'].mean():.2f}")
        linhas.append("")

    tempo_cols = [c for c in df.columns if c.endswith("_tempo_s")]
    if tempo_cols:
        linhas.append("Tempo médio por fase (segundos):")
        for c in tempo_cols:
            linhas.append(f"  - {c}: {df[c].mean():.4f}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(str(l) for l in linhas))

    print("\n".join(str(l) for l in linhas))


def fig_score_heuristico(df: pd.DataFrame, path: str,
                          corte_rejeicao: int = 2, corte_aprovacao: int = 7) -> None:
    if "score_heuristico" not in df.columns:
        return
    plt.figure(figsize=(7, 4))
    df["score_heuristico"].dropna().plot(kind="hist", bins=range(-5, 20), edgecolor="black")
    plt.axvline(corte_rejeicao + 0.5, color="red", linestyle="--",
                label=f"Corte rejeição direta (≤{corte_rejeicao})")
    plt.axvline(corte_aprovacao - 0.5, color="green", linestyle="--",
                label=f"Corte aprovação direta (≥{corte_aprovacao})")
    plt.title("Distribuição do score heurístico (Fase 3)")
    plt.xlabel("score_heuristico")
    plt.ylabel("nº de notícias")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def fig_decisao_pipeline(df: pd.DataFrame, path: str) -> None:
    n_total = len(df)
    n_descartadas_f1 = (df.get("fase1_aprovada") == False).sum()  # noqa: E712

    avancou = df[df.get("fase1_aprovada") == True]  # noqa: E712
    n_bypass = (avancou.get("provider_fase4") == "bypass").sum()
    n_llm = (avancou.get("provider_fase4") == "openai").sum()
    n_irrelevante = (avancou.get("relevancia_binaria") == 0).sum()
    n_relevante = (avancou.get("relevancia_binaria") == 1).sum()

    categorias = ["Descartadas\n(Fase 1)", "Bypass\n(Fase 3→4)", "LLM\n(Fase 4)"]
    valores = [n_descartadas_f1, n_bypass, n_llm]

    plt.figure(figsize=(7, 4))
    plt.bar(categorias, valores, color=["#888888", "#1f5cff", "#ff7a18"])
    for i, v in enumerate(valores):
        plt.text(i, v, str(int(v)), ha="center", va="bottom")
    plt.title(f"Funil de decisão do pipeline (N={n_total})\n"
              f"Relevantes: {n_relevante} | Irrelevantes (Fase4): {n_irrelevante}")
    plt.ylabel("nº de notícias")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def fig_tickers_origem(df: pd.DataFrame, path: str) -> None:
    cols = ["n_tickers_b3", "n_tickers_sp500", "n_tickers_outros"]
    if not set(cols).issubset(df.columns):
        return
    totais = df[cols].sum()
    plt.figure(figsize=(5, 5))
    plt.pie(totais, labels=["B3", "S&P 500", "Outros/Não identificado"],
            autopct="%1.1f%%", startangle=90)
    plt.title("Distribuição de tickers relacionados por origem (Fase 2)")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def fig_tempo_por_fase(df: pd.DataFrame, path: str) -> None:
    tempo_cols = [c for c in df.columns if c.endswith("_tempo_s")]
    if not tempo_cols:
        return
    medias = df[tempo_cols].mean().sort_values(ascending=False)
    plt.figure(figsize=(7, 4))
    medias.plot(kind="bar", color="#1f5cff")
    plt.title("Tempo médio de processamento por fase")
    plt.ylabel("segundos")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def gerar_amostra_fase4(df: pd.DataFrame, path: str,
                         n_zona_cinzenta: int = 80,
                         n_bypass: int = 30,
                         random_state: int = 42) -> None:
    """
    Gera uma amostra para anotação manual da Fase 4, priorizando notícias
    na "zona cinzenta" do score heurístico (3-6, onde a LLM é chamada),
    com uma fração menor de casos de bypass (aprovação/rejeição direta)
    para auditoria das regras de corte.
    """
    avancou = df[df.get("fase1_aprovada") == True].copy()  # noqa: E712
    if avancou.empty or "score_heuristico" not in avancou.columns:
        print("Sem dados suficientes para gerar amostra da Fase 4.")
        return

    zona_cinzenta = avancou[(avancou["score_heuristico"] >= 3) &
                             (avancou["score_heuristico"] <= 6)]
    bypass = avancou[(avancou["score_heuristico"] < 3) |
                      (avancou["score_heuristico"] > 6)]

    amostra_zc = zona_cinzenta.sample(
        n=min(n_zona_cinzenta, len(zona_cinzenta)), random_state=random_state
    )
    amostra_bp = bypass.sample(
        n=min(n_bypass, len(bypass)), random_state=random_state
    )

    amostra = pd.concat([amostra_zc, amostra_bp], ignore_index=True)

    colunas_uteis = [c for c in [
        "noticia_id", "link", "publicado_em", "score_heuristico",
        "criterios_ativados", "relevancia_global", "provider_fase4",
        "relevancia_binaria", "confianca_fase4"
    ] if c in amostra.columns]

    amostra = amostra[colunas_uteis]
    amostra["relevancia_manual"] = ""   # 0 ou 1, a preencher manualmente
    amostra["observacoes"] = ""

    amostra.to_csv(path, index=False, encoding="utf-8")
    print(f"Amostra para anotação manual salva em: {path} ({len(amostra)} notícias)")


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = carregar_dataframe(METRICS_PATH)
    print(f"Carregadas {len(df)} notícias de {METRICS_PATH}")

    df.to_csv(os.path.join(OUTPUT_DIR, "metricas.csv"), index=False, encoding="utf-8")

    gerar_resumo(df, os.path.join(OUTPUT_DIR, "resumo.txt"))
    fig_score_heuristico(df, os.path.join(OUTPUT_DIR, "fig_score_heuristico.png"))
    fig_decisao_pipeline(df, os.path.join(OUTPUT_DIR, "fig_decisao_pipeline.png"))
    fig_tickers_origem(df, os.path.join(OUTPUT_DIR, "fig_tickers_origem.png"))
    fig_tempo_por_fase(df, os.path.join(OUTPUT_DIR, "fig_tempo_por_fase.png"))
    gerar_amostra_fase4(df, os.path.join(OUTPUT_DIR, "amostra_fase4.csv"))

    print(f"\nArquivos gerados em ./{OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
