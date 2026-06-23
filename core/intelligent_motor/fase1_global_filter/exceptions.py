class PipelineError(Exception):
    pass


class ValidationError(PipelineError):
    pass


class CacheError(PipelineError):
    pass


class ModelError(PipelineError):
    pass


__all__ = ["PipelineError", "ValidationError", "CacheError", "ModelError"]
