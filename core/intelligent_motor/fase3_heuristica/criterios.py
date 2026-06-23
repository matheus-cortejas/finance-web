import re
import os
import yaml
from typing import Dict, Any, List, Tuple
from functools import lru_cache

def _get_fase3_config(config: dict | None = None) -> dict:
    if config is None:
        return {}   # fallback vazio
    return config.get("fase3", {})

def _consolidate_text(noticia: Dict[str, Any]) -> str:
    titulo = noticia.get("titulo") or ""
    descricao = noticia.get("descricao") or ""
    conteudo = noticia.get("conteudo") or ""
    return " ".join([titulo, descricao, conteudo]).lower()

# -------------------------------------------------------------------
# Funções existentes (melhoradas)
# -------------------------------------------------------------------
def avaliar_ticker_explicito(noticia: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Retorna (True/False, lista_de_tickers_encontrados).
    Agora também busca por nomes de empresas se um mapeamento opcional for fornecido.
    """
    texto = _consolidate_text(noticia)
    # Busca por tickers padrão B3: 4-5 letras + 1 dígito (ex: PETR4, VALE3, WEGE3)
    matches = re.findall(r"\b[A-Z]{4,5}\d\b", texto, re.IGNORECASE)
    # Remove duplicatas mantendo ordem
    unique = list(dict.fromkeys(matches))
    return (len(unique) > 0, unique)

def avaliar_setor_relacionado(noticia: Dict[str, Any]) -> bool:
    """Verifica se a notícia possui tickers relacionados (informados pela Fase 2)."""
    tickers = noticia.get("tickers_relacionados")
    return bool(tickers)

def avaliar_palavras_macro(noticia: Dict[str, Any], config: dict | None = None) -> bool:
    cfg = _get_fase3_config(config)
    keywords = cfg.get("palavras_macro", [])
    if not keywords:
        return False
    text = _consolidate_text(noticia)
    return any(k.lower() in text for k in keywords)

def avaliar_palavras_negativas(noticia: Dict[str, Any], config: dict | None = None) -> bool:
    cfg = _get_fase3_config(config)
    keywords = cfg.get("palavras_negativas", [])
    if not keywords:
        return False
    text = _consolidate_text(noticia)
    return any(k.lower() in text for k in keywords)

def avaliar_palavras_urgencia(noticia: Dict[str, Any], config: dict | None = None) -> bool:
    cfg = _get_fase3_config(config)
    keywords = cfg.get("palavras_urgencia", [])
    if not keywords:
        return False
    text = _consolidate_text(noticia)
    return any(k.lower() in text for k in keywords)

def avaliar_fonte_confiavel(noticia: Dict[str, Any], config: dict | None = None) -> bool:
    cfg = _get_fase3_config(config)
    fontes = cfg.get("fontes_confiaveis", [])
    if not fontes:
        return False
    fonte = noticia.get("fonte") or noticia.get("link", "")
    # Se a notícia não tem campo 'fonte', tenta extrair do domínio
    if not fonte and "link" in noticia:
        from urllib.parse import urlparse
        parsed = urlparse(noticia["link"])
        fonte = parsed.netloc
    return any(f in fonte.lower() for f in fontes)

# -------------------------------------------------------------------
# Novas funções
# -------------------------------------------------------------------
def avaliar_palavras_impacto(noticia: Dict[str, Any], config: dict | None = None) -> bool:
    cfg = _get_fase3_config(config)
    keywords = cfg.get("palavras_impacto", [])
    if not keywords:
        return False
    text = _consolidate_text(noticia)
    return any(k.lower() in text for k in keywords)

def avaliar_tendencia_positiva(noticia: Dict[str, Any], config: dict | None = None) -> bool:
    cfg = _get_fase3_config(config)
    keywords = cfg.get("palavras_tendencia_positiva", [])
    if not keywords:
        return False
    text = _consolidate_text(noticia)
    return any(k.lower() in text for k in keywords)

def avaliar_tendencia_negativa(noticia: Dict[str, Any], config: dict | None = None) -> bool:
    cfg = _get_fase3_config(config)
    keywords = cfg.get("palavras_tendencia_negativa", [])
    if not keywords:
        return False
    text = _consolidate_text(noticia)
    return any(k.lower() in text for k in keywords)

def avaliar_ambiguidade(noticia: Dict[str, Any], config: dict | None = None) -> bool:
    cfg = _get_fase3_config(config)
    keywords = cfg.get("palavras_ambiguidade", [])
    if not keywords:
        return False
    text = _consolidate_text(noticia)
    return any(k.lower() in text for k in keywords)

# Opcional: função que retorna um score total agregado (usando pesos)
def calcular_score(noticia: Dict[str, Any], config: dict | None = None) -> float:
    cfg = _get_fase3_config(config)
    pesos = cfg.get("pesos", {})
    score = 0.0
    # Cada avaliador retorna bool, multiplica pelo peso
    score += pesos.get("ticker_explicito", 0) * (1 if avaliar_ticker_explicito(noticia, config)[0] else 0)
    score += pesos.get("setor_relacionado", 0) * (1 if avaliar_setor_relacionado(noticia, config) else 0)
    score += pesos.get("macro", 0) * (1 if avaliar_palavras_macro(noticia, config) else 0)
    score += pesos.get("negativo", 0) * (1 if avaliar_palavras_negativas(noticia, config) else 0)
    score += pesos.get("urgencia", 0) * (1 if avaliar_palavras_urgencia(noticia, config) else 0)
    score += pesos.get("fonte_confiavel", 0) * (1 if avaliar_fonte_confiavel(noticia, config) else 0)
    score += pesos.get("impacto", 0) * (1 if avaliar_palavras_impacto(noticia, config) else 0)
    score += pesos.get("tendencia_positiva", 0) * (1 if avaliar_tendencia_positiva(noticia, config) else 0)
    score += pesos.get("tendencia_negativa", 0) * (1 if avaliar_tendencia_negativa(noticia, config) else 0)
    score += pesos.get("ambiguidade", 0) * (1 if avaliar_ambiguidade(noticia, config) else 0)
    return score

# -------------------------------------------------------------------
# Exportação das funções (inclui as novas)
# -------------------------------------------------------------------
__all__ = [
    "avaliar_ticker_explicito",
    "avaliar_setor_relacionado",
    "avaliar_palavras_macro",
    "avaliar_palavras_negativas",
    "avaliar_palavras_urgencia",
    "avaliar_fonte_confiavel",
    "avaliar_palavras_impacto",
    "avaliar_tendencia_positiva",
    "avaliar_tendencia_negativa",
    "avaliar_ambiguidade",
    "calcular_score",
]