from core.intelligent_motor.fase6_decisor.score_final import calcular_score_final


def test_score_intermediario():
    score = calcular_score_final(
        {
            "relevancia_global": 0.5,
            "score_heuristico": 10,
            "urgencia": 5,
        },
        {"score_final": {"pesos": {"relevancia_global": 0.4, "score_heuristico": 0.4, "urgencia": 0.2}, "max_score_heuristico": 20, "max_urgencia": 10}},
    )

    assert score == 0.5


def test_score_maximo():
    score = calcular_score_final(
        {
            "relevancia_global": 1,
            "score_heuristico": 20,
            "urgencia": 10,
        },
        {"score_final": {"pesos": {"relevancia_global": 0.4, "score_heuristico": 0.4, "urgencia": 0.2}, "max_score_heuristico": 20, "max_urgencia": 10}},
    )

    assert score == 1.0


def test_score_minimo():
    score = calcular_score_final(
        {
            "relevancia_global": 0,
            "score_heuristico": 0,
            "urgencia": 0,
        },
        {"score_final": {"pesos": {"relevancia_global": 0.4, "score_heuristico": 0.4, "urgencia": 0.2}, "max_score_heuristico": 20, "max_urgencia": 10}},
    )

    assert score == 0.0
