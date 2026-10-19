from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Callable, Iterable

from pipeline_lab.models import ExperimentRun


def _safe_div(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def binary_metrics(pairs: Iterable[tuple[bool, bool]]) -> dict:
    tp = fp = tn = fn = 0
    total = 0
    for pred, true in pairs:
        total += 1
        if pred and true:
            tp += 1
        elif pred and not true:
            fp += 1
        elif not pred and true:
            fn += 1
        else:
            tn += 1

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    accuracy = _safe_div(tp + tn, total)

    return {
        "total": total,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "positivos_reais": tp + fn,
        "negativos_reais": tn + fp,
    }


def _labeled_items(run: ExperimentRun):
    items = list(
        run.classifications.select_related("noticia__label").all()
    )
    labeled = []
    for item in items:
        try:
            label = item.noticia.label
        except Exception:
            label = None
        if label is not None and label.relevancia is not None:
            labeled.append((item, label))
    return items, labeled


def _sweep(
    labeled,
    getter: Callable,
    thresholds: list[float],
) -> dict:
    rows = [
        (getter(item), bool(label.relevancia))
        for item, label in labeled
        if getter(item) is not None
    ]
    if not rows:
        return {"thresholds": [], "best": None}

    results = []
    for threshold in thresholds:
        metrics = binary_metrics(
            (float(score) >= threshold, truth) for score, truth in rows
        )
        metrics["threshold"] = round(float(threshold), 4)
        results.append(metrics)

    best = max(
        results,
        key=lambda item: (item["f1"], item["precision"], item["recall"]),
    )
    return {"thresholds": results, "best": best}


def compute_run_metrics(run: ExperimentRun) -> dict:
    items, labeled = _labeled_items(run)

    fase1_pairs = [
        (bool(item.fase1_aprovada), bool(label.relevancia))
        for item, label in labeled
        if item.fase1_aprovada is not None
    ]
    fase4_pairs = [
        (item.relevancia_binaria == 1, bool(label.relevancia))
        for item, label in labeled
        if item.relevancia_binaria is not None
    ]

    score_sweep = _sweep(
        labeled,
        lambda item: item.score_heuristico,
        list(range(0, 21)),
    )
    relevancia_sweep = _sweep(
        labeled,
        lambda item: item.relevancia_global,
        [round(x / 20.0, 2) for x in range(0, 21)],
    )

    distribuicoes = {}
    for field in ("sentimento", "impacto", "categoria"):
        counter = Counter(
            (getattr(item, field) or "vazio") for item in items
        )
        distribuicoes[field] = dict(counter.most_common())

    tempos = [
        float(item.tempos.get("total_s"))
        for item in items
        if item.tempos and item.tempos.get("total_s") is not None
    ]

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "run_id": run.id,
        "modelo": run.modelo,
        "embedding_dim": run.embedding_dim,
        "total_noticias": run.total_noticias,
        "classificadas": len(items),
        "cobertura": round(_safe_div(len(items), run.total_noticias), 4),
        "labeled_total": len(labeled),
        "erros": sum(1 for item in items if item.erro),
        "tempo_medio_s": round(sum(tempos) / len(tempos), 4) if tempos else None,
        "fase1": {
            "metricas": binary_metrics(fase1_pairs),
            "avaliadas": len(fase1_pairs),
        },
        "fase4": {
            "metricas": binary_metrics(fase4_pairs),
            "avaliadas": len(fase4_pairs),
        },
        "score_heuristico": score_sweep,
        "relevancia_global": relevancia_sweep,
        "distribuicoes": distribuicoes,
    }
