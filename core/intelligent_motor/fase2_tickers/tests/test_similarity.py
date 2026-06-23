from core.intelligent_motor.fase2_tickers.similarity import cosine_similarity


def test_identity_and_orthogonality():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    c = [0.0, 1.0, 0.0]

    assert cosine_similarity(a, b) == 1.0
    assert cosine_similarity(a, c) == 0.0
