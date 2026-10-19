"""Manifesto dos artefatos gerados por execução no laboratório.

Mantido separado de ``metrics_charts`` para que a interface (views/templates)
possa conhecer nomes e rótulos sem importar pandas/matplotlib.
"""

from __future__ import annotations

CHART_FILES = [
    "fig_score_heuristico.png",
    "fig_decisao_pipeline.png",
    "fig_tickers_origem.png",
    "fig_tempo_por_fase.png",
    "fig_sweep_threshold.png",
    "fig_confusao.png",
    "fig_distribuicoes.png",
    "fig_comparativo_runs.png",
]
DATA_FILES = ["resumo.txt", "metricas.csv", "amostra_fase4.csv"]
ALL_FILES = CHART_FILES + DATA_FILES

# Rótulos usados na interface para cada arquivo.
FILE_LABELS = {
    "fig_score_heuristico.png": "Distribuição do score heurístico (Fase 3)",
    "fig_decisao_pipeline.png": "Funil de decisão do pipeline",
    "fig_tickers_origem.png": "Tickers relacionados por origem (Fase 2)",
    "fig_tempo_por_fase.png": "Tempo médio por fase",
    "fig_sweep_threshold.png": "Varredura de limiar (F1 × threshold)",
    "fig_confusao.png": "Matrizes de confusão (Fases 1 e 4)",
    "fig_distribuicoes.png": "Distribuições de sentimento/impacto/categoria",
    "fig_comparativo_runs.png": "Comparativo entre execuções",
    "resumo.txt": "Resumo textual",
    "metricas.csv": "Métricas em CSV",
    "amostra_fase4.csv": "Amostra para anotação da Fase 4",
}

__all__ = ["ALL_FILES", "CHART_FILES", "DATA_FILES", "FILE_LABELS"]
