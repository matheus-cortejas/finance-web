"""Fase 6 - Decisor de Alertas."""

from .perfis import PerfilUsuario
from .motor_regras import avaliar_regras
from .score_final import calcular_score_final
from .explicacao import gerar_explicacao
from .pipeline import decidir_alerta
from .exceptions import Fase6Error

__all__ = [
    "PerfilUsuario",
    "avaliar_regras",
    "calcular_score_final",
    "gerar_explicacao",
    "decidir_alerta",
    "Fase6Error",
]
