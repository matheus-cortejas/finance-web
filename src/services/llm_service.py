from __future__ import annotations

from llm.relevance import is_relevant


def assess_article(title: str, description: str, content: str, assets: list) -> dict:
    return is_relevant(title, description, content, assets)
