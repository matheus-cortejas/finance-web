from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


def _normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""
    return str(valor).strip().lower()


def _como_lista(valores: Any) -> list[str]:
    if valores is None:
        return []
    if isinstance(valores, (list, tuple, set)):
        return [
            texto
            for texto in (_normalizar_texto(item) for item in valores)
            if texto
        ]
    normalizado = _normalizar_texto(valores)
    return [normalizado] if normalizado else []


@dataclass(slots=True)
class PerfilUsuario:
    canais_habilitados: list[str] = field(default_factory=list)
    notificar_apenas_categorias: list[str] = field(default_factory=list)
    thresholds_personalizados: dict[str, Any] | None = None

    _acoes_canais: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def padrao(
        cls,
        config: dict[str, Any] | None = None,
    ) -> "PerfilUsuario":
        perfil = (config or {}).get("perfil_padrao", {}) or {}
        return cls.from_dict(perfil, config=config)

    @classmethod
    def from_dict(
        cls,
        dados: dict[str, Any] | None,
        config: dict[str, Any] | None = None,
    ) -> "PerfilUsuario":
        if dados is None:
            dados = {}
        if not isinstance(dados, dict):
            raise TypeError("Perfil deve ser um dicionário")

        acoes_canais = (config or {}).get("acoes_canais", {}) or {}

        return cls(
            canais_habilitados=_como_lista(dados.get("canais_habilitados")),
            notificar_apenas_categorias=_como_lista(
                dados.get("notificar_apenas_categorias")
            ),
            thresholds_personalizados=dados.get("thresholds_personalizados"),
            _acoes_canais={
                _normalizar_texto(chave): _normalizar_texto(valor)
                for chave, valor in acoes_canais.items()
                if _normalizar_texto(chave)
            },
        )

    def categoria_permitida(self, categoria: Any) -> bool:
        categoria_normalizada = _normalizar_texto(categoria)
        if not self.notificar_apenas_categorias:
            return True
        return categoria_normalizada in self.notificar_apenas_categorias

    def canal_habilitado(self, canal: Any) -> bool:
        canal_normalizado = _normalizar_texto(canal)
        if not canal_normalizado:
            return False

        if canal_normalizado == "historico":
            return True

        canal_base = self._acoes_canais.get(canal_normalizado, canal_normalizado)
        return canal_base in self.canais_habilitados

    def canais_filtrados(self, canais: Iterable[Any]) -> list[str]:
        return [
            _normalizar_texto(canal)
            for canal in canais
            if self .canal_habilitado(canal)
        ]
