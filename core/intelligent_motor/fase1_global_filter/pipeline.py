import hashlib
import os
import time
from typing import Dict, Any, Optional

import yaml

from .preprocessor import preprocessar_texto
from .embedding_generator import EmbeddingGenerator
from .cache_manager import get_cache_manager
from .similarity import calcular_similaridade
from .exceptions import PipelineError, ValidationError, ModelError

# ---------- Função auxiliar de fallback (apenas para compatibilidade) ----------
def _load_config_from_file() -> Dict[str, Any]:
    cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def avaliar_relevancia_global(
    noticia: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Parâmetros:
        noticia: dicionário com 'id', 'titulo', 'descricao', 'conteudo'
        config: dicionário completo de configuração (carregado pelo orquestrador).
                Se None, carrega do arquivo (fallback para testes).
    """
    # Validação básica
    if noticia is None or not isinstance(noticia, dict):
        raise ValidationError("Entrada deve ser um dict contendo 'id', 'titulo' e 'descricao'")
    if "id" not in noticia:
        raise ValidationError("Campo 'id' ausente")
    if not noticia.get("titulo"):
        raise ValidationError("Campo 'titulo' ausente ou vazio")

    # Carrega config (se não fornecida, usa fallback do arquivo)
    if config is None:
        full_config = _load_config_from_file()
        config = full_config.get("fase1", {})
    else:
        config = config.get("fase1", {})   # extrai a subseção
    
    threshold = float(config.get("threshold_relevancia", 0.55))
    ttl = int(config.get("cache", {}).get("ttl_segundos", 86400))

    preproc_text = preprocessar_texto(noticia)
    if not preproc_text:
        return None

    chave = f"emb:{_sha256(preproc_text)}"

    cache = get_cache_manager()

    emb_noticia = None
    try:
        emb_noticia = cache.get(chave)
    except Exception:
        emb_noticia = None

    if emb_noticia is None:
        try:
            generator = EmbeddingGenerator.instance()
            emb_noticia = generator.gerar(preproc_text)
        except Exception as exc:
            raise ModelError(str(exc))

        try:
            cache.set(chave, emb_noticia, ttl)
        except Exception:
            pass

    # reference embeddings
    ref_key = "ref:financeiro_mult"

    emb_refs = None
    try:
        emb_refs = cache.get(ref_key)
    except Exception:
        emb_refs = None

    if emb_refs is None:
        centroides = config.get("centroides_referencia", [])
        if not centroides:
            centroides = ["Análise financeira e mercado econômico"]
        try:               
            generator = EmbeddingGenerator.instance()
            emb_refs = []
            for idx, texto in enumerate(centroides):
                emb_refs.append(generator.gerar(texto))
        except Exception as exc:
            raise ModelError(str(exc))

        try:
            cache.set(ref_key, emb_refs, ttl)
        except Exception:
            pass

    try:
        scores = []
        for idx, emb_ref in enumerate(emb_refs):
            sim = calcular_similaridade(emb_noticia, emb_ref)
            scores.append(sim)
        score = max(scores)
    except Exception as exc:
        raise PipelineError(str(exc))

    if score >= threshold:
        return {
            "id": noticia["id"],
            "relevancia_global": float(score),
            "embedding": emb_noticia
        }
    return None


__all__ = ["avaliar_relevancia_global"]