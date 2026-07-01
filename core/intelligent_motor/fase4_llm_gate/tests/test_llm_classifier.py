from unittest.mock import MagicMock
from core.intelligent_motor.fase4_llm_gate.llm_classifier import LLMClassifier


def _make_classifier(client=None):
    config = {"fase4": {"llm": {"provider": "openai", "model": "test"}, "cache": {"enabled": False}}}
    clf = LLMClassifier(config=config)
    if client is not None:
        clf.client = client
    return clf


class DummyClient:
    class Chat:
        class Completions:
            @staticmethod
            def create(**kwargs):
                msg = MagicMock()
                msg.content = "1"
                choice = MagicMock()
                choice.message = msg
                result = MagicMock()
                result.choices = [choice]
                return result

    def __init__(self, api_key=None):
        self.chat = DummyClient.Chat()
        self.chat.completions = DummyClient.Chat.Completions()


def test_classificar_returns_decision():
    client = DummyClient()
    clf = _make_classifier(client=client)
    result = clf.classificar("prompt")
    assert result == 1


def test_classificar_fallback_when_no_client():
    clf = _make_classifier(client=None)
    result = clf.classificar("prompt")
    assert result == 1
