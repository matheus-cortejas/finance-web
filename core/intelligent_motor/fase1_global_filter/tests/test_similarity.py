from core.intelligent_motor.fase1_global_filter.similarity import calcular_similaridade


def test_identity_and_orthogonality():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    c = [0.0, 1.0, 0.0]

    assert calcular_similaridade(a, b) == 1.0
    assert calcular_similaridade(a, c) == 0.0
