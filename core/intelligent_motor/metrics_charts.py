"""metrics_charts.py

Geração dos gráficos do artigo (ENIAC/PSI) a partir do arquivo de métricas
``pipeline_metrics.jsonl`` e das métricas já calculadas por execução
(``ExperimentRun.metricas``).

Diferente de ``export_metrics.py`` (script autônomo, sem Django), este módulo
é pensado para ser chamado pelo próprio sistema, filtrando as linhas de UMA
execução (``run_id``) e usando os limiares/pesos efetivos daquela execução
para desenhar as linhas de corte.

Depende de ``pandas`` e ``matplotlib`` (backend Agg, sem display).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from core.intelligent_motor.chart_manifest import (  # noqa: E402
    ALL_FILES,
    CHART_FILES,
    DATA_FILES,
    FILE_LABELS,
)


# ---------------------------------------------------------------------------
# Carregamento
# ---------------------------------------------------------------------------

def load_metrics(metrics_path: str | Path, run_id: Optional[int] = None) -> pd.DataFrame:
    """Lê o JSONL e devolve um DataFrame (opcionalmente filtrado por run_id)."""
    registros: list[dict] = []
    path = Path(metrics_path)
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    registro = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if run_id is not None and registro.get("run_id") != run_id:
                    continue
                registros.append(registro)

    df = pd.DataFrame(registros)
    for coluna in ("publicado_em", "registrado_em"):
        if coluna in df.columns:
            df[coluna] = pd.to_datetime(df[coluna], errors="coerce")
    return df


def _cortes_fase4(parametros: Optional[dict]) -> tuple[int, int, int, int]:
    fase4 = (parametros or {}).get("fase4") or {}
    faixa = fase4.get("faixa_llm") or {}
    return (
        int(fase4.get("score_rejeicao_direta", 2)),
        int(faixa.get("minimo", 3)),
        int(faixa.get("maximo", 6)),
        int(fase4.get("score_aprovacao_direta", 7)),
    )


# ---------------------------------------------------------------------------
# Figuras do artigo
# ---------------------------------------------------------------------------

def fig_score_heuristico(
    df: pd.DataFrame,
    path: str | Path,
    *,
    parametros: Optional[dict] = None,
) -> bool:
    if "score_heuristico" not in df.columns:
        return False
    scores = df["score_heuristico"].dropna()
    if scores.empty:
        return False

    rejeicao, llm_min, llm_max, aprovacao = _cortes_fase4(parametros)
    lo = int(min(-1, scores.min()))
    hi = int(max(1, scores.max()))
    bins = range(lo, hi + 2)

    fig, ax = plt.subplots(figsize=(7, 4))
    scores.plot(
        kind="hist", bins=bins, edgecolor="black", ax=ax, color="#1f5cff"
    )
    ax.axvline(
        rejeicao + 0.5,
        color="red",
        linestyle="--",
        label=f"Rejeição direta (≤{rejeicao})",
    )
    if llm_min <= llm_max:
        ax.axvspan(
            llm_min - 0.5,
            llm_max + 0.5,
            color="#ffd8a8",
            alpha=0.35,
            label=f"Faixa LLM ({llm_min}–{llm_max})",
        )
    ax.axvline(
        aprovacao - 0.5,
        color="green",
        linestyle="--",
        label=f"Aprovação direta (≥{aprovacao})",
    )
    ax.set_title("Distribuição do score heurístico (Fase 3)")
    ax.set_xlabel("score_heuristico")
    ax.set_ylabel("nº de notícias")
    ax.legend(fontsize="small")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def fig_decisao_pipeline(df: pd.DataFrame, path: str | Path) -> bool:
    if df.empty:
        return False

    total = len(df)
    aprovada = df["fase1_aprovada"] if "fase1_aprovada" in df.columns else None
    n_descartadas = int((aprovada == False).sum()) if aprovada is not None else 0  # noqa: E712

    avancou = df[aprovada == True] if aprovada is not None else df.iloc[0:0]  # noqa: E712
    provider = (
        avancou["provider_fase4"]
        if "provider_fase4" in avancou.columns
        else pd.Series(dtype=object)
    )
    contagem = provider.value_counts(dropna=False)
    n_bypass = int(contagem.get("bypass", 0))
    n_llm = int(contagem.get("openai", 0))
    n_local = int(contagem.get("heuristica", 0)) + int(contagem.get("fallback", 0))

    n_relevante = 0
    if "relevancia_binaria" in avancou.columns:
        n_relevante = int((avancou["relevancia_binaria"] == 1).sum())

    categorias = [
        "Descartadas\n(Fase 1)",
        "Bypass\n(Fase 3→4)",
        "LLM\n(Fase 4)",
        "Heurística\n(sem LLM)",
    ]
    valores = [n_descartadas, n_bypass, n_llm, n_local]
    cores = ["#888888", "#1f5cff", "#ff7a18", "#2ca02c"]

    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.bar(categorias, valores, color=cores)
    for i, v in enumerate(valores):
        ax.text(i, v, str(int(v)), ha="center", va="bottom")
    ax.set_title(
        f"Funil de decisão do pipeline (N={total})\n"
        f"Relevantes (Fase 4): {n_relevante}"
    )
    ax.set_ylabel("nº de notícias")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def fig_tickers_origem(df: pd.DataFrame, path: str | Path) -> bool:
    cols = ["n_tickers_b3", "n_tickers_sp500", "n_tickers_outros"]
    if not set(cols).issubset(df.columns):
        return False
    totais = df[cols].sum()
    if float(totais.sum()) <= 0:
        return False

    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.pie(
        totais,
        labels=["B3", "S&P 500", "Outros/Não identificado"],
        autopct="%1.1f%%",
        startangle=90,
    )
    ax.set_title("Tickers relacionados por origem (Fase 2)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def fig_tempo_por_fase(df: pd.DataFrame, path: str | Path) -> bool:
    tempo_cols = [c for c in df.columns if c.endswith("_tempo_s")]
    if not tempo_cols:
        return False
    medias = df[tempo_cols].mean().sort_values(ascending=False)
    if medias.dropna().empty:
        return False

    fig, ax = plt.subplots(figsize=(7, 4))
    medias.plot(kind="bar", color="#1f5cff", ax=ax)
    ax.set_title("Tempo médio de processamento por fase")
    ax.set_ylabel("segundos")
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# Figuras extras (a partir de ExperimentRun.metricas)
# ---------------------------------------------------------------------------

def fig_sweep_threshold(metricas: Optional[dict], path: str | Path) -> bool:
    metricas = metricas or {}
    series = [
        ("relevancia_global", "Relevância global (Fase 1)", "#1f5cff"),
        ("score_heuristico", "Score heurístico (Fase 3)", "#ff7a18"),
    ]

    fig, ax = plt.subplots(figsize=(7, 4))
    desenhou = False
    for chave, rotulo, cor in series:
        rows = ((metricas.get(chave) or {}).get("thresholds")) or []
        pontos = [(r["threshold"], r["f1"]) for r in rows if r.get("f1") is not None]
        if not pontos:
            continue
        xs, ys = zip(*pontos)
        ax.plot(xs, ys, marker="o", markersize=3, label=rotulo, color=cor)
        best = (metricas.get(chave) or {}).get("best")
        if best and best.get("threshold") is not None:
            ax.axvline(
                best["threshold"],
                color=cor,
                linestyle=":",
                alpha=0.6,
                label=f"melhor {chave} = {best['threshold']:g}",
            )
        desenhou = True

    if not desenhou:
        plt.close(fig)
        return False

    ax.set_title("F1 em função do limiar (notícias anotadas)")
    ax.set_xlabel("threshold")
    ax.set_ylabel("F1")
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize="small")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def fig_confusao(metricas: Optional[dict], path: str | Path) -> bool:
    metricas = metricas or {}
    paineis = [("fase1", "Fase 1"), ("fase4", "Fase 4")]
    dados = []
    for chave, titulo in paineis:
        m = ((metricas.get(chave) or {}).get("metricas")) or {}
        if not m or not m.get("total"):
            dados.append((titulo, None))
        else:
            dados.append((titulo, m))

    if all(m is None for _, m in dados):
        return False

    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for ax, (titulo, m) in zip(axes, dados):
        if m is None:
            ax.axis("off")
            ax.set_title(f"{titulo}: sem labels")
            continue
        matriz = [[m["tn"], m["fp"]], [m["fn"], m["tp"]]]
        ax.imshow(matriz, cmap="Blues")
        ax.set_xticks([0, 1], labels=["Pred. 0", "Pred. 1"])
        ax.set_yticks([0, 1], labels=["Real 0", "Real 1"])
        for i in range(2):
            for j in range(2):
                ax.text(
                    j,
                    i,
                    str(matriz[i][j]),
                    ha="center",
                    va="center",
                    color="black",
                )
        ax.set_title(f"{titulo} — F1={m['f1']:.2f} (n={m['total']})")

    fig.suptitle("Matrizes de confusão (notícias anotadas)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def fig_distribuicoes(metricas: Optional[dict], path: str | Path) -> bool:
    distribuicoes = (metricas or {}).get("distribuicoes") or {}
    titulos = {
        "sentimento": "Sentimento",
        "impacto": "Impacto",
        "categoria": "Categoria",
    }
    disponiveis = {
        chave: valores
        for chave, valores in distribuicoes.items()
        if valores and chave in titulos
    }
    if not disponiveis:
        return False

    fig, axes = plt.subplots(1, len(disponiveis), figsize=(5 * len(disponiveis), 4))
    if len(disponiveis) == 1:
        axes = [axes]

    for ax, (chave, valores) in zip(axes, disponiveis.items()):
        itens = list(valores.items())[:8]
        nomes = [str(nome) or "vazio" for nome, _ in itens]
        qtds = [int(qtd) for _, qtd in itens]
        ax.bar(range(len(nomes)), qtds, color="#5c7cfa")
        ax.set_xticks(range(len(nomes)), labels=nomes, rotation=30, ha="right")
        ax.set_title(titulos[chave])
        ax.set_ylabel("nº de notícias")

    fig.suptitle("Distribuições da Fase 5")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def fig_comparativo_runs(rows: Iterable[dict], path: str | Path) -> bool:
    """Compara F1 (Fase 1 e Fase 4) entre execuções com rótulos."""
    rows = [
        r
        for r in rows
        if r.get("labeled_total")
        and (r.get("fase1_f1") is not None or r.get("fase4_f1") is not None)
    ]
    if not rows:
        return False

    labels = [r["label"] for r in rows]
    fase1 = [r.get("fase1_f1") or 0.0 for r in rows]
    fase4 = [r.get("fase4_f1") or 0.0 for r in rows]
    x = range(len(rows))
    largura = 0.38

    fig, ax = plt.subplots(figsize=(max(7, 1.2 * len(rows) + 3), 4))
    ax.bar([i - largura / 2 for i in x], fase1, largura, label="Fase 1", color="#1f5cff")
    ax.bar([i + largura / 2 for i in x], fase4, largura, label="Fase 4", color="#ff7a18")
    ax.set_xticks(list(x), labels=labels, rotation=30, ha="right")
    ax.set_ylabel("F1")
    ax.set_ylim(0, 1.05)
    ax.set_title("Comparativo entre execuções (F1 nas notícias anotadas)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# Dados auxiliares (resumo, CSV, amostra)
# ---------------------------------------------------------------------------

def gerar_resumo(
    df: pd.DataFrame,
    path: str | Path,
    *,
    parametros: Optional[dict] = None,
    run_meta: Optional[dict] = None,
) -> None:
    linhas: list[str] = []
    linhas.append("=== Resumo da execução — Motor Inteligente ===")
    if run_meta:
        linhas.append(f"Execução: {run_meta.get('run_id')}")
        linhas.append(f"Modelo: {run_meta.get('modelo')}")

    total = len(df)
    n_descartadas = int((df.get("fase1_aprovada") == False).sum()) if "fase1_aprovada" in df.columns else 0  # noqa: E712
    n_avancaram = int((df.get("fase1_aprovada") == True).sum()) if "fase1_aprovada" in df.columns else 0  # noqa: E712
    n_relevantes = int((df.get("relevancia_binaria") == 1).sum()) if "relevancia_binaria" in df.columns else 0

    linhas.append(f"Total de notícias processadas: {total}")
    if total:
        linhas.append(
            f"Descartadas na Fase 1: {n_descartadas} "
            f"({n_descartadas / total * 100:.1f}%)"
        )
    linhas.append(f"Avançaram para as Fases 2–4: {n_avancaram}")
    linhas.append(f"Classificadas como relevantes (Fase 4): {n_relevantes}")
    linhas.append("")

    if "provider_fase4" in df.columns:
        linhas.append("Decisão na Fase 4 por provider:")
        for nome, qtd in df["provider_fase4"].value_counts(dropna=False).items():
            linhas.append(f"  - {nome}: {qtd}")
        linhas.append("")

    if parametros:
        rejeicao, llm_min, llm_max, aprovacao = _cortes_fase4(parametros)
        fase1 = parametros.get("fase1") or {}
        fase2 = parametros.get("fase2") or {}
        linhas.append("Parâmetros efetivos:")
        linhas.append(
            f"  - Fase 1 θ_relevância: {fase1.get('threshold_relevancia')}"
        )
        linhas.append(f"  - Fase 1 centroides: {len(fase1.get('centroides_referencia') or [])}")
        linhas.append(
            f"  - Fase 2 θ_similaridade: {fase2.get('threshold_similaridade')}"
        )
        if fase2.get("estrategia") and fase2.get("estrategia") != "similaridade":
            linhas.append(
                f"  - Fase 2 estratégia: {fase2.get('estrategia')} "
                f"(top_k={fase2.get('top_k')}, "
                f"peso_lexical={fase2.get('peso_lexical')})"
            )
        linhas.append(
            f"  - Fase 4 cortes: rejeição ≤{rejeicao}, LLM {llm_min}–{llm_max}, "
            f"aprovação ≥{aprovacao}"
        )
        linhas.append("")

    if "score_heuristico" in df.columns and df["score_heuristico"].notna().any():
        linhas.append("Estatísticas do score_heuristico:")
        linhas.append(str(df["score_heuristico"].describe()))
        linhas.append("")

    cols_tickers = {"n_tickers_b3", "n_tickers_sp500", "n_tickers_outros"}
    if cols_tickers.issubset(df.columns):
        linhas.append("Média de tickers relacionados por notícia:")
        linhas.append(f"  - B3:     {df['n_tickers_b3'].mean():.2f}")
        linhas.append(f"  - S&P500: {df['n_tickers_sp500'].mean():.2f}")
        linhas.append(f"  - Outros: {df['n_tickers_outros'].mean():.2f}")
        linhas.append("")

    tempo_cols = [c for c in df.columns if c.endswith("_tempo_s")]
    if tempo_cols:
        linhas.append("Tempo médio por fase (segundos):")
        for coluna in tempo_cols:
            linhas.append(f"  - {coluna}: {df[coluna].mean():.4f}")

    Path(path).write_text("\n".join(linhas), encoding="utf-8")


def gerar_amostra_fase4(
    df: pd.DataFrame,
    path: str | Path,
    *,
    parametros: Optional[dict] = None,
    n_zona_cinzenta: int = 80,
    n_bypass: int = 30,
    random_state: int = 42,
) -> bool:
    if "fase1_aprovada" not in df.columns or "score_heuristico" not in df.columns:
        return False

    avancou = df[df["fase1_aprovada"] == True].copy()  # noqa: E712
    if avancou.empty:
        return False

    _, llm_min, llm_max, _ = _cortes_fase4(parametros)
    zona_cinzenta = avancou[
        (avancou["score_heuristico"] >= llm_min)
        & (avancou["score_heuristico"] <= llm_max)
    ]
    bypass = avancou[
        (avancou["score_heuristico"] < llm_min)
        | (avancou["score_heuristico"] > llm_max)
    ]

    amostra_zc = zona_cinzenta.sample(
        n=min(n_zona_cinzenta, len(zona_cinzenta)), random_state=random_state
    )
    amostra_bp = bypass.sample(
        n=min(n_bypass, len(bypass)), random_state=random_state
    )
    amostra = pd.concat([amostra_zc, amostra_bp], ignore_index=True)
    if amostra.empty:
        return False

    colunas = [
        c
        for c in [
            "noticia_id",
            "link",
            "publicado_em",
            "score_heuristico",
            "criterios_ativados",
            "relevancia_global",
            "provider_fase4",
            "relevancia_binaria",
            "confianca_fase4",
        ]
        if c in amostra.columns
    ]
    amostra = amostra[colunas]
    amostra["relevancia_manual"] = ""
    amostra["observacoes"] = ""
    amostra.to_csv(path, index=False, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------

def generate_all(
    df: pd.DataFrame,
    output_dir: str | Path,
    *,
    metricas: Optional[dict] = None,
    parametros: Optional[dict] = None,
    run_meta: Optional[dict] = None,
    comparativo_rows: Optional[Iterable[dict]] = None,
    include_amostra: bool = True,
) -> list[str]:
    """Gera todos os artefatos possíveis e devolve a lista de arquivos criados."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    escritos: list[str] = []

    def _tenta(nome: str, func) -> None:
        try:
            resultado = func()
        except Exception:
            resultado = False
        if resultado is not False and resultado is not None:
            escritos.append(nome)

    # Dados tabulares / texto (sempre que houver alguma linha).
    if not df.empty:
        df.to_csv(output / "metricas.csv", index=False, encoding="utf-8")
        escritos.append("metricas.csv")
    gerar_resumo(
        df, output / "resumo.txt", parametros=parametros, run_meta=run_meta
    )
    escritos.append("resumo.txt")

    _tenta(
        "fig_score_heuristico.png",
        lambda: fig_score_heuristico(
            df, output / "fig_score_heuristico.png", parametros=parametros
        ),
    )
    _tenta(
        "fig_decisao_pipeline.png",
        lambda: fig_decisao_pipeline(df, output / "fig_decisao_pipeline.png"),
    )
    _tenta(
        "fig_tickers_origem.png",
        lambda: fig_tickers_origem(df, output / "fig_tickers_origem.png"),
    )
    _tenta(
        "fig_tempo_por_fase.png",
        lambda: fig_tempo_por_fase(df, output / "fig_tempo_por_fase.png"),
    )
    _tenta(
        "fig_sweep_threshold.png",
        lambda: fig_sweep_threshold(metricas, output / "fig_sweep_threshold.png"),
    )
    _tenta(
        "fig_confusao.png",
        lambda: fig_confusao(metricas, output / "fig_confusao.png"),
    )
    _tenta(
        "fig_distribuicoes.png",
        lambda: fig_distribuicoes(metricas, output / "fig_distribuicoes.png"),
    )
    if comparativo_rows is not None:
        _tenta(
            "fig_comparativo_runs.png",
            lambda: fig_comparativo_runs(
                comparativo_rows, output / "fig_comparativo_runs.png"
            ),
        )
    if include_amostra:
        _tenta(
            "amostra_fase4.csv",
            lambda: gerar_amostra_fase4(
                df, output / "amostra_fase4.csv", parametros=parametros
            ),
        )

    return escritos


__all__ = [
    "ALL_FILES",
    "CHART_FILES",
    "DATA_FILES",
    "FILE_LABELS",
    "load_metrics",
    "generate_all",
]
