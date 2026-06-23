# fase5_rich_classification/pipeline.py
import logging
from typing import Optional

from .llm_classifier import LLMClassifier
from .prompt_builder import build_prompt
from .validator import validar_resposta
from .fallback import fallback_classify
from .exceptions import LLMError, ValidationError

logger = logging.getLogger(__name__)


def classificar_noticia_rica(
    noticia: dict,
    config: Optional[dict] = None,
    classifier: Optional[LLMClassifier] = None,
) -> dict:
    """
    Executa a Fase 5 - Classificação Rica.

    Parâmetros:
        noticia: dicionário enriquecido pelas fases anteriores.
        config: dicionário completo de configuração (carregado pelo orquestrador).
        classifier: opcional, instância de LLMClassifier.

    Retorna:
        noticia enriquecida com sentimento, impacto, urgencia, categoria, explicacao.
    """
    # Extrai configuração da fase5 (se não fornecida, usa dicionário vazio)
    if config is None:
        fase5_cfg = {}
    else:
        fase5_cfg = config.get("fase5", {})

    # Apenas notícias aprovadas na Fase 4
    if noticia.get("relevancia_binaria") != 1:
        logger.debug("Fase5 ignorada para notícia não aprovada pela Fase4")
        return noticia

    if classifier is None:
        # Passa a config para o LLMClassifier da fase 5
        classifier = LLMClassifier(config=config)

    prompt = build_prompt(noticia=noticia, config=fase5_cfg)

    try:
        result = classifier.classificar(prompt)
        validated = validar_resposta(result, config=fase5_cfg)
        noticia.update(validated)
        logger.info("FASE5_LLM_SUCCESS categoria=%s impacto=%s urgencia=%s",
                    validated.get("categoria"), validated.get("impacto"), validated.get("urgencia"))
        return noticia

    except (LLMError, ValidationError) as exc:
        logger.info("FASE5_LLM_ERROR fallback=True erro=%s", exc)
    except Exception as exc:
        logger.exception("FASE5_UNEXPECTED_ERROR fallback=True erro=%s", exc)

    # Fallback centralizado
    fallback_result = fallback_classify(noticia=noticia, config=fase5_cfg)
    noticia.update(fallback_result)
    logger.info("FASE5_FALLBACK sentimento=%s impacto=%s urgencia=%s categoria=%s",
                fallback_result.get("sentimento"), fallback_result.get("impacto"),
                fallback_result.get("urgencia"), fallback_result.get("categoria"))

    return noticia