from __future__ import annotations

from typing import Any


_REGRA_DEFAULT = {
    "nome": "default",
    "prioridade": "baixa",
    "acoes": ["historico"],
    "explicacao": "Notícia registrada apenas para histórico.",
    "condicoes": {},
}


def _normalizar(valor: Any) -> str:
    if valor is None:
        return ""
    return str(valor).strip().lower()


def _obter_valor(metadados: dict[str, Any], campo: str) -> Any:
    if not isinstance(metadados, dict):
        return None
    return metadados.get(campo)


def _comparar_intervalo(valor: Any, condicao: dict[str, Any]) -> bool:
    try:
        numero = float(valor)
    except Exception:
        return False

    minimo = condicao.get("min")
    maximo = condicao.get("max")

    if minimo is not None:
        try:
            if numero < float(minimo):
                return False
        except Exception:
            return False

    if maximo is not None:
        try:
            if numero > float(maximo):
                return False
        except Exception:
            return False

    return True


def _avaliar_bloco(metadados: dict[str, Any], bloco: Any) -> bool:
    if bloco is None:
        return False

    if isinstance(bloco, list):
        return all(_avaliar_bloco(metadados, item) for item in bloco)

    if not isinstance(bloco, dict):
        return False

    if "e" in bloco:
        filhos = bloco.get("e") or []
        return all(_avaliar_bloco(metadados, item) for item in filhos)

    if "ou" in bloco:
        filhos = bloco.get("ou") or []
        return any(_avaliar_bloco(metadados, item) for item in filhos)

    for campo, esperado in bloco.items():
        valor = _obter_valor(metadados, campo)

        if isinstance(esperado, dict):
            if not _comparar_intervalo(valor, esperado):
                return False
            continue

        if _normalizar(valor) != _normalizar(esperado):
            return False

    return True


def avaliar_regras(
    metadados: dict[str, Any],
    regras: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    regras_validas = regras or []

    for regra in regras_validas:
        if not isinstance(regra, dict):
            continue

        condicoes = regra.get("condicoes", {}) or {}
        if _avaliar_bloco(metadados, condicoes):
            return {
                "nome": regra.get("nome", _REGRA_DEFAULT["nome"]),
                "prioridade": _normalizar(regra.get("prioridade")) or _REGRA_DEFAULT["prioridade"],
                "acoes": list(regra.get("acoes", _REGRA_DEFAULT["acoes"])),
                "explicacao": regra.get("explicacao") or _REGRA_DEFAULT["explicacao"],
            }

    return dict(_REGRA_DEFAULT)


__all__ = ["avaliar_regras"]
