from core.intelligent_motor.fase6_decisor.perfis import PerfilUsuario


def test_categoria_permitida_com_lista_vazia():
    perfil = PerfilUsuario.from_dict(
        {
            "canais_habilitados": ["email", "push", "dashboard"],
            "notificar_apenas_categorias": [],
        },
        config={"acoes_canais": {"dashboard_destacado": "dashboard"}},
    )

    assert perfil.categoria_permitida("commodities") is True


def test_categoria_bloqueada():
    perfil = PerfilUsuario.from_dict(
        {
            "canais_habilitados": ["email", "push", "dashboard"],
            "notificar_apenas_categorias": ["commodities"],
        },
        config={"acoes_canais": {"dashboard_destacado": "dashboard"}},
    )

    assert perfil.categoria_permitida("macroeconomia") is False


def test_canal_habilitado():
    perfil = PerfilUsuario.from_dict(
        {
            "canais_habilitados": ["email", "dashboard"],
            "notificar_apenas_categorias": [],
        },
        config={"acoes_canais": {"dashboard_destacado": "dashboard"}},
    )

    assert perfil.canal_habilitado("email") is True
    assert perfil.canal_habilitado("dashboard_destacado") is True


def test_canal_desabilitado():
    perfil = PerfilUsuario.from_dict(
        {
            "canais_habilitados": ["dashboard"],
            "notificar_apenas_categorias": [],
        },
        config={"acoes_canais": {"dashboard_destacado": "dashboard"}},
    )

    assert perfil.canal_habilitado("push") is False
