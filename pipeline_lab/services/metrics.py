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


def pair_metrics_sets(pairs: Iterable[tuple[set, set]]) -> dict:
    """Métricas por par (ticker) a partir de conjuntos previsto x verdadeiro."""
    tp = fp = fn = 0
    itens = 0
    exatos = 0
    for previsto, verdadeiro in pairs:
        itens += 1
        tp += len(previsto & verdadeiro)
        fp += len(previsto - verdadeiro)
        fn += len(verdadeiro - previsto)
        if previsto == verdadeiro:
            exatos += 1
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    return {
        "itens": itens,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "exatos": exatos,
        "acuracia_conjunto": round(_safe_div(exatos, itens), 4),
    }


def label_target_fase1(label) -> bool | None:
    """Alvo da Fase 1: relevância financeira; cai para `relevancia` (legado)."""
    if label.relevancia_financeira is not None:
        return bool(label.relevancia_financeira)
    if label.relevancia is not None:
        return bool(label.relevancia)
    return None


def _labeled_items(run: ExperimentRun):
    items = list(run.classifications.select_related("noticia__label").all())
    labeled = []
    for item in items:
        try:
            label = item.noticia.label
        except Exception:
            label = None
        if label is None:
            continue
        if label.relevancia is None and label.relevancia_financeira is None:
            continue
        labeled.append((item, label))
    return items, labeled


def _sweep(
    labeled,
    getter: Callable,
    thresholds: list[float],
    target: Callable = lambda label: bool(label.relevancia),
) -> dict:
    rows = [
        (getter(item), bool(target(label)))
        for item, label in labeled
        if getter(item) is not None and target(label) is not None
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
        (bool(item.fase1_aprovada), label_target_fase1(label))
        for item, label in labeled
        if item.fase1_aprovada is not None
        and label_target_fase1(label) is not None
    ]
    fase4_pairs = [
        (item.relevancia_binaria == 1, bool(label.relevancia))
        for item, label in labeled
        if item.relevancia_binaria is not None and label.relevancia is not None
    ]

    fase2_pairs = [
        (
            set(item.tickers_relacionados or []),
            set(label.tickers_corretos or [])
            | set(label.tickers_faltantes or []),
        )
        for item, label in labeled
        if label.tickers_anotados
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
    fase1_sweep = _sweep(
        labeled,
        lambda item: item.relevancia_global,
        [round(x / 20.0, 2) for x in range(0, 21)],
        target=label_target_fase1,
    )

    distribuicoes = {}
    for field in ("sentimento", "impacto", "categoria"):
        counter = Counter(
            (getattr(item, field) or "vazio") for item in items
        )
        distribuicoes[field] = dict(counter.most_common())

    fase2_uso: Counter = Counter()
    for item in items:
        det = item.fase2_detalhes or {}
        if det.get("estrategia"):
            fase2_uso[f"estrategia:{det['estrategia']}"] += 1
        rerank = det.get("rerank") or {}
        if rerank.get("enabled"):
            fase2_uso[
                "rerank:" + ("aplicado" if rerank.get("aplicado") else "indisponivel")
            ] += 1
        llm = det.get("llm") or {}
        if llm.get("enabled"):
            fase2_uso[f"llm:{llm.get('provider') or 'fallback'}"] += 1

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
        "fase2": {
            "metricas": pair_metrics_sets(fase2_pairs),
            "avaliadas": len(fase2_pairs),
        },
        "fase4": {
            "metricas": binary_metrics(fase4_pairs),
            "avaliadas": len(fase4_pairs),
        },
        "score_heuristico": score_sweep,
        "relevancia_global": relevancia_sweep,
        "fase1_sweep": fase1_sweep,
        "distribuicoes": distribuicoes,
        "fase2_uso": dict(fase2_uso.most_common()),
    }
