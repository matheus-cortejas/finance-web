r"""Estratégias da Fase 2 (associação notícia → ticker).

O baseline do artigo (A0) associa por similaridade de cosseno contra *todos*
os ativos, com um único limiar. Isso gera associações espúrias (ex.: notícia
da PETR4 ligada a BRKM5/PRIO3/DOW/AVY). Este módulo implementa, de forma
**opcional e determinística**, duas defesas adicionais:

* **A1 — gating por setor**: classifica o setor da notícia por palavras-chave
  e restringe os candidatos aos ativos do mesmo setor. Ativos sem setor
  conhecido (``""``/``Outros``/``Não se aplica``) funcionam como curingas, para
  não derrubar o recall. Se nenhum setor for detectado, não há filtro (cai no
  comportamento de A0).
* **A2 — guarda lexical**: além do gating, força a inclusão de tickers citados
  explicitamente no texto (regex ``\b[A-Z]{4,5}\d\b``) e de nomes de empresas de
  um dicionário de aliases.

As funções aqui são puras (não acessam Django), para serem testáveis e
reutilizáveis; a resolução de ``Ativo.setor`` fica em :func:`setores_por_ticker`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set

from ..setores import SETOR_NAO_APLICA, pontuar_setores

ESTRATEGIA_SIMILARIDADE = "similaridade"
ESTRATEGIA_SETOR = "similaridade_setor"
ESTRATEGIA_SETOR_LEXICAL = "similaridade_setor_lexical"

ESTRATEGIAS = (
    ESTRATEGIA_SIMILARIDADE,
    ESTRATEGIA_SETOR,
    ESTRATEGIA_SETOR_LEXICAL,
)

# Setores "neutros": não servem para restringir candidatos.
_SETORES_CURINGA = {"", "outros", SETOR_NAO_APLICA.lower()}

_TICKER_RE = re.compile(r"\b[A-Z]{4,5}\d\b", re.IGNORECASE)


def _texto(noticia: Dict[str, Any]) -> str:
    return " ".join(
        str(noticia.get(parte) or "")
        for parte in ("titulo", "descricao", "conteudo")
    )


def texto_noticia(noticia: Dict[str, Any]) -> str:
    """Texto consolidado da notícia (título + descrição + conteúdo)."""
    return _texto(noticia)


def setores_detectados(noticia: Dict[str, Any]) -> Set[str]:
    """Setores inferidos do texto da notícia (classificador lexical)."""
    return set(pontuar_setores(_texto(noticia)))


def tickers_lexicais(noticia: Dict[str, Any]) -> List[str]:
    """Tickers citados explicitamente no texto (ex.: ``PETR4``)."""
    encontrados = _TICKER_RE.findall(_texto(noticia))
    return list(dict.fromkeys(t.upper() for t in encontrados))


def _e_curinga(setor: str) -> bool:
    return (setor or "").strip().lower() in _SETORES_CURINGA


def filtrar_por_setor(
    carteira: Iterable[str],
    setores_ativos: Dict[str, str],
    setores_noticia: Set[str],
) -> List[str]:
    """Mantém ativos do(s) setor(es) da notícia + curingas.

    Sem setor detectado, devolve a carteira inteira (comportamento A0).
    """
    if not setores_noticia:
        return list(carteira)
    alvo = {s.lower() for s in setores_noticia}
    selecionados = []
    for ticker in carteira:
        setor = setores_ativos.get(ticker, "")
        if _e_curinga(setor) or setor.lower() in alvo:
            selecionados.append(ticker)
    return selecionados


def aplicar_estrategia(
    estrategia: str,
    carteira: List[str],
    noticia: Dict[str, Any],
    setores_ativos: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Pré-filtra a carteira de candidatos conforme a estratégia.

    Devolve sempre um subconjunto de ``carteira`` (preserva a ordem).
    """
    estrategia = (estrategia or ESTRATEGIA_SIMILARIDADE).strip().lower()
    if estrategia not in ESTRATEGIAS or estrategia == ESTRATEGIA_SIMILARIDADE:
        return list(carteira)

    setores_ativos = setores_ativos or {}
    candidatos = filtrar_por_setor(
        carteira, setores_ativos, setores_detectados(noticia)
    )

    if estrategia == ESTRATEGIA_SETOR_LEXICAL:
        universo = set(carteira)
        for ticker in tickers_lexicais(noticia):
            if ticker in universo and ticker not in candidatos:
                candidatos.append(ticker)
    return candidatos


def setores_por_ticker() -> Dict[str, str]:
    """Lê ``Ativo.setor`` do banco. Import preguiçoso e tolerante a falhas."""
    try:
        from core.models import Ativo

        return dict(
            Ativo.objects.exclude(setor="").values_list("ticker", "setor")
        )
    except Exception:
        return {}


__all__ = [
    "ESTRATEGIA_SIMILARIDADE",
    "ESTRATEGIA_SETOR",
    "ESTRATEGIA_SETOR_LEXICAL",
    "ESTRATEGIAS",
    "setores_detectados",
    "tickers_lexicais",
    "texto_noticia",
    "filtrar_por_setor",
    "aplicar_estrategia",
    "setores_por_ticker",
]
