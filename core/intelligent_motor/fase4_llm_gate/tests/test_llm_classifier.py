from core.intelligent_motor.fase4_llm_gate.llm_classifier import LLMClassifier


class DummyClient:
    class Chat:
        @staticmethod
        def create(**kwargs):
            return {"choices": [{"message": {"content": "1"}}]}

    def __init__(self, api_key=None):
        self.chat = DummyClient.Chat()


def test_classificar_returns_1():
    client = DummyClient()
    clf = LLMClassifier(client=client, model="test", fallback_result=0)
    assert clf.classificar("prompt") == 1


def test_classificar_returns_0_with_invalid_response():
    class BadClient:
        class Chat:
            @staticmethod
            def create(**kwargs):
                return {"choices": [{"message": {"content": "maybe"}}]}

        def __init__(self):
            self.chat = BadClient.Chat()

    bad = BadClient()
    clf = LLMClassifier(client=bad, model="test", fallback_result=0)
    assert clf.classificar("p") == 0


def test_classificar_fallback_when_no_client():
    clf = LLMClassifier(client=None, fallback_result=1)
    assert clf.classificar("p") == 1
