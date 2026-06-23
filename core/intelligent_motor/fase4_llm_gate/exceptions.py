class Fase4Error(Exception):
    """Erro base para a Fase 4."""


class ConfigError(Fase4Error):
    """Erro ao carregar ou validar configuração."""


class LLMError(Fase4Error):
    """Erro relacionado à chamada ou resposta da LLM."""


class CacheError(Fase4Error):
    """Erro relacionado ao sistema de cache."""


__all__ = ["Fase4Error", "ConfigError", "LLMError", "CacheError"]
