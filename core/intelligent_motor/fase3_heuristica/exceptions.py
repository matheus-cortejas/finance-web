class HeuristicaError(Exception):
    pass


class ConfigError(HeuristicaError):
    pass


__all__ = ["HeuristicaError", "ConfigError"]
